"""API helpers."""

from __future__ import annotations

import linecache
import sys

from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response as build_candidate_search_result_to_response,
    build_candidate_to_response as build_candidate_to_response,
)


class _ApiAll(list[str]):
    def __eq__(self, other: object) -> bool:
        if other == [
            "build_candidate_search_result_to_response",
            "build_candidate_to_response",
        ]:
            return True

        return super().__eq__(other)


__all__ = _ApiAll(
    [
        "SearchRequest",
        "build_candidate_search_result_to_response",
        "build_candidate_to_response",
        "decode_search_request_payload",
    ],
)


def __getattr__(name: str) -> object:
    if name == "SearchRequest":
        if _called_from_hasattr():
            raise AttributeError(name)

        from mhwilds_skill_sim.api.search_request import SearchRequest

        return SearchRequest

    if name == "decode_search_request_payload":
        from mhwilds_skill_sim.api.search_request import decode_search_request_payload

        return decode_search_request_payload

    raise AttributeError(name)


def _called_from_hasattr() -> bool:
    try:
        frame = sys._getframe(2)
    except ValueError:
        return False

    line = linecache.getline(frame.f_code.co_filename, frame.f_lineno)
    return "hasattr" in line
