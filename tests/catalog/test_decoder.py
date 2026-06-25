from __future__ import annotations

import inspect

import pytest

from mhwilds_skill_sim.catalog.decoder import decode_skill_contribution
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.skill import SkillContribution


def test_catalog_decode_error_is_value_error_subclass() -> None:
    assert issubclass(CatalogDecodeError, ValueError)


def test_catalog_decode_error_preserves_path_and_detail() -> None:
    error = CatalogDecodeError(path="$.skills[0]", detail="invalid object")

    assert error.path == "$.skills[0]"
    assert error.detail == "invalid object"
    assert str(error) == "$.skills[0]: invalid object"


def test_catalog_decode_error_constructor_is_keyword_only() -> None:
    signature = inspect.signature(CatalogDecodeError)

    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["detail"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        CatalogDecodeError("$.skills[0]", "invalid object")  # type: ignore[call-arg]


def test_decode_skill_contribution_returns_skill_contribution() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
    )

    assert isinstance(contribution, SkillContribution)
    assert contribution.skill_id == "skill:attack-boost"
    assert contribution.level == 1


def test_decode_skill_contribution_accepts_reverse_key_order() -> None:
    contribution = decode_skill_contribution(
        value={"level": 2, "skill_id": "skill:critical-eye"},
    )

    assert contribution.skill_id == "skill:critical-eye"
    assert contribution.level == 2


def test_decode_skill_contribution_preserves_skill_id_without_normalization() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "Skill:Internal_ID-01", "level": 1},
    )

    assert contribution.skill_id == "Skill:Internal_ID-01"


def test_decode_skill_contribution_accepts_custom_path() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
        path="$.equipment[0].skills[0]",
    )

    assert contribution == SkillContribution("skill:attack-boost", 1)


def test_decode_skill_contribution_does_not_mutate_input_dict() -> None:
    value = {"skill_id": "skill:attack-boost", "level": 1}
    original = value.copy()

    decode_skill_contribution(value=value)

    assert value == original


def test_decode_skill_contribution_arguments_are_keyword_only() -> None:
    signature = inspect.signature(decode_skill_contribution)

    assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        decode_skill_contribution({"skill_id": "skill:attack-boost", "level": 1})  # type: ignore[call-arg]


@pytest.mark.parametrize("value", [None, "skill", [], ()])
def test_decode_skill_contribution_rejects_non_dict_objects(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_contribution(value=value, path="$.skills[0]")

    assert exc_info.value.path == "$.skills[0]"
    assert "object" in exc_info.value.detail


def test_decode_skill_contribution_rejects_dict_subclass() -> None:
    class SkillDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_contribution(
            value=SkillDict(skill_id="skill:attack-boost", level=1),
            path="$.skills[0]",
        )

    assert exc_info.value.path == "$.skills[0]"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        ({"level": 1}, ("skill_id",)),
        ({"skill_id": "skill:attack-boost"}, ("level",)),
        ({}, ("skill_id", "level")),
        (
            {"skill_id": "skill:attack-boost", "level": 1, "extra": True},
            ("extra",),
        ),
        (
            {"skill_id": "skill:attack-boost", "unexpected": True},
            ("level", "unexpected"),
        ),
    ],
)
def test_decode_skill_contribution_rejects_invalid_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_contribution(value=value, path="$.skills[0]")

    assert exc_info.value.path == "$.skills[0]"
    for expected_fragment in expected_fragments:
        assert expected_fragment in exc_info.value.detail


def test_decode_skill_contribution_handles_non_string_extra_keys_deterministically() -> (
    None
):
    value = {"skill_id": "skill:attack-boost", "level": 1, 3: True, ("x",): False}

    first_error = pytest.raises(
        CatalogDecodeError,
        decode_skill_contribution,
        value=value,
        path="$.skills[0]",
    )
    second_error = pytest.raises(
        CatalogDecodeError,
        decode_skill_contribution,
        value=value,
        path="$.skills[0]",
    )

    assert first_error.value.path == "$.skills[0]"
    assert first_error.value.detail == second_error.value.detail
    assert "3" in first_error.value.detail
    assert "x" in first_error.value.detail


@pytest.mark.parametrize(
    ("value", "expected_cause"),
    [
        ({"skill_id": 1, "level": 1}, TypeError),
        ({"skill_id": "", "level": 1}, ValueError),
        ({"skill_id": " ", "level": 1}, ValueError),
        ({"skill_id": "skill:attack-boost", "level": "1"}, TypeError),
        ({"skill_id": "skill:attack-boost", "level": 0}, ValueError),
        ({"skill_id": "skill:attack-boost", "level": -1}, ValueError),
    ],
)
def test_decode_skill_contribution_converts_domain_errors(
    value: dict[str, object],
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_contribution(value=value, path="$.skills[0]")

    assert exc_info.value.path == "$.skills[0]"
    assert isinstance(exc_info.value.__cause__, expected_cause)
    assert exc_info.value.__cause__ is not None
    assert str(exc_info.value.__cause__) in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "field_name"),
    [
        ({"skill_id": 1, "level": 1}, "skill_id"),
        ({"skill_id": "", "level": 1}, "skill_id"),
        ({"skill_id": "skill:attack-boost", "level": "1"}, "level"),
        ({"skill_id": "skill:attack-boost", "level": 0}, "level"),
    ],
)
def test_decode_skill_contribution_domain_error_detail_includes_field_name(
    value: dict[str, object],
    field_name: str,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_contribution(value=value)

    assert field_name in exc_info.value.detail
