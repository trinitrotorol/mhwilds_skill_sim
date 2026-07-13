"""CP-SAT search for complete Catalog builds."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from time import monotonic

from ortools.sat.python import cp_model

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.domain.skill import SkillKind
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.appraisal_charms import (
    generate_appraisal_charm_equipment_candidates,
)
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.equipment_filtering import (
    filter_equipment_candidates_by_weapon_kind,
)
from mhwilds_skill_sim.solver.equipment_variants import (
    expand_equipment_bonus_skill_variants,
)
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.validation.build import aggregate_valid_build_skill_levels
from mhwilds_skill_sim.validation.placement import DecorationPlacement


_EquipmentVariables = dict[
    EquipmentPart,
    tuple[tuple[EquipmentDefinition, cp_model.IntVar], ...],
]


@dataclass(frozen=True, slots=True)
class CpSatBuildSearchResult:
    candidates: tuple[BuildCandidate, ...]
    exhausted: bool
    timed_out: bool

    def __post_init__(self) -> None:
        if type(self.candidates) is not tuple:
            raise TypeError("candidates must be tuple")
        for candidate in self.candidates:
            if not isinstance(candidate, BuildCandidate):
                raise TypeError("candidates must contain only BuildCandidate")

        if type(self.exhausted) is not bool:
            raise TypeError("exhausted must be bool")
        if type(self.timed_out) is not bool:
            raise TypeError("timed_out must be bool")
        if self.exhausted and self.timed_out:
            raise ValueError("exhausted and timed_out must not both be true")


def find_catalog_build_candidate_with_cp_sat(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    weapon_kind: WeaponKind | None = None,
    timeout_seconds: float = 10.0,
) -> BuildCandidate | None:
    """Find one valid build satisfying all requirements, if CP-SAT can prove one."""

    _validate_inputs(
        catalog=catalog,
        requirements=requirements,
        weapon_kind=weapon_kind,
        timeout_seconds=timeout_seconds,
    )

    candidates_by_part = _prepare_candidates_by_part(
        catalog=catalog,
        weapon_kind=weapon_kind,
    )
    if any(not candidates_by_part[part] for part in EquipmentPart):
        return None

    model, equipment_variables, decoration_variables = _create_model(
        catalog=catalog,
        requirements=requirements,
        candidates_by_part=candidates_by_part,
    )
    solver, status = _solve_model(model=model, timeout_seconds=timeout_seconds)

    if status == cp_model.INFEASIBLE:
        return None
    if status == cp_model.UNKNOWN:
        raise TimeoutError("CP-SAT search timeout before finding a build")
    if status == cp_model.MODEL_INVALID:
        raise RuntimeError("CP-SAT model is invalid")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"unexpected CP-SAT solver status: {status}")

    return _reconstruct_candidate(
        solver=solver,
        catalog=catalog,
        requirements=requirements,
        equipment_variables=equipment_variables,
        decoration_variables=decoration_variables,
    )


def search_catalog_build_candidates_with_cp_sat(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    max_results: int,
    weapon_kind: WeaponKind | None = None,
    timeout_seconds: float = 10.0,
) -> CpSatBuildSearchResult:
    """Find a limited sequence of distinct Catalog equipment selections."""

    _validate_inputs(
        catalog=catalog,
        requirements=requirements,
        weapon_kind=weapon_kind,
        timeout_seconds=timeout_seconds,
    )
    _validate_max_results(value=max_results)
    deadline = monotonic() + timeout_seconds

    candidates_by_part = _prepare_candidates_by_part(
        catalog=catalog,
        weapon_kind=weapon_kind,
    )
    if any(not candidates_by_part[part] for part in EquipmentPart):
        return CpSatBuildSearchResult(
            candidates=(),
            exhausted=True,
            timed_out=False,
        )

    model, equipment_variables, decoration_variables = _create_model(
        catalog=catalog,
        requirements=requirements,
        candidates_by_part=candidates_by_part,
    )
    candidates: list[BuildCandidate] = []

    while True:
        remaining_seconds = deadline - monotonic()
        if remaining_seconds <= 0:
            return CpSatBuildSearchResult(
                candidates=tuple(candidates),
                exhausted=False,
                timed_out=True,
            )

        solver, status = _solve_model(
            model=model,
            timeout_seconds=remaining_seconds,
        )

        if status == cp_model.INFEASIBLE:
            return CpSatBuildSearchResult(
                candidates=tuple(candidates),
                exhausted=True,
                timed_out=False,
            )
        if status == cp_model.UNKNOWN:
            return CpSatBuildSearchResult(
                candidates=tuple(candidates),
                exhausted=False,
                timed_out=True,
            )
        if status == cp_model.MODEL_INVALID:
            raise RuntimeError("CP-SAT model is invalid")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"unexpected CP-SAT solver status: {status}")

        if status == cp_model.FEASIBLE:
            if len(candidates) < max_results:
                candidates.append(
                    _reconstruct_limited_candidate(
                        solver=solver,
                        catalog=catalog,
                        requirements=requirements,
                        equipment_variables=equipment_variables,
                        decoration_variables=decoration_variables,
                    )
                )
            return CpSatBuildSearchResult(
                candidates=tuple(candidates),
                exhausted=False,
                timed_out=True,
            )

        if len(candidates) >= max_results:
            return CpSatBuildSearchResult(
                candidates=tuple(candidates),
                exhausted=False,
                timed_out=False,
            )

        candidates.append(
            _reconstruct_limited_candidate(
                solver=solver,
                catalog=catalog,
                requirements=requirements,
                equipment_variables=equipment_variables,
                decoration_variables=decoration_variables,
            )
        )
        selected_variables = _reconstruct_selected_equipment_variables(
            solver=solver,
            equipment_variables=equipment_variables,
        )
        model.add(
            sum(selected_variables, 0) <= len(selected_variables) - 1,
        )


def _prepare_candidates_by_part(
    *,
    catalog: Catalog,
    weapon_kind: WeaponKind | None,
) -> dict[EquipmentPart, tuple[EquipmentDefinition, ...]]:
    filtered_equipment = filter_equipment_candidates_by_weapon_kind(
        equipment=catalog.equipment,
        weapon_kind=weapon_kind,
    )
    generated_charms = generate_appraisal_charm_equipment_candidates(
        skill_groups=catalog.appraisal_charm_skill_groups,
        patterns=catalog.appraisal_charm_patterns,
        skill_definitions=catalog.skills,
    )
    expanded_equipment = expand_equipment_bonus_skill_variants(
        equipment=filtered_equipment + generated_charms,
        skill_definitions=catalog.skills,
    )

    return {
        part: tuple(
            equipment for equipment in expanded_equipment if equipment.part is part
        )
        for part in EquipmentPart
    }


def _validate_inputs(
    *,
    catalog: object,
    requirements: object,
    weapon_kind: object,
    timeout_seconds: object,
) -> None:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")

    if type(requirements) is not tuple:
        raise TypeError("requirements must be tuple")

    seen_skill_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, SkillRequirement):
            raise TypeError("requirements must contain only SkillRequirement")
        if requirement.skill_id in seen_skill_ids:
            raise ValueError("requirements must not contain duplicate skill_id")
        seen_skill_ids.add(requirement.skill_id)

    if weapon_kind is not None and not isinstance(weapon_kind, WeaponKind):
        raise TypeError("weapon_kind must be WeaponKind or None")

    if type(timeout_seconds) not in (int, float):
        raise TypeError("timeout_seconds must be int or float")
    if type(timeout_seconds) is float and not isfinite(timeout_seconds):
        raise ValueError("timeout_seconds must be finite")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")


def _validate_max_results(*, value: object) -> None:
    if type(value) is not int:
        raise TypeError("max_results must be int")
    if value < 0:
        raise ValueError("max_results must be at least zero")


def _create_model(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    candidates_by_part: dict[EquipmentPart, tuple[EquipmentDefinition, ...]],
) -> tuple[cp_model.CpModel, _EquipmentVariables, tuple[cp_model.IntVar, ...]]:
    model = cp_model.CpModel()

    equipment_variables: _EquipmentVariables = {}
    ordered_equipment_variables: list[cp_model.IntVar] = []
    for part_index, part in enumerate(EquipmentPart):
        choices: list[tuple[EquipmentDefinition, cp_model.IntVar]] = []
        for candidate_index, equipment in enumerate(candidates_by_part[part]):
            variable = model.new_bool_var(
                f"equipment_{part_index}_{candidate_index}",
            )
            choices.append((equipment, variable))
            ordered_equipment_variables.append(variable)
        equipment_variables[part] = tuple(choices)
        model.add_exactly_one(variable for _, variable in choices)

    maximum_slot_count = sum(
        max(len(equipment.slots) for equipment in candidates_by_part[part])
        for part in EquipmentPart
    )
    decoration_variables = tuple(
        model.new_int_var(0, maximum_slot_count, f"decoration_{index}")
        for index, _ in enumerate(catalog.decorations)
    )

    _add_slot_capacity_constraints(
        model=model,
        equipment_variables=equipment_variables,
        decorations=catalog.decorations,
        decoration_variables=decoration_variables,
    )
    _add_skill_requirement_constraints(
        model=model,
        equipment_variables=equipment_variables,
        decorations=catalog.decorations,
        decoration_variables=decoration_variables,
        catalog=catalog,
        requirements=requirements,
    )

    model.minimize(sum(decoration_variables, 0))
    model.add_decision_strategy(
        ordered_equipment_variables,
        cp_model.CHOOSE_FIRST,
        cp_model.SELECT_MAX_VALUE,
    )
    if decoration_variables:
        model.add_decision_strategy(
            decoration_variables,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE,
        )

    return model, equipment_variables, decoration_variables


def _add_slot_capacity_constraints(
    *,
    model: cp_model.CpModel,
    equipment_variables: _EquipmentVariables,
    decorations: tuple[DecorationDefinition, ...],
    decoration_variables: tuple[cp_model.IntVar, ...],
) -> None:
    thresholds = sorted(
        {
            slot.level
            for choices in equipment_variables.values()
            for equipment, _ in choices
            for slot in equipment.slots
        }
        | {decoration.required_slot.level for decoration in decorations}
    )

    for kind in DecorationKind:
        for threshold in thresholds:
            required_capacity = sum(
                (
                    variable
                    for decoration, variable in zip(
                        decorations,
                        decoration_variables,
                    )
                    if decoration.required_slot.kind is kind
                    and decoration.required_slot.level >= threshold
                ),
                0,
            )
            selected_capacity_terms = []
            for choices in equipment_variables.values():
                for equipment, variable in choices:
                    matching_slot_count = sum(
                        slot.kind is kind and slot.level >= threshold
                        for slot in equipment.slots
                    )
                    if matching_slot_count:
                        selected_capacity_terms.append(matching_slot_count * variable)

            model.add(required_capacity <= sum(selected_capacity_terms, 0))


def _add_skill_requirement_constraints(
    *,
    model: cp_model.CpModel,
    equipment_variables: _EquipmentVariables,
    decorations: tuple[DecorationDefinition, ...],
    decoration_variables: tuple[cp_model.IntVar, ...],
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
) -> None:
    skills_by_id = {skill.skill_id: skill for skill in catalog.skills}

    for requirement_index, requirement in enumerate(requirements):
        total_terms = []
        for choices in equipment_variables.values():
            for equipment, variable in choices:
                contribution = sum(
                    skill.level
                    for skill in equipment.skills
                    if skill.skill_id == requirement.skill_id
                )
                if contribution:
                    total_terms.append(contribution * variable)

        for decoration, variable in zip(decorations, decoration_variables):
            contribution = sum(
                skill.level
                for skill in decoration.skills
                if skill.skill_id == requirement.skill_id
            )
            if contribution:
                total_terms.append(contribution * variable)

        skill_definition = skills_by_id.get(requirement.skill_id)
        if skill_definition is not None and skill_definition.kind in (
            SkillKind.SERIES,
            SkillKind.GROUP,
        ):
            if skill_definition.kind is SkillKind.SERIES:
                selected_piece_terms = [
                    variable
                    for choices in equipment_variables.values()
                    for equipment, variable in choices
                    if equipment.series_skill_id == requirement.skill_id
                ]
            else:
                selected_piece_terms = [
                    variable
                    for choices in equipment_variables.values()
                    for equipment, variable in choices
                    if equipment.group_skill_id == requirement.skill_id
                ]

            selected_piece_count = sum(selected_piece_terms, 0)
            for rank_index, rank in enumerate(skill_definition.ranks):
                required_pieces = rank.required_pieces
                if required_pieces is None:
                    raise RuntimeError("bonus skill rank must require pieces")

                active_rank = model.new_bool_var(
                    f"requirement_{requirement_index}_rank_{rank_index}",
                )
                model.add(
                    selected_piece_count >= required_pieces,
                ).only_enforce_if(active_rank)
                model.add(
                    selected_piece_count <= required_pieces - 1,
                ).only_enforce_if(active_rank.Not())
                total_terms.append(active_rank)

        model.add(sum(total_terms, 0) >= requirement.min_level)


def _solve_model(
    *,
    model: cp_model.CpModel,
    timeout_seconds: float,
) -> tuple[cp_model.CpSolver, cp_model.CpSolverStatus]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.log_search_progress = False
    fixed_search = getattr(cp_model, "FIXED_SEARCH", None)
    if fixed_search is not None:
        solver.parameters.search_branching = fixed_search
    status = solver.solve(model)
    return solver, status


def _reconstruct_equipment(
    *,
    solver: cp_model.CpSolver,
    equipment_variables: _EquipmentVariables,
) -> tuple[EquipmentDefinition, ...]:
    selected_equipment: list[EquipmentDefinition] = []
    for part in EquipmentPart:
        selected_for_part = [
            equipment
            for equipment, variable in equipment_variables[part]
            if solver.value(variable) == 1
        ]
        if len(selected_for_part) != 1:
            raise RuntimeError("CP-SAT model did not select exactly one equipment item")
        selected_equipment.append(selected_for_part[0])

    return tuple(selected_equipment)


def _reconstruct_selected_equipment_variables(
    *,
    solver: cp_model.CpSolver,
    equipment_variables: _EquipmentVariables,
) -> tuple[cp_model.IntVar, ...]:
    selected_variables: list[cp_model.IntVar] = []
    for part in EquipmentPart:
        selected_for_part = [
            variable
            for _, variable in equipment_variables[part]
            if solver.value(variable) == 1
        ]
        if len(selected_for_part) != 1:
            raise RuntimeError("CP-SAT model did not select exactly one equipment item")
        selected_variables.append(selected_for_part[0])

    return tuple(selected_variables)


def _reconstruct_candidate(
    *,
    solver: cp_model.CpSolver,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    equipment_variables: _EquipmentVariables,
    decoration_variables: tuple[cp_model.IntVar, ...],
) -> BuildCandidate:
    selected_equipment = _reconstruct_equipment(
        solver=solver,
        equipment_variables=equipment_variables,
    )
    placements = _reconstruct_placements(
        solver=solver,
        selected_equipment=selected_equipment,
        decorations=catalog.decorations,
        decoration_variables=decoration_variables,
    )
    aggregated = aggregate_valid_build_skill_levels(
        equipment=selected_equipment,
        decorations=catalog.decorations,
        placements=placements,
        skill_definitions=catalog.skills,
    )
    candidate = BuildCandidate(
        equipment=selected_equipment,
        placements=placements,
        skill_levels=tuple(aggregated.items()),
    )
    if not skill_levels_satisfy_requirements(
        skill_levels=dict(candidate.skill_levels),
        requirements=requirements,
    ):
        raise RuntimeError("reconstructed CP-SAT build does not satisfy requirements")

    return candidate


def _reconstruct_limited_candidate(
    *,
    solver: cp_model.CpSolver,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    equipment_variables: _EquipmentVariables,
    decoration_variables: tuple[cp_model.IntVar, ...],
) -> BuildCandidate:
    try:
        return _reconstruct_candidate(
            solver=solver,
            catalog=catalog,
            requirements=requirements,
            equipment_variables=equipment_variables,
            decoration_variables=decoration_variables,
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("failed to reconstruct a valid CP-SAT build") from error


def _reconstruct_placements(
    *,
    solver: cp_model.CpSolver,
    selected_equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    decoration_variables: tuple[cp_model.IntVar, ...],
) -> tuple[DecorationPlacement, ...]:
    selected_slots: list[tuple[int, int, DecorationSlot]] = []
    for equipment_index, equipment in enumerate(selected_equipment):
        selected_slots.extend(
            (equipment_index, slot_index, slot)
            for slot_index, slot in enumerate(equipment.slots)
        )

    decoration_instances: list[tuple[int, int, DecorationDefinition]] = []
    for decoration_index, (decoration, variable) in enumerate(
        zip(decorations, decoration_variables),
    ):
        count = solver.value(variable)
        if count < 0:
            raise RuntimeError("CP-SAT model returned a negative decoration count")
        decoration_instances.extend(
            (decoration.required_slot.level, decoration_index, decoration)
            for _ in range(count)
        )
    decoration_instances.sort(key=lambda item: (-item[0], item[1]))

    used_slots: set[tuple[int, int]] = set()
    placed: list[tuple[int, int, DecorationPlacement]] = []
    for _, _, decoration in decoration_instances:
        compatible_slots = (
            slot_entry
            for slot_entry in selected_slots
            if (slot_entry[0], slot_entry[1]) not in used_slots
            and slot_entry[2].kind is decoration.required_slot.kind
            and slot_entry[2].level >= decoration.required_slot.level
        )
        selected_slot = min(
            compatible_slots,
            key=lambda slot_entry: (
                slot_entry[2].level,
                slot_entry[0],
                slot_entry[1],
            ),
            default=None,
        )
        if selected_slot is None:
            raise RuntimeError("CP-SAT model and decoration reconstruction disagree")

        equipment_index, slot_index, _ = selected_slot
        used_slots.add((equipment_index, slot_index))
        placed.append(
            (
                equipment_index,
                slot_index,
                DecorationPlacement(
                    equipment_id=selected_equipment[equipment_index].equipment_id,
                    slot_index=slot_index,
                    decoration_id=decoration.decoration_id,
                ),
            )
        )

    placed.sort(key=lambda item: (item[0], item[1]))
    return tuple(placement for _, _, placement in placed)
