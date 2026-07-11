from __future__ import annotations

import copy
import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.catalog.decoder import (
    decode_decoration_definition,
    decode_decoration_slot,
    decode_skill_contribution,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot


def valid_decoration_value() -> dict[str, object]:
    return {
        "decoration_id": "fixture:decoration:armor-combination-2",
        "required_slot": {"kind": "armor", "level": 2},
        "skills": [
            {"skill_id": "skill:attack-boost", "level": 1},
            {"skill_id": "skill:critical-eye", "level": 1},
        ],
    }


def single_skill_decoration_value() -> dict[str, object]:
    return {
        "decoration_id": "fixture:decoration:armor-power-1",
        "required_slot": {"kind": "armor", "level": 1},
        "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
    }


def generator() -> Iterator[dict[str, object]]:
    yield {"skill_id": "skill:attack-boost", "level": 1}


def assert_nested_error_not_wrapped(error: CatalogDecodeError) -> None:
    assert not isinstance(error.__cause__, CatalogDecodeError)


def test_decode_decoration_definition_converts_single_skill_decoration() -> None:
    decoration = decode_decoration_definition(value=single_skill_decoration_value())

    assert isinstance(decoration, DecorationDefinition)
    assert decoration.decoration_id == "fixture:decoration:armor-power-1"
    assert decoration.required_slot == DecorationSlot(DecorationKind.ARMOR, 1)
    assert decoration.skills == (SkillContribution("skill:attack-boost", 1),)


def test_decode_decoration_definition_converts_multiple_skill_decoration() -> None:
    decoration = decode_decoration_definition(value=valid_decoration_value())

    assert isinstance(decoration, DecorationDefinition)
    assert decoration.decoration_id == "fixture:decoration:armor-combination-2"
    assert decoration.required_slot == DecorationSlot(DecorationKind.ARMOR, 2)
    assert type(decoration.skills) is tuple
    assert decoration.skills == (
        SkillContribution("skill:attack-boost", 1),
        SkillContribution("skill:critical-eye", 1),
    )


def test_decode_decoration_definition_preserves_skill_order() -> None:
    decoration = decode_decoration_definition(value=valid_decoration_value())

    assert [skill.skill_id for skill in decoration.skills] == [
        "skill:attack-boost",
        "skill:critical-eye",
    ]


def test_decode_decoration_definition_accepts_reverse_root_key_order() -> None:
    decoration = decode_decoration_definition(
        value={
            "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            "required_slot": {"kind": "weapon", "level": 1},
            "decoration_id": "fixture:decoration:weapon-power-1",
        },
    )

    assert decoration.decoration_id == "fixture:decoration:weapon-power-1"
    assert decoration.required_slot == DecorationSlot(DecorationKind.WEAPON, 1)


def test_decode_decoration_definition_accepts_custom_path() -> None:
    decoration = decode_decoration_definition(
        value=single_skill_decoration_value(),
        path="$.decorations[0]",
    )

    assert decoration == DecorationDefinition(
        decoration_id="fixture:decoration:armor-power-1",
        required_slot=DecorationSlot(DecorationKind.ARMOR, 1),
        skills=(SkillContribution("skill:attack-boost", 1),),
    )


def test_decode_decoration_definition_does_not_mutate_nested_input() -> None:
    value = valid_decoration_value()
    original = copy.deepcopy(value)

    decode_decoration_definition(value=value)

    assert value == original


def test_decode_decoration_definition_arguments_are_keyword_only() -> None:
    signature = inspect.signature(decode_decoration_definition)

    assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        decode_decoration_definition(valid_decoration_value())  # type: ignore[call-arg]


@pytest.mark.parametrize("value", [None, "decoration", [], ()])
def test_decode_decoration_definition_rejects_non_dict_objects(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    assert "object" in exc_info.value.detail


def test_decode_decoration_definition_rejects_dict_subclass() -> None:
    class DecorationDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(
            value=DecorationDict(single_skill_decoration_value()),
            path="$.decorations[0]",
        )

    assert exc_info.value.path == "$.decorations[0]"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        (
            {
                "required_slot": {"kind": "armor", "level": 1},
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            },
            ("decoration_id",),
        ),
        (
            {
                "decoration_id": "fixture:decoration:armor-power-1",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            },
            ("required_slot",),
        ),
        (
            {
                "decoration_id": "fixture:decoration:armor-power-1",
                "required_slot": {"kind": "armor", "level": 1},
            },
            ("skills",),
        ),
        ({}, ("decoration_id", "required_slot", "skills")),
        (
            {
                "decoration_id": "fixture:decoration:armor-power-1",
                "required_slot": {"kind": "armor", "level": 1},
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "extra": True,
            },
            ("extra",),
        ),
        (
            {
                "decoration_id": "fixture:decoration:armor-power-1",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "unexpected": True,
            },
            ("required_slot", "unexpected"),
        ),
    ],
)
def test_decode_decoration_definition_rejects_invalid_root_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    for expected_fragment in expected_fragments:
        assert expected_fragment in exc_info.value.detail


