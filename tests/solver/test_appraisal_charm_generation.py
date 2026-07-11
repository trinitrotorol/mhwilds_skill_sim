from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

import mhwilds_skill_sim.solver as solver
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.appraisal_charms import (
    generate_appraisal_charm_equipment_candidates,
)


def contribution(
    skill_id: str = "skill:attack-boost",
    level: int = 1,
) -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=level)


def skill_definition(
    skill_id: str = "skill:attack-boost",
    *,
    kind: SkillKind = SkillKind.ARMOR,
    maximum_level: int = 3,
) -> SkillDefinition:
    required_pieces = None if kind in (SkillKind.ARMOR, SkillKind.WEAPON) else 1
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(
                level=level,
                required_pieces=(
                    required_pieces * level if required_pieces is not None else None
                ),
            )
            for level in range(1, maximum_level + 1)
        ),
    )


def skill_group(
    group_id: str = "appraisal-group:A",
    skills: tuple[SkillContribution, ...] | None = None,
) -> AppraisalCharmSkillGroupDefinition:
    return AppraisalCharmSkillGroupDefinition(
        group_id=group_id,
        skills=skills if skills is not None else (contribution(),),
    )


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=DecorationKind.ARMOR, level=level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=DecorationKind.WEAPON, level=level)


def pattern(
    pattern_id: str = "appraisal-pattern:r8-a",
    *,
    rarity: int = 8,
    skill_group_ids: tuple[str, ...] = ("appraisal-group:A",),
    slots: tuple[DecorationSlot, ...] = (),
) -> AppraisalCharmPatternDefinition:
    return AppraisalCharmPatternDefinition(
        pattern_id=pattern_id,
        rarity=rarity,
        skill_group_ids=skill_group_ids,
        slots=slots,
    )


def generate(
    *,
    skill_groups: tuple[AppraisalCharmSkillGroupDefinition, ...] | None = None,
    patterns: tuple[AppraisalCharmPatternDefinition, ...] | None = None,
    skill_definitions: tuple[SkillDefinition, ...] | None = None,
) -> tuple[EquipmentDefinition, ...]:
    return generate_appraisal_charm_equipment_candidates(
        skill_groups=(skill_group(),) if skill_groups is None else skill_groups,
        patterns=(pattern(),) if patterns is None else patterns,
        skill_definitions=(
            (skill_definition(),) if skill_definitions is None else skill_definitions
        ),
    )


def group_generator() -> Iterator[AppraisalCharmSkillGroupDefinition]:
    yield skill_group()


def pattern_generator() -> Iterator[AppraisalCharmPatternDefinition]:
    yield pattern()


def definition_generator() -> Iterator[SkillDefinition]:
    yield skill_definition()


def test_empty_inputs_return_empty_exact_tuple() -> None:
    generated = generate_appraisal_charm_equipment_candidates(
        skill_groups=(),
        patterns=(),
        skill_definitions=(),
    )

    assert generated == ()
    assert type(generated) is tuple


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("skill_groups", [skill_group()]),
        ("skill_groups", {skill_group()}),
        ("skill_groups", group_generator()),
        ("skill_groups", None),
        ("patterns", [pattern()]),
        ("patterns", {pattern()}),
        ("patterns", pattern_generator()),
        ("patterns", None),
        ("skill_definitions", [skill_definition()]),
        ("skill_definitions", {skill_definition()}),
        ("skill_definitions", definition_generator()),
        ("skill_definitions", None),
    ],
)
def test_rejects_non_tuple_arguments(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "skill_groups": (skill_group(),),
        "patterns": (pattern(),),
        "skill_definitions": (skill_definition(),),
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError, match=field_name):
        generate_appraisal_charm_equipment_candidates(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    ["skill_groups", "patterns", "skill_definitions"],
)
def test_rejects_tuple_subclass_arguments(field_name: str) -> None:
    class DefinitionTuple(tuple[object, ...]):
        pass

    values: dict[str, object] = {
        "skill_groups": (skill_group(),),
        "patterns": (pattern(),),
        "skill_definitions": (skill_definition(),),
    }
    values[field_name] = DefinitionTuple(values[field_name])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=field_name):
        generate_appraisal_charm_equipment_candidates(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("skill_groups", "group"),
        ("patterns", "pattern"),
        ("skill_definitions", "skill"),
    ],
)
def test_rejects_invalid_argument_elements(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "skill_groups": (skill_group(),),
        "patterns": (pattern(),),
        "skill_definitions": (skill_definition(),),
    }
    values[field_name] = (invalid_value,)

    with pytest.raises(TypeError, match=field_name):
        generate_appraisal_charm_equipment_candidates(**values)  # type: ignore[arg-type]


