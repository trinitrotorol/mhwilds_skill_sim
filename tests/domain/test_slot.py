from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain import DecorationKind, DecorationSlot


def test_decoration_kind_values_match_public_contract() -> None:
    assert DecorationKind.WEAPON.value == "weapon"
    assert DecorationKind.ARMOR.value == "armor"


def test_can_create_weapon_decoration_slot() -> None:
    slot = DecorationSlot(kind=DecorationKind.WEAPON, level=1)

    assert slot.kind is DecorationKind.WEAPON
    assert slot.level == 1


def test_can_create_armor_decoration_slot() -> None:
    slot = DecorationSlot(kind=DecorationKind.ARMOR, level=2)

    assert slot.kind is DecorationKind.ARMOR
    assert slot.level == 2


def test_decoration_slots_with_same_values_are_equal() -> None:
    assert DecorationSlot(DecorationKind.WEAPON, 3) == DecorationSlot(
        DecorationKind.WEAPON,
        3,
    )


def test_decoration_slot_is_hashable() -> None:
    slot = DecorationSlot(DecorationKind.ARMOR, 1)

    assert hash(slot) == hash(DecorationSlot(DecorationKind.ARMOR, 1))


def test_decoration_slot_fields_cannot_be_reassigned() -> None:
    slot = DecorationSlot(DecorationKind.WEAPON, 1)

    with pytest.raises(FrozenInstanceError):
        slot.level = 2


def test_decoration_slot_rejects_raw_string_kind() -> None:
    with pytest.raises(TypeError):
        DecorationSlot(kind="weapon", level=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [0, -1])
def test_decoration_slot_rejects_non_positive_levels(level: int) -> None:
    with pytest.raises(ValueError):
        DecorationSlot(kind=DecorationKind.ARMOR, level=level)


def test_decoration_slot_rejects_bool_level() -> None:
    with pytest.raises(TypeError):
        DecorationSlot(kind=DecorationKind.WEAPON, level=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [1.5, "1", None])
def test_decoration_slot_rejects_non_int_levels(level: object) -> None:
    with pytest.raises(TypeError):
        DecorationSlot(kind=DecorationKind.WEAPON, level=level)  # type: ignore[arg-type]


def test_decoration_slot_accepts_level_four_without_upper_bound() -> None:
    slot = DecorationSlot(kind=DecorationKind.ARMOR, level=4)

    assert slot.level == 4


def test_domain_package_exports_public_slot_types() -> None:
    from mhwilds_skill_sim.domain import (
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
    )

    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
