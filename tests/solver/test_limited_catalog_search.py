from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.solver import (
    BuildCandidate,
    SkillRequirement,
    enumerate_build_candidates,
    enumerate_decoration_placement_combinations,
    enumerate_equipment_selections,
    filter_build_candidates_by_skill_requirements,
    search_build_candidates_by_skill_requirements,
    search_catalog_build_candidates_by_skill_requirements,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.search_result import (
    BuildCandidateSearchResult,
    search_limited_catalog_build_candidates_by_skill_requirements,
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


class CandidateTuple(tuple):
    pass


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def equipment_definition(
    part: EquipmentPart,
    equipment_id: str | None = None,
    *,
    skills: tuple[SkillContribution, ...] = (),
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=(),
    )


def complete_equipment(
    *,
    weapon_skills: tuple[SkillContribution, ...] = (),
) -> tuple[EquipmentDefinition, ...]:
    return tuple(
        equipment_definition(
            part,
            skills=weapon_skills if part is EquipmentPart.WEAPON else (),
        )
        for part in REQUIRED_PARTS
    )


def candidate(
    *,
    equipment_id: str = "equipment:weapon",
    skill_levels: tuple[tuple[str, int], ...] = (("skill:attack-boost", 1),),
) -> BuildCandidate:
    return BuildCandidate(
        equipment=(equipment_definition(EquipmentPart.WEAPON, equipment_id),),
        placements=(),
        skill_levels=skill_levels,
    )


def candidate_generator() -> Iterator[BuildCandidate]:
    yield candidate()


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def tiny_catalog() -> Catalog:
    return load_catalog(path=FIXTURE_PATH)


def empty_catalog() -> Catalog:
    return Catalog(schema_version=1, equipment=(), decorations=())


def manual_catalog() -> Catalog:
    return Catalog(
        schema_version=1,
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
        decorations=(),
    )


def limited_search(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    max_results: int,
) -> BuildCandidateSearchResult:
    return search_limited_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=requirements,
        max_results=max_results,
    )


def test_search_result_keeps_valid_values() -> None:
    build = candidate()

    result = BuildCandidateSearchResult(
        candidates=(build,),
        total_count=1,
        truncated=False,
    )

    assert result.candidates == (build,)
    assert result.total_count == 1
    assert result.truncated is False


def test_search_result_value_semantics_and_hashing() -> None:
    result = BuildCandidateSearchResult(
        candidates=(candidate(),),
        total_count=1,
        truncated=False,
    )

    assert result == BuildCandidateSearchResult(
        candidates=(candidate(),),
        total_count=1,
        truncated=False,
    )
    assert result != BuildCandidateSearchResult(
        candidates=(),
        total_count=1,
        truncated=True,
    )
    assert {result, result} == {result}


def test_search_result_is_frozen() -> None:
    result = BuildCandidateSearchResult(candidates=(), total_count=0, truncated=False)

    with pytest.raises(FrozenInstanceError):
        result.total_count = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "candidates",
    [[candidate()], {candidate()}, candidate_generator(), None],
)
def test_search_result_rejects_non_tuple_candidates(candidates: object) -> None:
    with pytest.raises(TypeError, match="candidates"):
        BuildCandidateSearchResult(
            candidates=candidates,  # type: ignore[arg-type]
            total_count=0,
            truncated=False,
        )


def test_search_result_rejects_candidates_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="candidates"):
        BuildCandidateSearchResult(
            candidates=CandidateTuple((candidate(),)),
            total_count=1,
            truncated=False,
        )


@pytest.mark.parametrize("invalid_candidate", ["candidate", None])
def test_search_result_rejects_invalid_candidate_elements(
    invalid_candidate: object,
) -> None:
    with pytest.raises(TypeError, match="candidates"):
        BuildCandidateSearchResult(
            candidates=(invalid_candidate,),  # type: ignore[arg-type]
            total_count=1,
            truncated=False,
        )


