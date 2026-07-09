"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    api_app = FastAPI(title="mhwilds-skill-sim")

    @api_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return api_app


app = create_app()