def test_decode_decoration_definition_handles_non_string_extra_keys_deterministically() -> (
    None
):
    value = valid_decoration_value()
    value[3] = True
    value[("x",)] = False

    with pytest.raises(CatalogDecodeError) as first_error:
        decode_decoration_definition(value=value, path="$.decorations[0]")
    with pytest.raises(CatalogDecodeError) as second_error:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert first_error.value.path == "$.decorations[0]"
    assert first_error.value.detail == second_error.value.detail
    assert "3" in first_error.value.detail
    assert "x" in first_error.value.detail


@pytest.mark.parametrize(
    ("decoration_id", "expected_cause"),
    [
        (1, TypeError),
        (None, TypeError),
        ("", ValueError),
        (" ", ValueError),
        (" fixture:decoration:armor-power-1", ValueError),
        ("fixture:decoration:armor-power-1 ", ValueError),
    ],
)
def test_decode_decoration_definition_converts_invalid_decoration_id_errors(
    decoration_id: object,
    expected_cause: type[Exception],
) -> None:
    value = single_skill_decoration_value()
    value["decoration_id"] = decoration_id

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    assert "decoration_id" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    "required_slot",
    [
        None,
        {"level": 1},
        {"kind": "armor"},
        {"kind": "body", "level": 1},
        {"kind": "armor", "level": 0},
    ],
)
def test_decode_decoration_definition_propagates_required_slot_errors(
    required_slot: object,
) -> None:
    value = single_skill_decoration_value()
    value["required_slot"] = required_slot

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0].required_slot"
    assert_nested_error_not_wrapped(exc_info.value)


@pytest.mark.parametrize(
    "skills",
    [
        ({"skill_id": "skill:attack-boost", "level": 1},),
        {"skill_id": "skill:attack-boost", "level": 1},
        {("skill:attack-boost", 1)},
        generator(),
        None,
    ],
)
def test_decode_decoration_definition_rejects_non_list_skills(skills: object) -> None:
    value = single_skill_decoration_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0].skills"
    assert "skills" in exc_info.value.detail


def test_decode_decoration_definition_rejects_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    value = single_skill_decoration_value()
    value["skills"] = SkillList([{"skill_id": "skill:attack-boost", "level": 1}])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0].skills"
    assert "skills" in exc_info.value.detail


def test_decode_decoration_definition_rejects_empty_skills_list() -> None:
    value = single_skill_decoration_value()
    value["skills"] = []

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0].skills"
    assert "skills" in exc_info.value.detail