def test_rejects_duplicate_group_ids() -> None:
    with pytest.raises(ValueError, match="skill_groups"):
        generate_appraisal_charm_equipment_candidates(
            skill_groups=(skill_group(), skill_group()),
            patterns=(),
            skill_definitions=(skill_definition(),),
        )


def test_rejects_duplicate_pattern_ids() -> None:
    with pytest.raises(ValueError, match="patterns"):
        generate(
            patterns=(pattern(), pattern()),
        )


def test_rejects_duplicate_skill_definition_ids() -> None:
    with pytest.raises(ValueError, match="skill_definitions"):
        generate(
            skill_definitions=(
                skill_definition(),
                skill_definition(kind=SkillKind.WEAPON),
            ),
        )


def test_rejects_missing_group_skill_reference() -> None:
    with pytest.raises(ValueError) as exc_info:
        generate(skill_definitions=())

    assert "skill_groups" in str(exc_info.value)
    assert "skill_definitions" in str(exc_info.value)
    assert "existing" in str(exc_info.value)


@pytest.mark.parametrize("kind", [SkillKind.SERIES, SkillKind.GROUP])
def test_rejects_bonus_skill_group_options(kind: SkillKind) -> None:
    with pytest.raises(ValueError) as exc_info:
        generate(skill_definitions=(skill_definition(kind=kind),))

    assert "skill_groups" in str(exc_info.value)
    assert "armor or weapon" in str(exc_info.value)


def test_rejects_group_contribution_above_maximum_rank() -> None:
    with pytest.raises(ValueError) as exc_info:
        generate(
            skill_groups=(skill_group(skills=(contribution(level=2),)),),
            skill_definitions=(skill_definition(maximum_level=1),),
        )

    assert "skill_groups" in str(exc_info.value)
    assert "skill_definitions" in str(exc_info.value)
    assert "maximum" in str(exc_info.value)


def test_rejects_missing_pattern_group_reference() -> None:
    with pytest.raises(ValueError) as exc_info:
        generate(
            patterns=(pattern(skill_group_ids=("appraisal-group:missing",)),),
        )

    assert "patterns" in str(exc_info.value)
    assert "skill_group_ids" in str(exc_info.value)


def test_repeated_pattern_group_references_are_accepted() -> None:
    generated = generate(
        patterns=(
            pattern(
                skill_group_ids=("appraisal-group:A", "appraisal-group:A"),
            ),
        ),
    )

    assert len(generated) == 1
    assert generated[0].skills == (contribution(level=2),)


def test_one_group_one_option_generates_expected_charm() -> None:
    slots = (weapon_slot(1), armor_slot(2))

    generated = generate(
        patterns=(pattern(slots=slots),),
    )

    assert generated == (
        EquipmentDefinition(
            equipment_id=(
                "generated:appraisal-charm:rarity-8:"
                "appraisal-pattern:r8-a:combination-1"
            ),
            part=EquipmentPart.CHARM,
            skills=(contribution(),),
            slots=slots,
            series_skill_id=None,
            group_skill_id=None,
            allows_series_skill_assignment=False,
            allows_group_skill_assignment=False,
        ),
    )


def test_one_group_multiple_options_preserves_option_order() -> None:
    groups = (
        skill_group(
            skills=(
                contribution("skill:critical-eye"),
                contribution("skill:attack-boost", 2),
            )
        ),
    )
    definitions = (
        skill_definition("skill:attack-boost"),
        skill_definition("skill:critical-eye"),
    )

    generated = generate(
        skill_groups=groups,
        skill_definitions=definitions,
    )

    assert [charm.skills for charm in generated] == [
        (contribution("skill:critical-eye"),),
        (contribution("skill:attack-boost", 2),),
    ]