@pytest.mark.parametrize("total_count", [True, 1.5, "1", None])
def test_search_result_rejects_non_int_total_count(total_count: object) -> None:
    with pytest.raises(TypeError, match="total_count"):
        BuildCandidateSearchResult(
            candidates=(),
            total_count=total_count,  # type: ignore[arg-type]
            truncated=False,
        )


def test_search_result_rejects_negative_total_count() -> None:
    with pytest.raises(ValueError, match="total_count"):
        BuildCandidateSearchResult(candidates=(), total_count=-1, truncated=False)


@pytest.mark.parametrize("truncated", [0, 1, "false", None])
def test_search_result_rejects_non_bool_truncated(truncated: object) -> None:
    with pytest.raises(TypeError, match="truncated"):
        BuildCandidateSearchResult(
            candidates=(),
            total_count=0,
            truncated=truncated,  # type: ignore[arg-type]
        )


def test_search_result_rejects_candidates_longer_than_total_count() -> None:
    with pytest.raises(ValueError, match="candidates"):
        BuildCandidateSearchResult(
            candidates=(candidate(),),
            total_count=0,
            truncated=False,
        )


def test_search_result_rejects_not_truncated_count_mismatch() -> None:
    with pytest.raises(ValueError, match="truncated"):
        BuildCandidateSearchResult(candidates=(), total_count=1, truncated=False)


@pytest.mark.parametrize(
    ("candidates", "total_count"),
    [
        ((), 0),
        ((candidate(),), 1),
    ],
)
def test_search_result_rejects_truncated_without_omitted_candidates(
    candidates: tuple[BuildCandidate, ...],
    total_count: int,
) -> None:
    with pytest.raises(ValueError, match="truncated"):
        BuildCandidateSearchResult(
            candidates=candidates,
            total_count=total_count,
            truncated=True,
        )


def test_solver_package_exports_search_result() -> None:
    from mhwilds_skill_sim.solver import (
        BuildCandidateSearchResult as ExportedSearchResult,
    )

    assert ExportedSearchResult is BuildCandidateSearchResult


def test_empty_catalog_returns_empty_untruncated_result() -> None:
    result = limited_search(catalog=empty_catalog(), requirements=(), max_results=0)

    assert result == BuildCandidateSearchResult(
        candidates=(),
        total_count=0,
        truncated=False,
    )


def test_zero_limit_truncates_when_candidates_exist() -> None:
    result = limited_search(catalog=tiny_catalog(), requirements=(), max_results=0)

    assert result.candidates == ()
    assert result.total_count > 0
    assert result.truncated is True


def test_one_result_limit_returns_one_candidate_and_total_count() -> None:
    catalog = tiny_catalog()
    all_candidates = search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=(),
    )

    result = limited_search(catalog=catalog, requirements=(), max_results=1)

    assert result.candidates == all_candidates[:1]
    assert result.total_count == len(all_candidates)
    assert result.total_count > 1
    assert result.truncated is True


def test_limit_equal_to_total_count_returns_all_candidates() -> None:
    catalog = tiny_catalog()
    all_candidates = search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=(),
    )

    result = limited_search(
        catalog=catalog,
        requirements=(),
        max_results=len(all_candidates),
    )

    assert result.candidates == all_candidates
    assert result.total_count == len(all_candidates)
    assert result.truncated is False


def test_limit_larger_than_total_count_returns_all_candidates() -> None:
    catalog = tiny_catalog()
    all_candidates = search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=(),
    )

    result = limited_search(
        catalog=catalog,
        requirements=(),
        max_results=len(all_candidates) + 1,
    )

    assert result.candidates == all_candidates
    assert result.total_count == len(all_candidates)
    assert result.truncated is False


def test_limit_applies_after_requirement_filtering() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:critical-eye", 3),)
    all_candidates = search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=requirements,
    )

    result = limited_search(
        catalog=catalog,
        requirements=requirements,
        max_results=2,
    )

    assert result.candidates == all_candidates[:2]
    assert result.total_count == len(all_candidates)
    assert result.truncated is (len(all_candidates) > 2)


