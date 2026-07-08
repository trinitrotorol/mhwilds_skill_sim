from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.validation.placement import DecorationPlacement


def placement(
    *,
    equipment_id: str = "fixture:weapon:training-blade",
    slot_index: int = 0,
    decoration_id: str = "fixture:decoration:armor-power-1",
) -> DecorationPlacement:
    return DecorationPlacement(
        equipment_id=equipment_id,
        slot_index=slot_index,
        decoration_id=decoration_id,
    )


def test_can_create_decoration_placement_with_valid_values() -> None:
    definition = DecorationPlacement(
        equipment_id="weapon:great-sword:hope-blade",
        slot_index=2,
        decoration_id="decoration:venom-jewel-1",
    )

    assert definition.equipment_id == "weapon:great-sword:hope-blade"
    assert definition.slot_index == 2
    assert definition.decoration_id == "decoration:venom-jewel-1"


@pytest.mark.parametrize(
    "equipment_id",
    [
        "fixture:weapon:training-blade",
        "weapon:great-sword:hope-blade",
        "armor:head:hope-mask",
        "charm:challenger-1",
        "Equipment:Internal_ID-01",
    ],
)
def test_preserves_equipment_id_without_normalization(equipment_id: str) -> None:
    definition = placement(equipment_id=equipment_id)

    assert definition.equipment_id == equipment_id


@pytest.mark.parametrize(
    "decoration_id",
    [
        "fixture:decoration:armor-power-1",
        "decoration:venom-jewel-1",
        "wilds:decoration:-2144349312",
        "Decoration:Internal_ID-01",
    ],
)
def test_preserves_decoration_id_without_normalization(decoration_id: str) -> None:
    definition = placement(decoration_id=decoration_id)

    assert definition.decoration_id == decoration_id


def test_accepts_slot_index_zero() -> None:
    definition = placement(slot_index=0)

    assert definition.slot_index == 0


def test_accepts_large_positive_slot_index() -> None:
    definition = placement(slot_index=999)

    assert definition.slot_index == 999


def test_decoration_placements_with_same_values_are_equal() -> None:
    assert placement() == placement()


@pytest.mark.parametrize(
    "other",
    [
        placement(equipment_id="armor:head:hope-mask"),
        placement(slot_index=1),
        placement(decoration_id="decoration:venom-jewel-1"),
    ],
)
def test_decoration_placements_with_different_values_are_not_equal(
    other: DecorationPlacement,
) -> None:
    assert placement() != other


def test_decoration_placement_is_hashable() -> None:
    assert hash(placement()) == hash(placement())


def test_decoration_placement_fields_cannot_be_reassigned() -> None:
    definition = placement()

    with pytest.raises(FrozenInstanceError):
        definition.slot_index = 1


def test_validation_package_exports_decoration_placement() -> None:
    from mhwilds_skill_sim.validation import (
        DecorationPlacement as ExportedDecorationPlacement,
    )

    assert ExportedDecorationPlacement is DecorationPlacement


def test_validation_package_keeps_existing_public_export() -> None:
    from mhwilds_skill_sim.validation import can_place_decoration_in_equipment_slot
    from mhwilds_skill_sim.validation.decoration import (
        can_place_decoration_in_equipment_slot as decoration_validator,
    )

    assert can_place_decoration_in_equipment_slot is decoration_validator


@pytest.mark.parametrize("equipment_id", ["", " ", "\t\n"])
def test_rejects_empty_or_blank_equipment_id(equipment_id: str) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        placement(equipment_id=equipment_id)


@pytest.mark.parametrize(
    "equipment_id",
    [" fixture:weapon:training-blade", "\tfixture:weapon:training-blade"],
)
def test_rejects_equipment_id_with_leading_whitespace(equipment_id: str) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        placement(equipment_id=equipment_id)


@pytest.mark.parametrize(
    "equipment_id",
    ["fixture:weapon:training-blade ", "fixture:weapon:training-blade\n"],
)
def test_rejects_equipment_id_with_trailing_whitespace(equipment_id: str) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        placement(equipment_id=equipment_id)


@pytest.mark.parametrize("equipment_id", [1, None])
def test_rejects_non_str_equipment_id(equipment_id: object) -> None:
    with pytest.raises(TypeError, match="equipment_id"):
        DecorationPlacement(
            equipment_id=equipment_id,  # type: ignore[arg-type]
            slot_index=0,
            decoration_id="fixture:decoration:armor-power-1",
        )


@pytest.mark.parametrize("slot_index", [-1, -99])
def test_rejects_negative_slot_index(slot_index: int) -> None:
    with pytest.raises(ValueError, match="slot_index"):
        placement(slot_index=slot_index)


@pytest.mark.parametrize("slot_index", [True, 1.0, "0", None])
def test_rejects_non_int_slot_index(slot_index: object) -> None:
    with pytest.raises(TypeError, match="slot_index"):
        DecorationPlacement(
            equipment_id="fixture:weapon:training-blade",
            slot_index=slot_index,  # type: ignore[arg-type]
            decoration_id="fixture:decoration:armor-power-1",
        )


@pytest.mark.parametrize("decoration_id", ["", " ", "\t\n"])
def test_rejects_empty_or_blank_decoration_id(decoration_id: str) -> None:
    with pytest.raises(ValueError, match="decoration_id"):
        placement(decoration_id=decoration_id)


@pytest.mark.parametrize(
    "decoration_id",
    [" fixture:decoration:armor-power-1", "\tfixture:decoration:armor-power-1"],
)
def test_rejects_decoration_id_with_leading_whitespace(decoration_id: str) -> None:
    with pytest.raises(ValueError, match="decoration_id"):
        placement(decoration_id=decoration_id)


@pytest.mark.parametrize(
    "decoration_id",
    ["fixture:decoration:armor-power-1 ", "fixture:decoration:armor-power-1\n"],
)
def test_rejects_decoration_id_with_trailing_whitespace(decoration_id: str) -> None:
    with pytest.raises(ValueError, match="decoration_id"):
        placement(decoration_id=decoration_id)


@pytest.mark.parametrize("decoration_id", [1, None])
def test_rejects_non_str_decoration_id(decoration_id: object) -> None:
    with pytest.raises(TypeError, match="decoration_id"):
        DecorationPlacement(
            equipment_id="fixture:weapon:training-blade",
            slot_index=0,
            decoration_id=decoration_id,  # type: ignore[arg-type]
        )