def test_two_group_cartesian_product_has_exact_deterministic_order() -> None:
    groups = (
        skill_group(
            "appraisal-group:A",
            (
                contribution("skill:attack-boost"),
                contribution("skill:critical-eye"),
            ),
        ),
        skill_group(
            "appraisal-group:B",
            (
                contribution("skill:weakness-exploit"),
                contribution("skill:weapon-technique"),
            ),
        ),
    )
    definitions = tuple(
        skill_definition(
            skill_id,
            kind=(
                SkillKind.WEAPON
                if skill_id == "skill:weapon-technique"
                else SkillKind.ARMOR
            ),
        )
        for skill_id in (
            "skill:attack-boost",
            "skill:critical-eye",
            "skill:weakness-exploit",
            "skill:weapon-technique",
        )
    )

    generated = generate(
        skill_groups=groups,
        patterns=(
            pattern(
                skill_group_ids=("appraisal-group:A", "appraisal-group:B"),
            ),
        ),
        skill_definitions=definitions,
    )

    assert [charm.skills for charm in generated] == [
        (
            contribution("skill:attack-boost"),
            contribution("skill:weakness-exploit"),
        ),
        (
            contribution("skill:attack-boost"),
            contribution("skill:weapon-technique"),
        ),
        (
            contribution("skill:critical-eye"),
            contribution("skill:weakness-exploit"),
        ),
        (
            contribution("skill:critical-eye"),
            contribution("skill:weapon-technique"),
        ),
    ]
    assert [charm.equipment_id.rsplit("-", 1)[-1] for charm in generated] == [
        "1",
        "2",
        "3",
        "4",
    ]


def test_three_group_product_uses_last_position_as_fast_dimension() -> None:
    groups = tuple(
        skill_group(
            f"appraisal-group:{group_name}",
            (
                contribution(f"skill:{group_name.lower()}1"),
                contribution(f"skill:{group_name.lower()}2"),
            ),
        )
        for group_name in ("A", "B", "C")
    )
    definitions = tuple(
        skill_definition(f"skill:{group_name.lower()}{option}")
        for group_name in ("A", "B", "C")
        for option in (1, 2)
    )

    generated = generate(
        skill_groups=groups,
        patterns=(
            pattern(
                skill_group_ids=(
                    "appraisal-group:A",
                    "appraisal-group:B",
                    "appraisal-group:C",
                ),
            ),
        ),
        skill_definitions=definitions,
    )

    assert len(generated) == 8
    assert [tuple(skill.skill_id for skill in charm.skills) for charm in generated] == [
        ("skill:a1", "skill:b1", "skill:c1"),
        ("skill:a1", "skill:b1", "skill:c2"),
        ("skill:a1", "skill:b2", "skill:c1"),
        ("skill:a1", "skill:b2", "skill:c2"),
        ("skill:a2", "skill:b1", "skill:c1"),
        ("skill:a2", "skill:b1", "skill:c2"),
        ("skill:a2", "skill:b2", "skill:c1"),
        ("skill:a2", "skill:b2", "skill:c2"),
    ]


def test_repeated_group_positions_choose_independently_before_deduplication() -> None:
    groups = (
        skill_group(
            skills=(
                contribution("skill:attack-boost"),
                contribution("skill:critical-eye"),
            )
        ),
    )
    definitions = (
        skill_definition("skill:attack-boost", maximum_level=2),
        skill_definition("skill:critical-eye", maximum_level=2),
    )

    generated = generate(
        skill_groups=groups,
        patterns=(
            pattern(
                skill_group_ids=("appraisal-group:A", "appraisal-group:A"),
            ),
        ),
        skill_definitions=definitions,
    )

    assert [charm.skills for charm in generated] == [
        (contribution("skill:attack-boost", 2),),
        (
            contribution("skill:attack-boost"),
            contribution("skill:critical-eye"),
        ),
        (contribution("skill:critical-eye", 2),),
    ]
    assert [charm.equipment_id.rsplit("-", 1)[-1] for charm in generated] == [
        "1",
        "2",
        "4",
    ]