def test_returns_build_candidate_search_result() -> None:
    result = limited_search(catalog=tiny_catalog(), requirements=(), max_results=1)

    assert isinstance(result, BuildCandidateSearchResult)


def test_limited_search_requires_keyword_arguments() -> None:
    signature = inspect.signature(
        search_limited_catalog_build_candidates_by_skill_requirements,
    )

    assert signature.parameters["catalog"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["requirements"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["max_results"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        search_limited_catalog_build_candidates_by_skill_requirements(
            tiny_catalog(), (), 1
        )  # type: ignore[call-arg]


def test_limited_search_inputs_are_not_modified() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:attack-boost", 3),)
    original_catalog = catalog
    original_equipment = catalog.equipment
    original_decorations = catalog.decorations
    original_requirements = requirements

    limited_search(catalog=catalog, requirements=requirements, max_results=1)

    assert catalog == original_catalog
    assert catalog.equipment == original_equipment
    assert catalog.decorations == original_decorations
    assert requirements == original_requirements


def test_solver_package_exports_limited_search_and_keeps_existing_public_exports() -> (
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
        search_limited_catalog_build_candidates_by_skill_requirements as exported_limited,
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
    assert (
        exported_limited
        is search_limited_catalog_build_candidates_by_skill_requirements
    )
    assert exported_requirements is skill_levels_satisfy_requirements


@pytest.mark.parametrize("max_results", [True, 1.5, "1", None])
def test_rejects_invalid_max_results_types(max_results: object) -> None:
    with pytest.raises(TypeError, match="max_results"):
        search_limited_catalog_build_candidates_by_skill_requirements(
            catalog=empty_catalog(),
            requirements=(),
            max_results=max_results,  # type: ignore[arg-type]
        )


def test_rejects_negative_max_results() -> None:
    with pytest.raises(ValueError, match="max_results"):
        search_limited_catalog_build_candidates_by_skill_requirements(
            catalog=empty_catalog(),
            requirements=(),
            max_results=-1,
        )


def test_propagates_invalid_catalog_type_error() -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_limited_catalog_build_candidates_by_skill_requirements(
            catalog="catalog",  # type: ignore[arg-type]
            requirements=(),
            max_results=1,
        )


def test_propagates_requirement_list_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_limited_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=[requirement()],  # type: ignore[arg-type]
            max_results=1,
        )


def test_propagates_invalid_requirement_element_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_limited_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=("skill:attack-boost",),  # type: ignore[arg-type]
            max_results=1,
        )


def test_propagates_duplicate_requirement_skill_id_value_error() -> None:
    with pytest.raises(ValueError, match="requirements"):
        search_limited_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
            max_results=1,
        )


def test_total_count_is_before_limit_not_an_early_stop_count() -> None:
    catalog = tiny_catalog()
    all_candidates = search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=(requirement("skill:attack-boost", 3),),
    )

    result = limited_search(
        catalog=catalog,
        requirements=(requirement("skill:attack-boost", 3),),
        max_results=1,
    )

    assert result.total_count == len(all_candidates)
    assert result.total_count > len(result.candidates)


def test_manual_catalog_deterministically_returns_same_result() -> None:
    catalog = manual_catalog()
    requirements = (requirement("skill:attack-boost", 1),)

    first = limited_search(
        catalog=catalog,
        requirements=requirements,
        max_results=1,
    )
    second = limited_search(
        catalog=catalog,
        requirements=requirements,
        max_results=1,
    )

    assert first == second


def test_search_adds_no_request_or_solver_result_public_types() -> None:
    import mhwilds_skill_sim.solver as solver
    import mhwilds_skill_sim.solver.search_result as search_result_module

    for name in ("SearchRequest", "SolverResult", "BuildResult"):
        assert not hasattr(solver, name)
        assert not hasattr(search_result_module, name)
