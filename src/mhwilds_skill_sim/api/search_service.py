"""API search service composition."""

from __future__ import annotations

from mhwilds_skill_sim.api.search_request import decode_search_request_payload
from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response,
    build_cp_sat_search_result_to_response,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.solver.cp_sat_search import (
    search_catalog_build_candidates_with_cp_sat,
)
from mhwilds_skill_sim.solver.search_result import (
    search_limited_catalog_build_candidates_by_skill_requirements,
)


_CP_SAT_SEARCH_TIMEOUT_SECONDS = 10.0


def search_catalog_build_candidates_from_payload(
    *,
    catalog: Catalog,
    payload: object,
) -> dict[str, object]:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")

    request = decode_search_request_payload(payload=payload)
    result = search_limited_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=request.requirements,
        max_results=request.max_results,
        weapon_kind=request.weapon_kind,
    )
    return build_candidate_search_result_to_response(result=result)


def search_catalog_build_candidates_with_cp_sat_from_payload(
    *,
    catalog: Catalog,
    payload: object,
) -> dict[str, object]:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")

    request = decode_search_request_payload(payload=payload)
    result = search_catalog_build_candidates_with_cp_sat(
        catalog=catalog,
        requirements=request.requirements,
        max_results=request.max_results,
        weapon_kind=request.weapon_kind,
        timeout_seconds=_CP_SAT_SEARCH_TIMEOUT_SECONDS,
    )
    return build_cp_sat_search_result_to_response(result=result)
