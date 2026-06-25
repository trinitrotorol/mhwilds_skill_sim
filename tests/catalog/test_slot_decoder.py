from __future__ import annotations

import inspect

import pytest

from mhwilds_skill_sim.catalog.decoder import (
    decode_decoration_slot,
    decode_skill_contribution,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot


@pytest.mark.parametrize(
    ("kind", "level", "expected_kind"),
    [
        ("weapon", 1, DecorationKind.WEAPON),
        ("weapon", 2, DecorationKind.WEAPON),
        ("armor", 1, DecorationKind.ARMOR),
        ("armor", 4, DecorationKind.ARMOR),
    ],
)
def test_decode_decoration_slot_returns_decoration_slot(
    kind: str,
    level: int,
    expected_kind: DecorationKind,
) -> None:
    slot = decode_decoration_slot(value={"kind": kind, "level": level})

    assert isinstance(slot, DecorationSlot)
    assert slot.kind is expected_kind
    assert slot.level == level


def test_decode_decoration_slot_accepts_reverse_key_order() -> None:
    slot = decode_decoration_slot(value={"level": 2, "kind": "weapon"})

    assert slot == DecorationSlot(DecorationKind.WEAPON, 2)


def test_decode_decoration_slot_accepts_custom_path() -> None:
    slot = decode_decoration_slot(
        value={"kind": "armor", "level": 1},
        path="$.equipment[0].slots[0]",
    )

    assert slot == DecorationSlot(DecorationKind.ARMOR, 1)


def test_decode_decoration_slot_does_not_mutate_input_dict() -> None:
    value = {"kind": "weapon", "level": 1}
    original = value.copy()

    decode_decoration_slot(value=value)

    assert value == original


def test_decode_decoration_slot_arguments_are_keyword_only() -> None:
    signature = inspect.signature(decode_decoration_slot)

    assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        decode_decoration_slot({"kind": "weapon", "level": 1})  # type: ignore[call-arg]


def test_decode_decoration_slot_accepts_large_positive_level() -> None:
    slot = decode_decoration_slot(value={"kind": "armor", "level": 999})

    assert slot.level == 999


@pytest.mark.parametrize("value", [None, "slot", [], ()])
def test_decode_decoration_slot_rejects_non_dict_objects(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_slot(value=value, path="$.slots[0]")

    assert exc_info.value.path == "$.slots[0]"
    assert "object" in exc_info.value.detail


def test_decode_decoration_slot_rejects_dict_subclass() -> None:
    class SlotDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_slot(
            value=SlotDict(kind="weapon", level=1),
            path="$.slots[0]",
        )

    assert exc_info.value.path == "$.slots[0]"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        ({"level": 1}, ("kind",)),
        ({"kind": "weapon"}, ("level",)),
        ({}, ("kind", "level")),
        ({"kind": "weapon", "level": 1, "extra": True}, ("extra",)),
        ({"kind": "weapon", "unexpected": True}, ("level", "unexpected")),
    ],
)
def test_decode_decoration_slot_rejects_invalid_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_slot(value=value, path="$.slots[0]")

    assert exc_info.value.path == "$.slots[0]"
    for expected_fragment in expected_fragments:
        assert expected_fragment in exc_info.value.detail


def test_decode_decoration_slot_handles_non_string_extra_keys_deterministically() -> (
    None
):
    value = {"kind": "weapon", "level": 1, 3: True, ("x",): False}

    with pytest.raises(CatalogDecodeError) as first_error:
        decode_decoration_slot(value=value, path="$.slots[0]")
    with pytest.raises(CatalogDecodeError) as second_error:
        decode_decoration_slot(value=value, path="$.slots[0]")

    assert first_error.value.path == "$.slots[0]"
    assert first_error.value.detail == second_error.value.detail
    assert "3" in first_error.value.detail
    assert "x" in first_error.value.detail


@pytest.mark.parametrize(
    ("kind", "expected_cause"),
    [
        ("Weapon", ValueError),
        ("body", ValueError),
        ("", ValueError),
        (1, TypeError),
        (None, TypeError),
        (True, TypeError),
        (DecorationKind.WEAPON, TypeError),
    ],
)
def test_decode_decoration_slot_converts_invalid_kind_errors(
    kind: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_slot(value={"kind": kind, "level": 1}, path="$.slots[0]")

    assert exc_info.value.path == "$.slots[0]"
    assert "kind" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    ("level", "expected_cause"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_decode_decoration_slot_converts_invalid_level_errors(
    level: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_slot(
            value={"kind": "weapon", "level": level}, path="$.slots[0]"
        )

    assert exc_info.value.path == "$.slots[0]"
    assert "level" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_existing_skill_contribution_decoder_still_works() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
    )

    assert contribution == SkillContribution("skill:attack-boost", 1)


def test_catalog_decode_error_still_imports_directly() -> None:
    error = CatalogDecodeError(path="$.slots[0]", detail="invalid object")

    assert str(error) == "$.slots[0]: invalid object"
