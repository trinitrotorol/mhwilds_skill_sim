from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mhwilds_skill_sim.api.ranked_search_request import (
    RankedSearchRequest,
    decode_ranked_search_request_payload,
)
from mhwilds_skill_sim.domain.equipment import WeaponKind
from mhwilds_skill_sim.solver.preferences import SkillPreference
from mhwilds_skill_sim.solver.requirements import SkillRequirement


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def preference(
    skill_id: str = "skill:critical-eye",
    target_level: int = 1,
) -> SkillPreference:
    return SkillPreference(skill_id=skill_id, target_level=target_level)


class RequirementTuple(tuple):
    pass


class PreferenceTuple(tuple):
    pass


class PayloadDict(dict[str, object]):
    pass


class PreferenceList(list[object]):
    pass


class PreferencePayloadDict(dict[str, object]):
    pass


def valid_payload() -> dict[str, object]:
    return {
        "requirements": [
            {
                "skill_id": "skill:attack-boost",
                "min_level": 3,
            },
        ],
        "preferences": [
            {
                "skill_id": "skill:critical-eye",
                "target_level": 5,
            },
        ],
        "max_results": 10,
        "weapon_kind": "great-sword",
    }


def test_ranked_search_request_keeps_valid_values() -> None:
    requirements = (requirement(),)
    preferences = (preference(),)

    request = RankedSearchRequest(
        requirements=requirements,
        preferences=preferences,
        max_results=10,
        weapon_kind=WeaponKind.GREAT_SWORD,
    )

    assert request.requirements is requirements
    assert request.preferences is preferences
    assert request.max_results == 10
    assert request.weapon_kind is WeaponKind.GREAT_SWORD


def test_ranked_search_request_is_frozen_and_uses_slots() -> None:
    request = RankedSearchRequest(requirements=(), preferences=(), max_results=0)

    assert RankedSearchRequest.__slots__ == (
        "requirements",
        "preferences",
        "max_results",
        "weapon_kind",
    )
    assert not hasattr(request, "__dict__")
    with pytest.raises(FrozenInstanceError):
        request.max_results = 1  # type: ignore[misc]


def test_ranked_search_request_has_value_semantics_and_is_hashable() -> None:
    request = RankedSearchRequest(
        requirements=(requirement(),),
        preferences=(preference(),),
        max_results=1,
        weapon_kind=WeaponKind.BOW,
    )

    assert request == RankedSearchRequest(
        requirements=(requirement(),),
        preferences=(preference(),),
        max_results=1,
        weapon_kind=WeaponKind.BOW,
    )
    assert request != RankedSearchRequest(
        requirements=(requirement(),),
        preferences=(preference(target_level=2),),
        max_results=1,
        weapon_kind=WeaponKind.BOW,
    )
    assert {request, request} == {request}


@pytest.mark.parametrize("requirements", [[requirement()], None])
def test_ranked_search_request_rejects_non_tuple_requirements(
    requirements: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        RankedSearchRequest(
            requirements=requirements,  # type: ignore[arg-type]
            preferences=(),
            max_results=1,
        )


def test_ranked_search_request_rejects_requirements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        RankedSearchRequest(
            requirements=RequirementTuple((requirement(),)),
            preferences=(),
            max_results=1,
        )


def test_ranked_search_request_rejects_invalid_requirement_item() -> None:
    with pytest.raises(TypeError, match="requirements"):
        RankedSearchRequest(
            requirements=("skill:attack-boost",),  # type: ignore[arg-type]
            preferences=(),
            max_results=1,
        )


def test_ranked_search_request_rejects_duplicate_requirement_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        RankedSearchRequest(
            requirements=(requirement(min_level=1), requirement(min_level=2)),
            preferences=(),
            max_results=1,
        )


@pytest.mark.parametrize("preferences", [[preference()], None])
def test_ranked_search_request_rejects_non_tuple_preferences(
    preferences: object,
) -> None:
    with pytest.raises(TypeError, match="preferences"):
        RankedSearchRequest(
            requirements=(),
            preferences=preferences,  # type: ignore[arg-type]
            max_results=1,
        )


def test_ranked_search_request_rejects_preferences_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="preferences"):
        RankedSearchRequest(
            requirements=(),
            preferences=PreferenceTuple((preference(),)),
            max_results=1,
        )


