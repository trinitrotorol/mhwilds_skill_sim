"""FastAPI application factory."""

from __future__ import annotations

from fastapi import Body, FastAPI, HTTPException, Request

from mhwilds_skill_sim.api.search_service import (
    search_catalog_build_candidates_from_payload,
)
from mhwilds_skill_sim.catalog.model import Catalog


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

    @api_app.post("/search")
    def search(
        request: Request,
        payload: object = Body(...),
    ) -> dict[str, object]:
        catalog = getattr(request.app.state, "catalog", None)
        if not isinstance(catalog, Catalog):
            raise HTTPException(
                status_code=503,
                detail="catalog is not configured",
            )

        return search_catalog_build_candidates_from_payload(
            catalog=catalog,
            payload=payload,
        )

    return api_app


app = create_app()
