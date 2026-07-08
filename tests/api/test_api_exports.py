from pathlib import Path

import mhwilds_skill_sim.api as api
from mhwilds_skill_sim.api.search_request import (
    SearchRequest,
    decode_search_request_payload,
)
from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response,
    build_candidate_to_response,
)


EXPECTED_API_ALL = [
    "SearchRequest",
    "build_candidate_search_result_to_response",
    "build_candidate_to_response",
    "decode_search_request_payload",
]


def test_api_all_is_plain_list_in_expected_order() -> None:
    assert type(api.__all__) is list
    assert api.__all__ == EXPECTED_API_ALL


def test_api_exports_are_direct_references() -> None:
    assert api.SearchRequest is SearchRequest
    assert api.decode_search_request_payload is decode_search_request_payload
    assert api.build_candidate_to_response is build_candidate_to_response
    assert (
        api.build_candidate_search_result_to_response
        is build_candidate_search_result_to_response
    )


def test_api_hasattr_reflects_public_exports() -> None:
    assert hasattr(api, "SearchRequest") is True
    assert hasattr(api, "decode_search_request_payload") is True
    assert hasattr(api, "__task_034_missing_export__") is False


def test_api_does_not_export_solver_result_types() -> None:
    assert not hasattr(api, "SolverResult")
    assert not hasattr(api, "BuildResult")


def test_api_init_has_no_compatibility_shims_or_web_frameworks() -> None:
    source = Path(api.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    assert "linecache" not in source
    assert "sys._getframe" not in source
    assert "_ApiAll" not in source
    assert "_called_from_hasattr" not in source
    assert "def __getattr__" not in source
    assert "fastapi" not in lowered_source
    assert "pydantic" not in lowered_source
    assert "router" not in lowered_source
    assert "endpoint" not in lowered_source
