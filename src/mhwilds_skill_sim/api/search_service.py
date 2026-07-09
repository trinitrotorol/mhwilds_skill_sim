"""API search service composition."""

from __future__ import annotations

from mhwilds_skill_sim.api.search_request import decode_search_request_payload
from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.solver.search_result import (
    search_limited_catalog_build_candidates_by_skill_requirements,
)


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
    )
    return build_candidate_search_result_to_response(result=result)
