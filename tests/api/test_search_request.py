from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mhwilds_skill_sim.api.search_request import (
    SearchRequest,
    decode_search_request_payload,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement()


def payload_requirement_generator() -> Iterator[dict[str, object]]:
    yield {"skill_id": "skill:attack-boost", "min_level": 1}


class RequirementTuple(tuple):
    pass


class PayloadDict(dict[str, object]):
    pass


class RequirementList(list[object]):
    pass


class RequirementPayloadDict(dict[str, object]):
    pass


def valid_payload() -> dict[str, object]:
    return {
        "requirements": [
            {
                "skill_id": "skill:attack-boost",
                "min_level": 3,
            },
        ],
        "max_results": 20,
    }


def test_search_request_keeps_valid_values() -> None:
    requirements = (
        requirement("skill:attack-boost", 1),
        requirement("skill:critical-eye", 2),
    )

    request = SearchRequest(requirements=requirements, max_results=20)

    assert request.requirements == requirements
    assert request.max_results == 20


def test_search_request_accepts_empty_requirements_and_zero_max_results() -> None:
    request = SearchRequest(requirements=(), max_results=0)

    assert request.requirements == ()
    assert request.max_results == 0


def test_search_request_value_semantics_and_hashing() -> None:
    request = SearchRequest(requirements=(requirement(),), max_results=1)

    assert request == SearchRequest(requirements=(requirement(),), max_results=1)
    assert request != SearchRequest(requirements=(), max_results=1)
    assert {request, request} == {request}


def test_search_request_is_frozen() -> None:
    request = SearchRequest(requirements=(), max_results=0)

    with pytest.raises(FrozenInstanceError):
        request.max_results = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "requirements",
    [[requirement()], {requirement()}, requirement_generator(), None],
)
def test_search_request_rejects_non_tuple_requirements(requirements: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        SearchRequest(
            requirements=requirements,  # type: ignore[arg-type]
            max_results=0,
        )


def test_search_request_rejects_requirements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        SearchRequest(requirements=RequirementTuple((requirement(),)), max_results=1)


@pytest.mark.parametrize("invalid_requirement", ["skill:attack-boost", None])
def test_search_request_rejects_invalid_requirement_elements(
    invalid_requirement: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        SearchRequest(
            requirements=(invalid_requirement,),  # type: ignore[arg-type]
            max_results=1,
        )


def test_search_request_rejects_duplicate_requirement_skill_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        SearchRequest(
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
            max_results=1,
        )


@pytest.mark.parametrize("max_results", [True, 1.5, "1", None])
def test_search_request_rejects_invalid_max_results_types(
    max_results: object,
) -> None:
    with pytest.raises(TypeError, match="max_results"):
        SearchRequest(
            requirements=(),
            max_results=max_results,  # type: ignore[arg-type]
        )


def test_search_request_rejects_negative_max_results() -> None:
    with pytest.raises(ValueError, match="max_results"):
        SearchRequest(requirements=(), max_results=-1)


def test_search_request_public_import() -> None:
    from mhwilds_skill_sim.api import SearchRequest as ExportedSearchRequest

    assert ExportedSearchRequest is SearchRequest


def test_decode_search_request_payload_converts_valid_payload() -> None:
    request = decode_search_request_payload(payload=valid_payload())

    assert request == SearchRequest(
        requirements=(requirement("skill:attack-boost", 3),),
        max_results=20,
    )


def test_decode_search_request_payload_accepts_empty_requirements() -> None:
    request = decode_search_request_payload(
        payload={
            "requirements": [],
            "max_results": 10,
        },
    )

    assert request == SearchRequest(requirements=(), max_results=10)


def test_decode_search_request_payload_preserves_requirement_order() -> None:
    request = decode_search_request_payload(
        payload={
            "requirements": [
                {"skill_id": "skill:attack-boost", "min_level": 1},
                {"skill_id": "skill:critical-eye", "min_level": 2},
            ],
            "max_results": 20,
        },
    )

    assert request.requirements == (
        requirement("skill:attack-boost", 1),
        requirement("skill:critical-eye", 2),
    )


def test_decode_search_request_payload_preserves_max_results_zero_and_large_values() -> (
    None
):
    assert (
        decode_search_request_payload(
            payload={
                "requirements": [],
                "max_results": 0,
            },
        ).max_results
        == 0
    )
    assert (
        decode_search_request_payload(
            payload={
                "requirements": [],
                "max_results": 9999,
            },
        ).max_results
        == 9999
    )


def test_decode_search_request_payload_accepts_root_key_order_variations() -> None:
    request = decode_search_request_payload(
        payload={
            "max_results": 5,
            "requirements": [
                {"min_level": 3, "skill_id": "Skill:Internal_ID-01"},
            ],
        },
    )

    assert request == SearchRequest(
        requirements=(requirement("Skill:Internal_ID-01", 3),),
        max_results=5,
    )


def test_decode_search_request_payload_preserves_skill_id_text() -> None:
    request = decode_search_request_payload(
        payload={
            "requirements": [
                {"skill_id": "Skill:Internal_ID-01", "min_level": 1},
            ],
            "max_results": 1,
        },
    )

    assert request.requirements == (requirement("Skill:Internal_ID-01", 1),)


def test_decode_search_request_payload_does_not_mutate_input() -> None:
    payload = valid_payload()
    original_payload = {
        "requirements": [dict(payload["requirements"][0])],  # type: ignore[index]
        "max_results": payload["max_results"],
    }

    decode_search_request_payload(payload=payload)

    assert payload == original_payload


def test_decode_search_request_payload_requires_keyword_argument() -> None:
    signature = inspect.signature(decode_search_request_payload)

    assert signature.parameters["payload"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        decode_search_request_payload(valid_payload())  # type: ignore[call-arg]


def test_decode_search_request_payload_public_import_and_api_all() -> None:
    import mhwilds_skill_sim.api as api
    from mhwilds_skill_sim.api import (
        decode_search_request_payload as exported_decoder,
    )
    from mhwilds_skill_sim.api import (
        build_candidate_search_result_to_response,
        build_candidate_to_response,
    )

    assert exported_decoder is decode_search_request_payload
    assert api.SearchRequest is SearchRequest
    assert api.build_candidate_to_response is build_candidate_to_response
    assert (
        api.build_candidate_search_result_to_response
        is build_candidate_search_result_to_response
    )
    assert type(api.__all__) is list
    assert api.__all__ == [
        "SearchRequest",
        "build_candidate_search_result_to_response",
        "build_candidate_to_response",
        "decode_search_request_payload",
    ]


@pytest.mark.parametrize("payload", [None, "payload", [], ()])
def test_decode_search_request_payload_rejects_non_dict_payload(
    payload: object,
) -> None:
    with pytest.raises(TypeError, match="payload"):
        decode_search_request_payload(payload=payload)


def test_decode_search_request_payload_rejects_dict_subclass() -> None:
    with pytest.raises(TypeError, match="payload"):
        decode_search_request_payload(
            payload=PayloadDict({"requirements": [], "max_results": 1}),
        )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"max_results": 1}, "requirements"),
        ({"requirements": []}, "max_results"),
        ({}, "requirements.*max_results"),
    ],
)
def test_decode_search_request_payload_rejects_missing_root_keys(
    payload: dict[str, object],
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        decode_search_request_payload(payload=payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"requirements": [], "max_results": 1, "extra": True},
        {"requirements": [], "max_results": 1, 1: True},
    ],
)
def test_decode_search_request_payload_rejects_extra_root_keys(
    payload: dict[object, object],
) -> None:
    with pytest.raises(ValueError, match="payload.*unexpected keys"):
        decode_search_request_payload(payload=payload)


