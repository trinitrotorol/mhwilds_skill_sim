from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver import (
    BuildCandidate,
    SkillRequirement,
    enumerate_build_candidates,
    enumerate_decoration_placement_combinations,
    enumerate_equipment_selections,
    filter_build_candidates_by_skill_requirements,
    search_build_candidates_by_skill_requirements,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.catalog_search import (
    search_catalog_build_candidates_by_skill_requirements,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"

REQUIRED_PARTS = (
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
)


class CatalogSubclass(Catalog):
    pass


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def equipment_definition(
    part: EquipmentPart,
    equipment_id: str | None = None,
    *,
    skills: tuple[SkillContribution, ...] = (),
    slots: tuple[DecorationSlot, ...] = (),
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
    )


def complete_equipment(
    *,
    weapon_skills: tuple[SkillContribution, ...] = (),
    weapon_slots: tuple[DecorationSlot, ...] = (),
) -> tuple[EquipmentDefinition, ...]:
    return tuple(
        equipment_definition(
            part,
            skills=weapon_skills if part is EquipmentPart.WEAPON else (),
            slots=weapon_slots if part is EquipmentPart.WEAPON else (),
        )
        for part in REQUIRED_PARTS
    )


def decoration_definition(
    decoration_id: str = "decoration:weapon-1",
    *,
    required_slot: DecorationSlot | None = None,
    skills: tuple[SkillContribution, ...] | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=required_slot or weapon_slot(1),
        skills=skills or (skill("skill:decoration-default", 1),),
    )


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def tiny_catalog() -> Catalog:
    return load_catalog(path=FIXTURE_PATH)


def catalog_search(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
) -> tuple[BuildCandidate, ...]:
    return search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=requirements,
    )


def test_empty_catalog_and_empty_requirements_returns_empty_tuple() -> None:
    catalog = Catalog(schema_version=1, equipment=(), decorations=())

    assert catalog_search(catalog=catalog, requirements=()) == ()


def test_tiny_catalog_empty_requirements_returns_candidates() -> None:
    catalog = tiny_catalog()

    result = catalog_search(catalog=catalog, requirements=())

    assert len(result) > 0
    assert result == search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=(),
    )


def test_tiny_catalog_equipment_skills_can_satisfy_requirements() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:attack-boost", 3),),
    )

    assert any(
        build.placements == () and dict(build.skill_levels)["skill:attack-boost"] >= 3
        for build in result
    )


def test_tiny_catalog_decoration_skills_can_satisfy_requirements() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:weakness-exploit", 4),),
    )

    assert len(result) > 0
    assert all(
        dict(build.skill_levels)["skill:weakness-exploit"] >= 4 for build in result
    )
    assert any(
        "fixture:decoration:armor-tenderizer-2"
        in tuple(placement.decoration_id for placement in build.placements)
        for build in result
    )


def test_tiny_catalog_unsatisfied_requirements_return_empty_tuple() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:not-present", 1),),
    )

    assert result == ()


def test_multiple_requirements_must_all_be_satisfied() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(
            requirement("skill:attack-boost", 3),
            requirement("skill:critical-eye", 3),
        ),
    )

    assert len(result) > 0
    assert all(
        dict(build.skill_levels)["skill:attack-boost"] >= 3
        and dict(build.skill_levels)["skill:critical-eye"] >= 3
        for build in result
    )


def test_result_order_matches_existing_search_order() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:critical-eye", 3),)

    result = catalog_search(catalog=catalog, requirements=requirements)
    direct_result = search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=requirements,
    )

    assert result == direct_result


def test_returns_tuple_with_build_candidate_elements() -> None:
    result = catalog_search(catalog=tiny_catalog(), requirements=())

    assert type(result) is tuple
    assert all(isinstance(build, BuildCandidate) for build in result)