def test_ranked_search_request_rejects_invalid_preference_item() -> None:
    with pytest.raises(TypeError, match="preferences"):
        RankedSearchRequest(
            requirements=(),
            preferences=("skill:critical-eye",),  # type: ignore[arg-type]
            max_results=1,
        )


def test_ranked_search_request_rejects_duplicate_preference_ids() -> None:
    with pytest.raises(ValueError, match="preferences"):
        RankedSearchRequest(
            requirements=(),
            preferences=(preference(target_level=1), preference(target_level=2)),
            max_results=1,
        )


def test_ranked_search_request_accepts_empty_preferences_and_overlap() -> None:
    assert (
        RankedSearchRequest(
            requirements=(),
            preferences=(),
            max_results=0,
        ).preferences
        == ()
    )

    skill_id = "skill:attack-boost"
    request = RankedSearchRequest(
        requirements=(requirement(skill_id),),
        preferences=(preference(skill_id),),
        max_results=0,
    )

    assert request.requirements[0].skill_id == request.preferences[0].skill_id


@pytest.mark.parametrize("max_results", [True, -1, 1.5, "1", None])
def test_ranked_search_request_rejects_invalid_max_results(
    max_results: object,
) -> None:
    error_type = ValueError if max_results == -1 else TypeError
    with pytest.raises(error_type, match="max_results"):
        RankedSearchRequest(
            requirements=(),
            preferences=(),
            max_results=max_results,  # type: ignore[arg-type]
        )


def test_ranked_search_request_accepts_none_and_valid_weapon_kind() -> None:
    assert (
        RankedSearchRequest(
            requirements=(),
            preferences=(),
            max_results=0,
        ).weapon_kind
        is None
    )
    assert (
        RankedSearchRequest(
            requirements=(),
            preferences=(),
            max_results=0,
            weapon_kind=WeaponKind.BOW,
        ).weapon_kind
        is WeaponKind.BOW
    )


def test_ranked_search_request_rejects_invalid_weapon_kind() -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        RankedSearchRequest(
            requirements=(),
            preferences=(),
            max_results=0,
            weapon_kind="bow",  # type: ignore[arg-type]
        )


def test_ranked_search_request_does_not_mutate_input_tuples() -> None:
    requirements = (requirement(),)
    preferences = (preference(),)
    original_requirements = tuple(requirements)
    original_preferences = tuple(preferences)

    RankedSearchRequest(
        requirements=requirements,
        preferences=preferences,
        max_results=1,
    )

    assert requirements == original_requirements
    assert preferences == original_preferences