def test_decode_search_request_payload_reports_missing_and_extra_root_keys() -> None:
    with pytest.raises(ValueError) as exc_info:
        decode_search_request_payload(payload={"requirements": [], "extra": True})

    message = str(exc_info.value)
    assert "payload" in message
    assert "max_results" in message
    assert "extra" in message


def test_decode_search_request_payload_reports_non_string_extra_keys() -> None:
    with pytest.raises(ValueError) as exc_info:
        decode_search_request_payload(payload={"requirements": [], 1: True})

    message = str(exc_info.value)
    assert "payload" in message
    assert "max_results" in message
    assert "1" in message


@pytest.mark.parametrize(
    "requirements",
    [(), {}, set(), payload_requirement_generator(), None],
)
def test_decode_search_request_payload_rejects_non_list_requirements(
    requirements: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        decode_search_request_payload(
            payload={
                "requirements": requirements,
                "max_results": 1,
            },
        )


def test_decode_search_request_payload_rejects_requirements_list_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        decode_search_request_payload(
            payload={
                "requirements": RequirementList(),
                "max_results": 1,
            },
        )


@pytest.mark.parametrize("value", [None, "requirement", []])
def test_decode_search_request_payload_rejects_non_dict_requirement_items(
    value: object,
) -> None:
    with pytest.raises(TypeError, match=r"requirements\[0\]"):
        decode_search_request_payload(
            payload={
                "requirements": [value],
                "max_results": 1,
            },
        )


def test_decode_search_request_payload_rejects_requirement_dict_subclass() -> None:
    with pytest.raises(TypeError, match=r"requirements\[0\]"):
        decode_search_request_payload(
            payload={
                "requirements": [
                    RequirementPayloadDict(
                        {
                            "skill_id": "skill:attack-boost",
                            "min_level": 1,
                        },
                    ),
                ],
                "max_results": 1,
            },
        )


@pytest.mark.parametrize(
    ("requirement_payload", "expected"),
    [
        ({"min_level": 1}, r"requirements\[0\].*skill_id"),
        ({"skill_id": "skill:attack-boost"}, r"requirements\[0\].*min_level"),
        (
            {"skill_id": "skill:attack-boost", "min_level": 1, "extra": True},
            r"requirements\[0\].*extra",
        ),
    ],
)
def test_decode_search_request_payload_rejects_invalid_requirement_item_shape(
    requirement_payload: dict[str, object],
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        decode_search_request_payload(
            payload={
                "requirements": [requirement_payload],
                "max_results": 1,
            },
        )


def test_decode_search_request_payload_reports_requirement_index() -> None:
    with pytest.raises(ValueError, match=r"requirements\[1\].*min_level"):
        decode_search_request_payload(
            payload={
                "requirements": [
                    {"skill_id": "skill:attack-boost", "min_level": 1},
                    {"skill_id": "skill:critical-eye"},
                ],
                "max_results": 1,
            },
        )


@pytest.mark.parametrize("skill_id", [1, None])
def test_decode_search_request_payload_propagates_invalid_skill_id_type(
    skill_id: object,
) -> None:
    with pytest.raises(TypeError, match="skill_id"):
        decode_search_request_payload(
            payload={
                "requirements": [
                    {"skill_id": skill_id, "min_level": 1},
                ],
                "max_results": 1,
            },
        )


@pytest.mark.parametrize("min_level", [True, 1.5, "1", None])
def test_decode_search_request_payload_propagates_invalid_min_level_type(
    min_level: object,
) -> None:
    with pytest.raises(TypeError, match="min_level"):
        decode_search_request_payload(
            payload={
                "requirements": [
                    {"skill_id": "skill:attack-boost", "min_level": min_level},
                ],
                "max_results": 1,
            },
        )


def test_decode_search_request_payload_propagates_invalid_min_level_value() -> None:
    with pytest.raises(ValueError, match="min_level"):
        decode_search_request_payload(
            payload={
                "requirements": [
                    {"skill_id": "skill:attack-boost", "min_level": 0},
                ],
                "max_results": 1,
            },
        )


def test_decode_search_request_payload_rejects_duplicate_skill_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        decode_search_request_payload(
            payload={
                "requirements": [
                    {"skill_id": "skill:attack-boost", "min_level": 1},
                    {"skill_id": "skill:attack-boost", "min_level": 2},
                ],
                "max_results": 1,
            },
        )


@pytest.mark.parametrize("max_results", [True, 1.5, "1", None])
def test_decode_search_request_payload_rejects_invalid_max_results_types(
    max_results: object,
) -> None:
    with pytest.raises(TypeError, match="max_results"):
        decode_search_request_payload(
            payload={
                "requirements": [],
                "max_results": max_results,
            },
        )


def test_decode_search_request_payload_rejects_negative_max_results() -> None:
    with pytest.raises(ValueError, match="max_results"):
        decode_search_request_payload(
            payload={
                "requirements": [],
                "max_results": -1,
            },
        )


def test_search_request_scope_regression() -> None:
    import mhwilds_skill_sim.api as api
    import mhwilds_skill_sim.api.search_request as search_request

    for name in ("SolverResult", "BuildResult"):
        assert not hasattr(api, name)
        assert not hasattr(search_request, name)

    source = Path(search_request.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    assert "fastapi" not in lowered_source
    assert "pydantic" not in lowered_source
    assert "router" not in lowered_source
    assert "search_catalog_build_candidates" not in source
    assert "search_limited_catalog_build_candidates" not in source
    assert "build_candidate_to_response" not in source
    assert "build_candidate_search_result_to_response" not in source