def test_search_requires_keyword_arguments() -> None:
    signature = inspect.signature(search_catalog_build_candidates_by_skill_requirements)

    assert signature.parameters["catalog"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["requirements"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        search_catalog_build_candidates_by_skill_requirements(tiny_catalog(), ())  # type: ignore[call-arg]


def test_inputs_are_not_modified() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:attack-boost", 3),)
    original_catalog = catalog
    original_equipment = catalog.equipment
    original_decorations = catalog.decorations
    original_requirements = requirements

    catalog_search(catalog=catalog, requirements=requirements)

    assert catalog == original_catalog
    assert catalog.equipment == original_equipment
    assert catalog.decorations == original_decorations
    assert requirements == original_requirements


def test_solver_package_exports_catalog_search_and_keeps_existing_public_exports() -> (
    None
):
    from mhwilds_skill_sim.solver import BuildCandidate as ExportedBuildCandidate
    from mhwilds_skill_sim.solver import SkillRequirement as ExportedRequirement
    from mhwilds_skill_sim.solver import (
        enumerate_build_candidates as exported_builds,
    )
    from mhwilds_skill_sim.solver import (
        enumerate_decoration_placement_combinations as exported_decorations,
    )
    from mhwilds_skill_sim.solver import (
        enumerate_equipment_selections as exported_equipment,
    )
    from mhwilds_skill_sim.solver import (
        filter_build_candidates_by_skill_requirements as exported_filter,
    )
    from mhwilds_skill_sim.solver import (
        search_build_candidates_by_skill_requirements as exported_search,
    )
    from mhwilds_skill_sim.solver import (
        search_catalog_build_candidates_by_skill_requirements as exported_catalog_search,
    )
    from mhwilds_skill_sim.solver import (
        skill_levels_satisfy_requirements as exported_requirements,
    )

    assert ExportedBuildCandidate is BuildCandidate
    assert ExportedRequirement is SkillRequirement
    assert exported_builds is enumerate_build_candidates
    assert exported_decorations is enumerate_decoration_placement_combinations
    assert exported_equipment is enumerate_equipment_selections
    assert exported_filter is filter_build_candidates_by_skill_requirements
    assert exported_search is search_build_candidates_by_skill_requirements
    assert (
        exported_catalog_search is search_catalog_build_candidates_by_skill_requirements
    )
    assert exported_requirements is skill_levels_satisfy_requirements


def test_delegates_to_existing_search_with_catalog_contents() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:weakness-exploit", 4),)

    assert catalog_search(catalog=catalog, requirements=requirements) == (
        search_build_candidates_by_skill_requirements(
            equipment=catalog.equipment,
            decorations=catalog.decorations,
            requirements=requirements,
        )
    )


@pytest.mark.parametrize("catalog", ["catalog", {}, None])
def test_rejects_non_catalog_values(catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=catalog,  # type: ignore[arg-type]
            requirements=(),
        )


def test_accepts_catalog_subclass() -> None:
    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())

    assert catalog_search(catalog=catalog, requirements=()) == ()


def test_propagates_requirement_list_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=[requirement()],  # type: ignore[arg-type]
        )


def test_propagates_invalid_requirement_element_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=("skill:attack-boost",),  # type: ignore[arg-type]
        )


def test_propagates_duplicate_requirement_skill_id_value_error() -> None:
    with pytest.raises(ValueError, match="requirements"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
        )


def test_manual_catalog_search_does_not_require_load_catalog() -> None:
    catalog = Catalog(
        schema_version=1,
        equipment=complete_equipment(weapon_skills=(skill("skill:attack-boost", 1),)),
        decorations=(),
    )

    result = catalog_search(
        catalog=catalog,
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert len(result) == 1
    assert result[0].equipment == catalog.equipment


def test_search_does_not_rank_or_limit_satisfying_candidates() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:attack-boost", 3),),
    )

    assert len(result) > 1
    assert result == search_build_candidates_by_skill_requirements(
        equipment=tiny_catalog().equipment,
        decorations=tiny_catalog().decorations,
        requirements=(requirement("skill:attack-boost", 3),),
    )


def test_search_adds_no_request_or_result_public_types() -> None:
    import mhwilds_skill_sim.solver as solver
    import mhwilds_skill_sim.solver.catalog_search as catalog_search_module

    for name in ("SearchRequest", "SolverResult", "BuildResult"):
        assert not hasattr(solver, name)
        assert not hasattr(catalog_search_module, name)