def test_repeated_selected_skills_are_summed_in_first_occurrence_order() -> None:
    groups = (
        skill_group(
            "appraisal-group:B",
            (contribution("skill:attack-boost", 2),),
        ),
        skill_group(
            "appraisal-group:A",
            (contribution("skill:attack-boost", 1),),
        ),
        skill_group(
            "appraisal-group:J",
            (contribution("skill:weakness-exploit", 1),),
        ),
    )

    generated = generate(
        skill_groups=groups,
        patterns=(
            pattern(
                skill_group_ids=(
                    "appraisal-group:B",
                    "appraisal-group:A",
                    "appraisal-group:J",
                )
            ),
        ),
        skill_definitions=(
            skill_definition("skill:weakness-exploit"),
            skill_definition("skill:attack-boost", maximum_level=3),
        ),
    )

    assert generated[0].skills == (
        contribution("skill:attack-boost", 3),
        contribution("skill:weakness-exploit", 1),
    )


def test_rejects_aggregated_selected_level_above_maximum_rank() -> None:
    groups = (skill_group(skills=(contribution("skill:attack-boost", 2),)),)

    with pytest.raises(ValueError) as exc_info:
        generate(
            skill_groups=groups,
            patterns=(
                pattern(
                    skill_group_ids=("appraisal-group:A", "appraisal-group:A"),
                ),
            ),
            skill_definitions=(
                skill_definition("skill:attack-boost", maximum_level=3),
            ),
        )

    assert "skill_groups" in str(exc_info.value)
    assert "skill_definitions" in str(exc_info.value)
    assert "maximum" in str(exc_info.value)


def test_generated_values_slots_flags_and_ids_match_contract() -> None:
    slots = (weapon_slot(3), armor_slot(2), armor_slot(1))
    generated = generate(
        patterns=(
            pattern(
                pattern_id="fixture:pattern:Case-Sensitive",
                rarity=999,
                slots=slots,
            ),
        ),
    )
    charm = generated[0]

    assert charm.equipment_id == (
        "generated:appraisal-charm:rarity-999:"
        "fixture:pattern:Case-Sensitive:combination-1"
    )
    assert charm.part is EquipmentPart.CHARM
    assert charm.slots == slots
    assert charm.series_skill_id is None
    assert charm.group_skill_id is None
    assert charm.allows_series_skill_assignment is False
    assert charm.allows_group_skill_assignment is False


def test_generated_ids_are_unique_across_patterns_and_combinations() -> None:
    groups = (
        skill_group(
            skills=(
                contribution("skill:attack-boost"),
                contribution("skill:critical-eye"),
            )
        ),
    )
    patterns = (
        pattern("pattern:first", slots=(armor_slot(1),)),
        pattern("pattern:second", slots=(armor_slot(2),)),
    )

    generated = generate(
        skill_groups=groups,
        patterns=patterns,
        skill_definitions=(
            skill_definition("skill:attack-boost"),
            skill_definition("skill:critical-eye"),
        ),
    )

    ids = [charm.equipment_id for charm in generated]
    assert len(ids) == len(set(ids)) == 4


def test_generated_equipment_is_hashable_and_frozen() -> None:
    charm = generate()[0]

    assert {charm, charm} == {charm}
    with pytest.raises(FrozenInstanceError):
        charm.equipment_id = "changed"


def test_inputs_are_not_mutated() -> None:
    groups = (skill_group(),)
    patterns = (pattern(),)
    definitions = (skill_definition(),)
    before = (groups, patterns, definitions)

    generate_appraisal_charm_equipment_candidates(
        skill_groups=groups,
        patterns=patterns,
        skill_definitions=definitions,
    )

    assert (groups, patterns, definitions) == before


def test_returns_new_outer_tuple_on_each_nonempty_call() -> None:
    first = generate()
    second = generate()

    assert first == second
    assert first is not second


def test_selection_orders_with_equal_totals_and_slots_deduplicate() -> None:
    groups = (
        skill_group(
            "appraisal-group:A",
            (
                contribution("skill:attack-boost"),
                contribution("skill:weakness-exploit"),
            ),
        ),
        skill_group(
            "appraisal-group:B",
            (
                contribution("skill:weakness-exploit"),
                contribution("skill:attack-boost"),
            ),
        ),
    )

    generated = generate(
        skill_groups=groups,
        patterns=(
            pattern(
                skill_group_ids=("appraisal-group:A", "appraisal-group:B"),
                slots=(armor_slot(1),),
            ),
        ),
        skill_definitions=(
            skill_definition("skill:attack-boost", maximum_level=2),
            skill_definition("skill:weakness-exploit", maximum_level=2),
        ),
    )

    assert len(generated) == 3
    assert generated[0].equipment_id.endswith("combination-1")
    assert generated[0].skills == (
        contribution("skill:attack-boost"),
        contribution("skill:weakness-exploit"),
    )


