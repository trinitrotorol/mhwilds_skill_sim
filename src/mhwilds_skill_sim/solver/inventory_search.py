"""Finite-inventory CP-SAT search with explicit deterministic equipment ranking."""

from __future__ import annotations

from time import monotonic

from ortools.sat.python import cp_model

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart, WeaponKind
from mhwilds_skill_sim.solver import cp_sat_search as cp
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.inventory import (
    InventorySearchSnapshot,
    apply_inventory_to_catalog,
    validate_candidate_inventory,
)
from mhwilds_skill_sim.solver.preferences import SkillPreference
from mhwilds_skill_sim.solver.requirements import SkillRequirement


def search_inventory_ranked_builds(
    *,
    catalog: Catalog,
    catalog_revision: str,
    snapshot: InventorySearchSnapshot,
    requirements: tuple[SkillRequirement, ...],
    preferences: tuple[SkillPreference, ...],
    max_results: int,
    weapon_kind: WeaponKind | None = None,
    timeout_seconds: float = 10.0,
) -> cp.CpSatBuildSearchResult:
    """Rank by capped score, decoration count, then catalog equipment order.

    A timeout during either objective or tie resolution is reported as unproven.
    Snapshot filtering does not mutate the source Catalog or persisted inventory.
    """
    cp._validate_inputs(
        catalog=catalog,
        requirements=requirements,
        weapon_kind=weapon_kind,
        timeout_seconds=timeout_seconds,
    )
    cp._validate_preferences(preferences=preferences)
    if type(max_results) is not int or not 1 <= max_results <= 20:
        raise ValueError("inventory max_results must be between 1 and 20")
    catalog = apply_inventory_to_catalog(
        catalog=catalog,
        snapshot=snapshot,
        catalog_revision=catalog_revision,
    )
    deadline = monotonic() + timeout_seconds
    choices = cp._prepare_candidates_by_part(catalog=catalog, weapon_kind=weapon_kind)
    if any(not values for values in choices.values()):
        return cp.CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)
    decoration_limit = cp._calculate_decoration_limit(candidates_by_part=choices)
    cp._validate_preference_objective_range(
        preferences=preferences,
        decoration_limit=decoration_limit,
    )
    model, equipment_variables, decoration_variables, score_variables = (
        cp._create_ranked_model(
            catalog=catalog,
            requirements=requirements,
            preferences=preferences,
            candidates_by_part=choices,
            decoration_limit=decoration_limit,
        )
    )
    quantities = dict(snapshot.decorations)
    for decoration, variable in zip(catalog.decorations, decoration_variables):
        model.add(
            variable
            <= min(
                quantities.get(decoration.decoration_id, 0),
                decoration_limit,
            )
        )
    primary = sum(score_variables, 0) * (decoration_limit + 1) - sum(
        decoration_variables,
        0,
    )
    candidates: list[BuildCandidate] = []

    def finish(*, exhausted: bool = False, timed_out: bool = False):
        return cp.CpSatBuildSearchResult(
            candidates=tuple(candidates),
            exhausted=exhausted,
            timed_out=timed_out,
        )

    def solve(current):
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None, cp_model.UNKNOWN
        return cp._solve_model(model=current, timeout_seconds=remaining)

    while True:
        solver, status = solve(model)
        if status == cp_model.INFEASIBLE:
            return finish(exhausted=True)
        if status == cp_model.UNKNOWN:
            return finish(timed_out=True)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE) or solver is None:
            raise RuntimeError("inventory CP-SAT model failed")
        if len(candidates) >= max_results:
            return finish(timed_out=status != cp_model.OPTIMAL)
        proven = status == cp_model.OPTIMAL
        if proven:
            # Lexicographic equipment ties are separate bounded solves, avoiding
            # mixed-radix objective integer overflow on the expanded real catalog.
            tied = model.clone()
            tied.add(primary == solver.value(primary))
            for part in EquipmentPart:
                rank = sum(
                    index * variable
                    for index, (_, variable) in enumerate(equipment_variables[part])
                )
                tied.minimize(rank)
                tie_solver, tie_status = solve(tied)
                if tie_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    proven = False
                    break
                solver = tie_solver
                if tie_status != cp_model.OPTIMAL:
                    proven = False
                    break
                tied.add(rank == solver.value(rank))
        candidate = cp._reconstruct_ranked_candidate(
            solver=solver,
            catalog=catalog,
            requirements=requirements,
            preferences=preferences,
            equipment_variables=equipment_variables,
            decoration_variables=decoration_variables,
            preference_score_variables=score_variables,
        )
        validate_candidate_inventory(candidate=candidate, snapshot=snapshot)
        candidates.append(candidate)
        if not proven:
            return finish(timed_out=True)
        selected = cp._reconstruct_selected_equipment_variables(
            solver=solver,
            equipment_variables=equipment_variables,
        )
        model.add(sum(selected, 0) <= len(selected) - 1)