def test_decode_ranked_search_request_payload_has_exact_keyword_only_signature() -> (
    None
):
    signature = inspect.signature(decode_ranked_search_request_payload)

    assert list(signature.parameters) == ["payload"]
    assert signature.parameters["payload"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        decode_ranked_search_request_payload(valid_payload())  # type: ignore[call-arg]


def test_decode_ranked_search_request_payload_converts_full_payload() -> None:
    request = decode_ranked_search_request_payload(payload=valid_payload())

    assert request == RankedSearchRequest(
        requirements=(requirement(min_level=3),),
        preferences=(preference(target_level=5),),
        max_results=10,
        weapon_kind=WeaponKind.GREAT_SWORD,
    )


def test_decode_ranked_search_request_payload_preserves_omitted_and_null_weapon_kind() -> (
    None
):
    omitted = valid_payload()
    del omitted["weapon_kind"]
    explicit_null = {**omitted, "weapon_kind": None}

    assert decode_ranked_search_request_payload(payload=omitted).weapon_kind is None
    assert (
        decode_ranked_search_request_payload(payload=explicit_null).weapon_kind is None
    )


def test_decode_ranked_search_request_payload_accepts_empty_preferences() -> None:
    payload = {**valid_payload(), "preferences": []}

    assert decode_ranked_search_request_payload(payload=payload).preferences == ()


def test_decode_ranked_search_request_payload_preserves_item_order() -> None:
    payload = {
        "requirements": [
            {"skill_id": "skill:first-required", "min_level": 1},
            {"skill_id": "skill:second-required", "min_level": 2},
        ],
        "preferences": [
            {"skill_id": "skill:first-preferred", "target_level": 3},
            {"skill_id": "skill:second-preferred", "target_level": 4},
        ],
        "max_results": 2,
    }

    request = decode_ranked_search_request_payload(payload=payload)

    assert [value.skill_id for value in request.requirements] == [
        "skill:first-required",
        "skill:second-required",
    ]
    assert [value.skill_id for value in request.preferences] == [
        "skill:first-preferred",
        "skill:second-preferred",
    ]


def test_decode_ranked_search_request_payload_allows_requirement_preference_overlap() -> (
    None
):
    payload = {
        "requirements": [{"skill_id": "skill:overlap", "min_level": 1}],
        "preferences": [{"skill_id": "skill:overlap", "target_level": 5}],
        "max_results": 1,
    }

    request = decode_ranked_search_request_payload(payload=payload)

    assert request.requirements[0].skill_id == request.preferences[0].skill_id


def test_decode_ranked_search_request_payload_accepts_unknown_and_large_target() -> (
    None
):
    payload = {
        "requirements": [],
        "preferences": [
            {"skill_id": "unknown:skill:999", "target_level": 999_999},
        ],
        "max_results": 1,
    }

    assert decode_ranked_search_request_payload(payload=payload).preferences == (
        preference("unknown:skill:999", 999_999),
    )


@pytest.mark.parametrize("payload", [None, [], "payload"])
def test_decode_ranked_search_request_payload_rejects_non_dict_root(
    payload: object,
) -> None:
    with pytest.raises(TypeError, match="payload"):
        decode_ranked_search_request_payload(payload=payload)


def test_decode_ranked_search_request_payload_rejects_root_dict_subclass() -> None:
    with pytest.raises(TypeError, match="payload"):
        decode_ranked_search_request_payload(payload=PayloadDict(valid_payload()))


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"requirements": [], "max_results": 1},
            "preferences",
        ),
        (
            {"preferences": [], "max_results": 1},
            "requirements",
        ),
        (
            {"requirements": [], "preferences": []},
            "max_results",
        ),
    ],
)
def test_decode_ranked_search_request_payload_rejects_missing_root_keys(
    payload: dict[str, object],
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        decode_ranked_search_request_payload(payload=payload)


def test_decode_ranked_search_request_payload_rejects_extra_root_key() -> None:
    with pytest.raises(ValueError, match="payload.*unexpected keys.*extra"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "extra": True},
        )


@pytest.mark.parametrize("preferences", [None, (), {}, "preference"])
def test_decode_ranked_search_request_payload_rejects_non_list_preferences(
    preferences: object,
) -> None:
    with pytest.raises(TypeError, match="preferences"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "preferences": preferences},
        )


def test_decode_ranked_search_request_payload_rejects_preference_list_subclass() -> (
    None
):
    with pytest.raises(TypeError, match="preferences"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "preferences": PreferenceList()},
        )


@pytest.mark.parametrize("value", [None, [], "preference"])
def test_decode_ranked_search_request_payload_rejects_non_dict_preference_item(
    value: object,
) -> None:
    with pytest.raises(TypeError, match=r"preferences\[0\]"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "preferences": [value]},
        )


def test_decode_ranked_search_request_payload_rejects_preference_dict_subclass() -> (
    None
):
    value = PreferencePayloadDict(
        {"skill_id": "skill:critical-eye", "target_level": 1},
    )

    with pytest.raises(TypeError, match=r"preferences\[0\]"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "preferences": [value]},
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"target_level": 1}, r"preferences\[0\].*skill_id"),
        (
            {"skill_id": "skill:critical-eye"},
            r"preferences\[0\].*target_level",
        ),
        (
            {
                "skill_id": "skill:critical-eye",
                "target_level": 1,
                "extra": True,
            },
            r"preferences\[0\].*unexpected keys.*extra",
        ),
    ],
)
def test_decode_ranked_search_request_payload_rejects_invalid_preference_shape(
    value: dict[str, object],
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "preferences": [value]},
        )