def test_equivalent_charms_from_different_patterns_keep_first_occurrence() -> None:
    groups = (
        skill_group("appraisal-group:A", (contribution("skill:attack-boost"),)),
        skill_group(
            "appraisal-group:J",
            (contribution("skill:weakness-exploit"),),
        ),
    )
    patterns = (
        pattern(
            "pattern:first",
            skill_group_ids=("appraisal-group:A", "appraisal-group:J"),
            slots=(armor_slot(1),),
        ),
        pattern(
            "pattern:second",
            rarity=7,
            skill_group_ids=("appraisal-group:J", "appraisal-group:A"),
            slots=(armor_slot(1),),
        ),
    )

    generated = generate(
        skill_groups=groups,
        patterns=patterns,
        skill_definitions=(
            skill_definition("skill:attack-boost"),
            skill_definition("skill:weakness-exploit"),
        ),
    )

    assert len(generated) == 1
    assert "pattern:first" in generated[0].equipment_id
    assert generated[0].skills == (
        contribution("skill:attack-boost"),
        contribution("skill:weakness-exploit"),
    )


def test_different_slot_layouts_do_not_deduplicate() -> None:
    generated = generate(
        patterns=(
            pattern("pattern:first", slots=(armor_slot(1),)),
            pattern("pattern:second", slots=(armor_slot(2),)),
        )
    )

    assert len(generated) == 2
    assert generated[0].slots != generated[1].slots


def test_different_skill_totals_do_not_deduplicate() -> None:
    groups = (
        skill_group(
            "appraisal-group:A",
            (contribution("skill:attack-boost", 1),),
        ),
        skill_group(
            "appraisal-group:B",
            (contribution("skill:attack-boost", 2),),
        ),
    )

    generated = generate(
        skill_groups=groups,
        patterns=(
            pattern(
                "pattern:first",
                skill_group_ids=("appraisal-group:A",),
            ),
            pattern(
                "pattern:second",
                skill_group_ids=("appraisal-group:B",),
            ),
        ),
        skill_definitions=(skill_definition(maximum_level=2),),
    )

    assert [charm.skills for charm in generated] == [
        (contribution("skill:attack-boost", 1),),
        (contribution("skill:attack-boost", 2),),
    ]


def test_generator_arguments_are_keyword_only() -> None:
    signature = inspect.signature(generate_appraisal_charm_equipment_candidates)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        generate_appraisal_charm_equipment_candidates((), (), ())  # type: ignore[call-arg]


def test_solver_package_exports_generator_in_required_order() -> None:
    from mhwilds_skill_sim.solver import (
        generate_appraisal_charm_equipment_candidates as exported_generator,
    )

    assert exported_generator is generate_appraisal_charm_equipment_candidates
    assert solver.__all__ == [
        "BuildCandidate",
        "BuildCandidateSearchResult",
        "SkillRequirement",
        "enumerate_build_candidates",
        "enumerate_decoration_placement_combinations",
        "enumerate_equipment_selections",
        "expand_equipment_bonus_skill_variants",
        "filter_build_candidates_by_skill_requirements",
        "generate_appraisal_charm_equipment_candidates",
        "search_catalog_build_candidates_by_skill_requirements",
        "search_build_candidates_by_skill_requirements",
        "search_limited_catalog_build_candidates_by_skill_requirements",
        "skill_levels_satisfy_requirements",
    ]


def test_existing_solver_exports_remain_available() -> None:
    for name in (
        "BuildCandidate",
        "BuildCandidateSearchResult",
        "SkillRequirement",
        "enumerate_build_candidates",
        "enumerate_decoration_placement_combinations",
        "enumerate_equipment_selections",
        "expand_equipment_bonus_skill_variants",
        "filter_build_candidates_by_skill_requirements",
        "search_catalog_build_candidates_by_skill_requirements",
        "search_build_candidates_by_skill_requirements",
        "search_limited_catalog_build_candidates_by_skill_requirements",
        "skill_levels_satisfy_requirements",
    ):
        assert hasattr(solver, name)
