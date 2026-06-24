from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain import (
    DecorationKind,
    DecorationSlot,
    SkillContribution,
    can_place_decoration,
)


def test_can_create_skill_contribution_with_valid_values() -> None:
    contribution = SkillContribution(skill_id="skill:attack-boost", level=1)

    assert contribution.skill_id == "skill:attack-boost"
    assert contribution.level == 1


@pytest.mark.parametrize(
    "skill_id",
    [
        "skill:attack-boost",
        "skill:critical-eye",
        "wilds:skill:123456",
        "Skill:Internal_ID-01",
    ],
)
def test_skill_contribution_preserves_skill_id_without_normalization(
    skill_id: str,
) -> None:
    contribution = SkillContribution(skill_id=skill_id, level=2)

    assert contribution.skill_id == skill_id


def test_skill_contributions_with_same_values_are_equal() -> None:
    assert SkillContribution("skill:attack-boost", 1) == SkillContribution(
        "skill:attack-boost",
        1,
    )


@pytest.mark.parametrize(
    "other",
    [
        SkillContribution("skill:critical-eye", 1),
        SkillContribution("skill:attack-boost", 2),
    ],
)
def test_skill_contributions_with_different_values_are_not_equal(
    other: SkillContribution,
) -> None:
    assert SkillContribution("skill:attack-boost", 1) != other


def test_skill_contribution_is_hashable() -> None:
    contribution = SkillContribution("skill:attack-boost", 1)

    assert hash(contribution) == hash(SkillContribution("skill:attack-boost", 1))


def test_skill_contribution_fields_cannot_be_reassigned() -> None:
    contribution = SkillContribution("skill:attack-boost", 1)

    with pytest.raises(FrozenInstanceError):
        contribution.level = 2


@pytest.mark.parametrize("skill_id", ["", " ", "\t\n"])
def test_skill_contribution_rejects_empty_or_blank_skill_id(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        SkillContribution(skill_id=skill_id, level=1)


@pytest.mark.parametrize("skill_id", [" skill:attack-boost", "\tskill:attack-boost"])
def test_skill_contribution_rejects_leading_whitespace_skill_id(
    skill_id: str,
) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        SkillContribution(skill_id=skill_id, level=1)


@pytest.mark.parametrize("skill_id", ["skill:attack-boost ", "skill:attack-boost\n"])
def test_skill_contribution_rejects_trailing_whitespace_skill_id(
    skill_id: str,
) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        SkillContribution(skill_id=skill_id, level=1)


@pytest.mark.parametrize("skill_id", [1, None])
def test_skill_contribution_rejects_non_str_skill_id(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_id"):
        SkillContribution(skill_id=skill_id, level=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [0, -1])
def test_skill_contribution_rejects_non_positive_levels(level: int) -> None:
    with pytest.raises(ValueError, match="level"):
        SkillContribution(skill_id="skill:attack-boost", level=level)


def test_skill_contribution_rejects_bool_level() -> None:
    with pytest.raises(TypeError, match="level"):
        SkillContribution(skill_id="skill:attack-boost", level=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [1.5, "1", None])
def test_skill_contribution_rejects_non_int_levels(level: object) -> None:
    with pytest.raises(TypeError, match="level"):
        SkillContribution(skill_id="skill:attack-boost", level=level)  # type: ignore[arg-type]


def test_skill_contribution_accepts_large_positive_level_without_upper_bound() -> None:
    contribution = SkillContribution(skill_id="skill:attack-boost", level=999)

    assert contribution.level == 999


def test_domain_package_exports_skill_contribution() -> None:
    from mhwilds_skill_sim.domain import SkillContribution as ExportedSkillContribution

    assert ExportedSkillContribution is SkillContribution


def test_domain_package_keeps_existing_slot_exports() -> None:
    from mhwilds_skill_sim.domain import (
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
        can_place_decoration as exported_can_place_decoration,
    )

    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
    assert exported_can_place_decoration is can_place_decoration