@pytest.mark.parametrize("skill_id", [1, None, ""])
def test_decode_ranked_search_request_payload_propagates_invalid_skill_id(
    skill_id: object,
) -> None:
    error_type = ValueError if skill_id == "" else TypeError
    with pytest.raises(error_type, match=r"preferences\[0\].*skill_id"):
        decode_ranked_search_request_payload(
            payload={
                **valid_payload(),
                "preferences": [{"skill_id": skill_id, "target_level": 1}],
            },
        )


@pytest.mark.parametrize("target_level", [True, 0, -1, 1.5, "1", None])
def test_decode_ranked_search_request_payload_propagates_invalid_target_level(
    target_level: object,
) -> None:
    error_type = ValueError if target_level in (0, -1) else TypeError
    with pytest.raises(error_type, match=r"preferences\[0\].*target_level"):
        decode_ranked_search_request_payload(
            payload={
                **valid_payload(),
                "preferences": [
                    {
                        "skill_id": "skill:critical-eye",
                        "target_level": target_level,
                    },
                ],
            },
        )


def test_decode_ranked_search_request_payload_reports_value_error_item_index() -> None:
    with pytest.raises(ValueError, match=r"preferences\[1\].*target_level"):
        decode_ranked_search_request_payload(
            payload={
                **valid_payload(),
                "preferences": [
                    {"skill_id": "skill:first", "target_level": 1},
                    {"skill_id": "skill:second", "target_level": 0},
                ],
            },
        )


def test_decode_ranked_search_request_payload_rejects_duplicate_preference_ids() -> (
    None
):
    with pytest.raises(ValueError, match=r"preferences\[1\].*skill_id"):
        decode_ranked_search_request_payload(
            payload={
                **valid_payload(),
                "preferences": [
                    {"skill_id": "skill:critical-eye", "target_level": 1},
                    {"skill_id": "skill:critical-eye", "target_level": 2},
                ],
            },
        )


def test_decode_ranked_search_request_payload_propagates_requirement_validation() -> (
    None
):
    with pytest.raises(ValueError, match="min_level"):
        decode_ranked_search_request_payload(
            payload={
                **valid_payload(),
                "requirements": [
                    {"skill_id": "skill:attack-boost", "min_level": 0},
                ],
            },
        )


@pytest.mark.parametrize("max_results", [True, -1])
def test_decode_ranked_search_request_payload_propagates_max_results_validation(
    max_results: object,
) -> None:
    error_type = ValueError if max_results == -1 else TypeError
    with pytest.raises(error_type, match="max_results"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "max_results": max_results},
        )


@pytest.mark.parametrize("weapon_kind", [1, "great_sword"])
def test_decode_ranked_search_request_payload_propagates_weapon_kind_validation(
    weapon_kind: object,
) -> None:
    error_type = ValueError if type(weapon_kind) is str else TypeError
    with pytest.raises(error_type, match="weapon_kind"):
        decode_ranked_search_request_payload(
            payload={**valid_payload(), "weapon_kind": weapon_kind},
        )


def test_decode_ranked_search_request_payload_does_not_mutate_payload() -> None:
    payload = valid_payload()
    original = {
        "requirements": [dict(payload["requirements"][0])],  # type: ignore[index]
        "preferences": [dict(payload["preferences"][0])],  # type: ignore[index]
        "max_results": payload["max_results"],
        "weapon_kind": payload["weapon_kind"],
    }

    decode_ranked_search_request_payload(payload=payload)

    assert payload == original


def test_ranked_search_request_is_direct_module_only_and_api_all_is_unchanged() -> None:
    import mhwilds_skill_sim.api as api

    assert not hasattr(api, "RankedSearchRequest")
    assert not hasattr(api, "decode_ranked_search_request_payload")
    assert api.__all__ == [
        "SearchRequest",
        "app",
        "build_candidate_search_result_to_response",
        "build_candidate_to_response",
        "create_app",
        "decode_search_request_payload",
        "search_catalog_build_candidates_from_payload",
    ]


def test_ranked_search_request_scope_regression() -> None:
    import mhwilds_skill_sim.api.ranked_search_request as ranked_search_request

    source = Path(ranked_search_request.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    for forbidden in (
        "fastapi",
        "pydantic",
        "requests",
        "urllib",
        "pathlib",
        "open(",
    ):
        assert forbidden not in lowered_source
