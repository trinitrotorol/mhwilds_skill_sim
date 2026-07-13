"""FastAPI application factory."""

from __future__ import annotations

from fastapi import Body, FastAPI, HTTPException, Request

from mhwilds_skill_sim.api.catalog_response import (
    build_catalog_metadata_response,
)
from mhwilds_skill_sim.api.search_service import (
    search_catalog_build_candidates_from_payload,
    search_catalog_build_candidates_with_cp_sat_from_payload,
)
from mhwilds_skill_sim.catalog.model import Catalog


def _catalog_from_request(*, request: Request) -> Catalog:
    catalog = getattr(request.app.state, "catalog", None)
    if not isinstance(catalog, Catalog):
        raise HTTPException(
            status_code=503,
            detail="catalog is not configured",
        )

    return catalog


def create_app(
    *,
    catalog: Catalog | None = None,
) -> FastAPI:
    if catalog is not None and not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog or None")

    api_app = FastAPI(title="mhwilds-skill-sim")
    if catalog is not None:
        api_app.state.catalog = catalog

    @api_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api_app.get("/catalog/metadata")
    def catalog_metadata(request: Request) -> dict[str, object]:
        catalog = _catalog_from_request(request=request)
        return build_catalog_metadata_response(catalog=catalog)

    @api_app.post("/search")
    def search(
        request: Request,
        payload: object = Body(...),
    ) -> dict[str, object]:
        catalog = _catalog_from_request(request=request)
        return search_catalog_build_candidates_from_payload(
            catalog=catalog,
            payload=payload,
        )

    @api_app.post("/search/cp-sat")
    def search_cp_sat(
        request: Request,
        payload: object = Body(...),
    ) -> dict[str, object]:
        catalog = _catalog_from_request(request=request)
        return search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=catalog,
            payload=payload,
        )

    return api_app


app = create_app()