@pytest.mark.parametrize(
    ("skills", "expected_path"),
    [
        ([{"level": 1}], "$.decorations[0].skills[0]"),
        (
            [
                {"skill_id": "skill:attack-boost", "level": 1},
                {"skill_id": "skill:critical-eye"},
            ],
            "$.decorations[0].skills[1]",
        ),
        ([{"skill_id": "", "level": 1}], "$.decorations[0].skills[0]"),
    ],
)
def test_decode_decoration_definition_propagates_skill_element_errors(
    skills: list[object],
    expected_path: str,
) -> None:
    value = single_skill_decoration_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == expected_path
    assert_nested_error_not_wrapped(exc_info.value)


@pytest.mark.parametrize(
    "skills",
    [
        [
            {"skill_id": "skill:attack-boost", "level": 1},
            {"skill_id": "skill:attack-boost", "level": 1},
        ],
        [
            {"skill_id": "skill:attack-boost", "level": 1},
            {"skill_id": "skill:attack-boost", "level": 2},
        ],
    ],
)
def test_decode_decoration_definition_converts_duplicate_skill_errors(
    skills: list[dict[str, object]],
) -> None:
    value = single_skill_decoration_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_existing_skill_contribution_decoder_still_works() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
    )

    assert contribution == SkillContribution("skill:attack-boost", 1)


def test_existing_decoration_slot_decoder_still_works() -> None:
    slot = decode_decoration_slot(value={"kind": "weapon", "level": 1})

    assert slot == DecorationSlot(DecorationKind.WEAPON, 1)


def test_catalog_decode_error_still_imports_directly() -> None:
    error = CatalogDecodeError(path="$.decorations[0]", detail="invalid object")

    assert str(error) == "$.decorations[0]: invalid object"


def test_decode_normalized_decoration_without_display_name_remains_valid() -> None:
    decoded = decode_decoration_definition(value=single_skill_decoration_value())

    assert decoded.display_name is None


def test_decode_normalized_decoration_accepts_explicit_null_display_name() -> None:
    value = single_skill_decoration_value()
    value["display_name"] = None

    decoded = decode_decoration_definition(value=value)

    assert decoded.display_name is None


@pytest.mark.parametrize(
    "display_name",
    ["攻撃珠【1】（テスト）", "Attack Jewel [1] (Test)"],
)
def test_decode_normalized_decoration_preserves_display_name(
    display_name: str,
) -> None:
    value = single_skill_decoration_value()
    value["display_name"] = display_name

    decoded = decode_decoration_definition(value=value)

    assert decoded.display_name == display_name


def test_decode_normalized_decoration_display_name_key_order_is_independent() -> None:
    value = {
        "display_name": "攻撃珠【1】（テスト）",
        "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
        "decoration_id": "fixture:decoration:armor-power-1",
        "required_slot": {"kind": "armor", "level": 1},
    }

    decoded = decode_decoration_definition(value=value)

    assert decoded == DecorationDefinition(
        decoration_id="fixture:decoration:armor-power-1",
        required_slot=DecorationSlot(DecorationKind.ARMOR, 1),
        skills=(SkillContribution("skill:attack-boost", 1),),
        display_name="攻撃珠【1】（テスト）",
    )


@pytest.mark.parametrize(
    ("display_name", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (1.5, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" Attack Jewel", ValueError),
        ("Attack Jewel ", ValueError),
    ],
)
def test_decode_normalized_decoration_wraps_invalid_display_name(
    display_name: object,
    expected_cause: type[Exception],
) -> None:
    value = single_skill_decoration_value()
    value["display_name"] = display_name

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    assert "display_name" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_decode_normalized_decoration_rejects_display_name_string_subclass() -> None:
    class DisplayName(str):
        pass

    value = single_skill_decoration_value()
    value["display_name"] = DisplayName("Attack Jewel")

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    assert "display_name" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_normalized_decoration_with_display_name_still_rejects_unknown_key() -> None:
    value = single_skill_decoration_value()
    value["display_name"] = "Attack Jewel"
    value["description"] = "must remain upstream-only"

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_decoration_definition(value=value, path="$.decorations[0]")

    assert exc_info.value.path == "$.decorations[0]"
    assert "description" in exc_info.value.detail
    assert exc_info.value.__cause__ is None
