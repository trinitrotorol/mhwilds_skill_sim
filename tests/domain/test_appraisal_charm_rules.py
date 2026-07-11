from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import mhwilds_skill_sim.domain as domain
from mhwilds_skill_sim.domain import (
    AppraisalCharmPatternDefinition as ExportedAppraisalCharmPatternDefinition,
)
from mhwilds_skill_sim.domain import (
    AppraisalCharmSkillGroupDefinition as ExportedAppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot


def contribution(
    skill_id: str = "skill:attack-boost",
    level: int = 1,
) -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=DecorationKind.WEAPON, level=level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=DecorationKind.ARMOR, level=level)


def skill_group(
    group_id: str = "appraisal-group:A",
    skills: tuple[SkillContribution, ...] | None = None,
) -> AppraisalCharmSkillGroupDefinition:
    return AppraisalCharmSkillGroupDefinition(
        group_id=group_id,
        skills=skills if skills is not None else (contribution(),),
    )


def pattern(
    pattern_id: str = "appraisal-pattern:r8-a-b",
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


def test_skill_group_accepts_valid_ordered_skills() -> None:
    skills = (
        contribution("skill:critical-eye", 1),
        contribution("skill:attack-boost", 2),
    )

    created = skill_group(group_id="appraisal-group:B", skills=skills)

    assert created.group_id == "appraisal-group:B"
    assert created.skills == skills
    assert created.skills[0].skill_id == "skill:critical-eye"


def test_skill_group_supports_positional_dataclass_construction() -> None:
    created = AppraisalCharmSkillGroupDefinition(
        "appraisal-group:A",
        (contribution(),),
    )

    assert created == skill_group()


def test_skill_group_equality_hashing_and_frozen_behavior() -> None:
    created = skill_group()

    assert created == skill_group()
    assert hash(created) == hash(skill_group())
    assert created != skill_group(group_id="appraisal-group:B")
    with pytest.raises(FrozenInstanceError):
        created.group_id = "appraisal-group:B"


@pytest.mark.parametrize(
    ("group_id", "expected_exception"),
    [
        (None, TypeError),
        (1, TypeError),
        (True, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" appraisal-group:A", ValueError),
        ("appraisal-group:A ", ValueError),
    ],
)
def test_skill_group_rejects_invalid_group_id(
    group_id: object,
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception, match="group_id"):
        AppraisalCharmSkillGroupDefinition(
            group_id=group_id,  # type: ignore[arg-type]
            skills=(contribution(),),
        )


def test_skill_group_rejects_group_id_string_subclass() -> None:
    class GroupId(str):
        pass

    with pytest.raises(TypeError, match="group_id"):
        skill_group(group_id=GroupId("appraisal-group:A"))


def skill_generator():
    yield contribution()


@pytest.mark.parametrize(
    "skills",
    [
        [contribution()],
        {contribution()},
        skill_generator(),
        None,
    ],
)
def test_skill_group_rejects_non_tuple_skills(skills: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        AppraisalCharmSkillGroupDefinition(
            group_id="appraisal-group:A",
            skills=skills,  # type: ignore[arg-type]
        )


def test_skill_group_rejects_skills_tuple_subclass() -> None:
    class SkillTuple(tuple[SkillContribution, ...]):
        pass

    with pytest.raises(TypeError, match="skills"):
        skill_group(skills=SkillTuple((contribution(),)))


def test_skill_group_rejects_empty_skills() -> None:
    with pytest.raises(ValueError, match="skills"):
        skill_group(skills=())


@pytest.mark.parametrize("invalid_skill", [None, "skill", 1])
def test_skill_group_rejects_invalid_skill_items(invalid_skill: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        skill_group(skills=(invalid_skill,))  # type: ignore[arg-type]


def test_skill_group_rejects_duplicate_skill_ids() -> None:
    with pytest.raises(ValueError, match="skills"):
        skill_group(
            skills=(
                contribution("skill:attack-boost", 1),
                contribution("skill:attack-boost", 2),
            )
        )


def test_skill_group_does_not_perform_catalog_lookup_or_rank_validation() -> None:
    unknown = contribution("skill:not-in-a-catalog", 999)

    created = skill_group(skills=(unknown,))

    assert created.skills == (unknown,)


def test_pattern_accepts_two_and_three_skill_group_sequences() -> None:
    two_groups = ("appraisal-group:A", "appraisal-group:J")
    three_groups = (
        "appraisal-group:B",
        "appraisal-group:A",
        "appraisal-group:J",
    )

    assert pattern(skill_group_ids=two_groups).skill_group_ids == two_groups
    assert pattern(skill_group_ids=three_groups).skill_group_ids == three_groups


def test_pattern_accepts_and_preserves_repeated_group_ids() -> None:
    group_ids = (
        "appraisal-group:A",
        "appraisal-group:A",
        "appraisal-group:J",
    )

    assert pattern(skill_group_ids=group_ids).skill_group_ids == group_ids


def test_pattern_accepts_any_positive_rarity() -> None:
    assert pattern(rarity=1).rarity == 1
    assert pattern(rarity=999).rarity == 999


@pytest.mark.parametrize("rarity", [True, False, 1.5, "8", None])
def test_pattern_rejects_non_exact_int_rarity(rarity: object) -> None:
    with pytest.raises(TypeError, match="rarity"):
        pattern(rarity=rarity)  # type: ignore[arg-type]


@pytest.mark.parametrize("rarity", [0, -1])
def test_pattern_rejects_non_positive_rarity(rarity: int) -> None:
    with pytest.raises(ValueError, match="rarity"):
        pattern(rarity=rarity)


def group_id_generator():
    yield "appraisal-group:A"


@pytest.mark.parametrize(
    "skill_group_ids",
    [
        ["appraisal-group:A"],
        {"appraisal-group:A"},
        group_id_generator(),
        None,
    ],
)
def test_pattern_rejects_non_tuple_skill_group_ids(skill_group_ids: object) -> None:
    with pytest.raises(TypeError, match="skill_group_ids"):
        pattern(skill_group_ids=skill_group_ids)  # type: ignore[arg-type]


def test_pattern_rejects_skill_group_ids_tuple_subclass() -> None:
    class GroupIdTuple(tuple[str, ...]):
        pass

    with pytest.raises(TypeError, match="skill_group_ids"):
        pattern(skill_group_ids=GroupIdTuple(("appraisal-group:A",)))


@pytest.mark.parametrize(
    "skill_group_ids",
    [
        (),
        (
            "appraisal-group:A",
            "appraisal-group:B",
            "appraisal-group:J",
            "appraisal-group:K",
        ),
    ],
)
def test_pattern_rejects_group_counts_outside_one_to_three(
    skill_group_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="skill_group_ids"):
        pattern(skill_group_ids=skill_group_ids)


@pytest.mark.parametrize(
    ("group_id", "expected_exception"),
    [
        (None, TypeError),
        (1, TypeError),
        (True, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" appraisal-group:A", ValueError),
        ("appraisal-group:A ", ValueError),
    ],
)
def test_pattern_rejects_invalid_group_id_values(
    group_id: object,
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception, match="skill_group_ids"):
        pattern(skill_group_ids=(group_id,))  # type: ignore[arg-type]


def test_pattern_rejects_group_id_string_subclass() -> None:
    class GroupId(str):
        pass

    with pytest.raises(TypeError, match="skill_group_ids"):
        pattern(skill_group_ids=(GroupId("appraisal-group:A"),))


def slot_generator():
    yield armor_slot()


@pytest.mark.parametrize(
    "slots",
    [
        [armor_slot()],
        {armor_slot()},
        slot_generator(),
        None,
    ],
)
def test_pattern_rejects_non_tuple_slots(slots: object) -> None:
    with pytest.raises(TypeError, match="slots"):
        pattern(slots=slots)  # type: ignore[arg-type]


def test_pattern_rejects_slots_tuple_subclass() -> None:
    class SlotTuple(tuple[DecorationSlot, ...]):
        pass

    with pytest.raises(TypeError, match="slots"):
        pattern(slots=SlotTuple((armor_slot(),)))


@pytest.mark.parametrize("invalid_slot", [None, "slot", 1])
def test_pattern_rejects_invalid_slot_items(invalid_slot: object) -> None:
    with pytest.raises(TypeError, match="slots"):
        pattern(slots=(invalid_slot,))  # type: ignore[arg-type]


def test_pattern_accepts_empty_slots() -> None:
    assert pattern(slots=()).slots == ()


def test_pattern_accepts_four_slots_with_weapon_first() -> None:
    slots = (weapon_slot(3), armor_slot(3), armor_slot(2), armor_slot(1))

    assert pattern(slots=slots).slots == slots


def test_pattern_accepts_duplicate_armor_slot_levels() -> None:
    slots = (armor_slot(1), armor_slot(1), armor_slot(1))

    assert pattern(slots=slots).slots == slots


def test_pattern_rejects_more_than_four_slots() -> None:
    slots = (
        weapon_slot(),
        armor_slot(1),
        armor_slot(1),
        armor_slot(1),
        armor_slot(1),
    )

    with pytest.raises(ValueError, match="slots"):
        pattern(slots=slots)


def test_pattern_rejects_two_weapon_slots() -> None:
    with pytest.raises(ValueError, match="slots"):
        pattern(slots=(weapon_slot(1), weapon_slot(2)))


def test_pattern_rejects_four_armor_slots() -> None:
    with pytest.raises(ValueError, match="slots"):
        pattern(slots=(armor_slot(1),) * 4)


def test_pattern_rejects_weapon_slot_after_armor_slot() -> None:
    with pytest.raises(ValueError, match="slots"):
        pattern(slots=(armor_slot(1), weapon_slot(1)))


@pytest.mark.parametrize(
    ("pattern_id", "expected_exception"),
    [
        (None, TypeError),
        (1, TypeError),
        (True, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" appraisal-pattern:A", ValueError),
        ("appraisal-pattern:A ", ValueError),
    ],
)
def test_pattern_rejects_invalid_pattern_id(
    pattern_id: object,
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception, match="pattern_id"):
        AppraisalCharmPatternDefinition(
            pattern_id=pattern_id,  # type: ignore[arg-type]
            rarity=8,
            skill_group_ids=("appraisal-group:A",),
            slots=(),
        )


def test_pattern_rejects_pattern_id_string_subclass() -> None:
    class PatternId(str):
        pass

    with pytest.raises(TypeError, match="pattern_id"):
        pattern(pattern_id=PatternId("appraisal-pattern:A"))


def test_pattern_equality_hashing_and_frozen_behavior() -> None:
    created = pattern(
        skill_group_ids=("appraisal-group:A", "appraisal-group:J"),
        slots=(weapon_slot(), armor_slot()),
    )

    assert created == pattern(
        skill_group_ids=("appraisal-group:A", "appraisal-group:J"),
        slots=(weapon_slot(), armor_slot()),
    )
    assert hash(created) == hash(
        pattern(
            skill_group_ids=("appraisal-group:A", "appraisal-group:J"),
            slots=(weapon_slot(), armor_slot()),
        )
    )
    assert created != pattern(pattern_id="appraisal-pattern:other")
    with pytest.raises(FrozenInstanceError):
        created.rarity = 7


def test_domain_package_exports_appraisal_types_first() -> None:
    assert ExportedAppraisalCharmPatternDefinition is AppraisalCharmPatternDefinition
    assert (
        ExportedAppraisalCharmSkillGroupDefinition is AppraisalCharmSkillGroupDefinition
    )
    assert domain.__all__ == [
        "AppraisalCharmPatternDefinition",
        "AppraisalCharmSkillGroupDefinition",
        "DecorationDefinition",
        "DecorationKind",
        "DecorationSlot",
        "EquipmentDefinition",
        "EquipmentPart",
        "SkillContribution",
        "SkillDefinition",
        "SkillKind",
        "SkillRankDefinition",
        "aggregate_skill_levels",
        "calculate_equipment_bonus_skill_contributions",
        "can_place_decoration",
    ]


def test_all_existing_domain_exports_remain_available() -> None:
    for name in (
        "DecorationDefinition",
        "DecorationKind",
        "DecorationSlot",
        "EquipmentDefinition",
        "EquipmentPart",
        "SkillContribution",
        "SkillDefinition",
        "SkillKind",
        "SkillRankDefinition",
        "aggregate_skill_levels",
        "calculate_equipment_bonus_skill_contributions",
        "can_place_decoration",
    ):
        assert hasattr(domain, name)
