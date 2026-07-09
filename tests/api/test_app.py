from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException

from mhwilds_skill_sim.api.search_service import (
    search_catalog_build_candidates_from_payload,
)
from mhwilds_skill_sim.api.app import app, create_app
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.model import Catalog


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT / "pyproject.toml"
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"
app_module = importlib.import_module("mhwilds_skill_sim.api.app")


def project_dependencies() -> list[str]:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return pyproject["project"]["dependencies"]


def dependency_names(dependencies: list[str]) -> set[str]:
    names: set[str] = set()
    for dependency in dependencies:
        normalized = dependency.lower()
        name = (
            normalized.split("<", 1)[0]
            .split(">", 1)[0]
            .split("=", 1)[0]
            .split("[", 1)[0]
            .strip()
        )
        names.add(name)
    return names


def route_for_path(application: FastAPI, path: str) -> Any:
    for route in application.routes:
        if getattr(route, "path", None) == path:
            return route

    raise AssertionError(f"route not found: {path}")


def call_route_endpoint(route: Any, **kwargs: object) -> object:
    value = route.endpoint(**kwargs)
    if inspect.isawaitable(value):
        return asyncio.run(value)

    return value


def fake_request(application: FastAPI) -> SimpleNamespace:
    return SimpleNamespace(app=application)


def tiny_catalog() -> Catalog:
    return load_catalog(path=FIXTURE_PATH)


def valid_search_payload(max_results: int = 1) -> dict[str, object]:
    return {
        "requirements": [],
        "max_results": max_results,
    }


def test_project_dependencies_include_fastapi_runtime_dependency() -> None:
    dependencies = project_dependencies()

    assert "fastapi>=0.115,<1" in dependencies


def test_project_dependencies_do_not_add_server_or_client_dependencies() -> None:
    names = dependency_names(project_dependencies())

    assert "uvicorn" not in names
    assert "httpx" not in names
    assert "pydantic" not in names


def test_create_app_returns_fastapi_instance() -> None:
    assert isinstance(create_app(), FastAPI)


def test_create_app_returns_new_instance_each_call() -> None:
    first = create_app()
    second = create_app()

    assert first is not second


def test_create_app_configures_title() -> None:
    assert create_app().title == "mhwilds-skill-sim"


def test_module_level_app_is_fastapi_instance() -> None:
    assert isinstance(app, FastAPI)
    assert app.title == "mhwilds-skill-sim"


def test_create_app_requires_no_arguments() -> None:
    signature = inspect.signature(create_app)

    assert signature.parameters == {}


def test_app_module_exports_create_app_and_app() -> None:
    assert app_module.create_app is create_app
    assert app_module.app is app


def test_api_package_exports_create_app_and_app() -> None:
    from mhwilds_skill_sim.api import app as exported_app
    from mhwilds_skill_sim.api import create_app as exported_create_app

    assert exported_create_app is create_app
    assert exported_app is app


def test_health_get_route_exists() -> None:
    route = route_for_path(create_app(), "/health")

    assert "GET" in route.methods


def test_health_endpoint_returns_status_ok() -> None:
    route = route_for_path(create_app(), "/health")

    assert call_route_endpoint(route) == {"status": "ok"}


def test_health_route_does_not_include_post() -> None:
    route = route_for_path(create_app(), "/health")

    assert "POST" not in route.methods


def test_health_route_is_in_openapi_schema() -> None:
    schema = create_app().openapi()

    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]


def test_search_post_route_exists() -> None:
    route = route_for_path(create_app(), "/search")

    assert "POST" in route.methods


def test_search_route_does_not_include_get() -> None:
    route = route_for_path(create_app(), "/search")

    assert "GET" not in route.methods


def test_search_route_is_in_openapi_schema() -> None:
    schema = create_app().openapi()

    assert "/search" in schema["paths"]
    assert "post" in schema["paths"]["/search"]


def test_search_endpoint_returns_serializable_response_from_state_catalog() -> None:
    application = create_app()
    catalog = tiny_catalog()
    payload = valid_search_payload()
    original_catalog = catalog
    original_payload = dict(payload)
    application.state.catalog = catalog
    route = route_for_path(application, "/search")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
        payload=payload,
    )

    assert isinstance(response, dict)
    assert list(response) == ["candidates", "total_count", "truncated"]
    assert len(response["candidates"]) == 1  # type: ignore[arg-type]
    json.dumps(response)
    assert response == search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload,
    )
    assert catalog == original_catalog
    assert payload == original_payload


def test_search_endpoint_raises_503_when_catalog_is_missing() -> None:
    application = create_app()
    route = route_for_path(application, "/search")

    with pytest.raises(HTTPException) as exc_info:
        call_route_endpoint(
            route,
            request=fake_request(application),
            payload=valid_search_payload(),
        )

    assert exc_info.value.status_code == 503
    assert "catalog" in exc_info.value.detail
    assert "configured" in exc_info.value.detail


def test_search_endpoint_raises_503_when_catalog_is_invalid() -> None:
    application = create_app()
    application.state.catalog = "catalog"
    route = route_for_path(application, "/search")

    with pytest.raises(HTTPException) as exc_info:
        call_route_endpoint(
            route,
            request=fake_request(application),
            payload=valid_search_payload(),
        )

    assert exc_info.value.status_code == 503
    assert "catalog" in exc_info.value.detail


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ([], TypeError),
        (
            {
                "requirements": [
                    {"skill_id": "skill:attack-boost", "min_level": 1},
                    {"skill_id": "skill:attack-boost", "min_level": 2},
                ],
                "max_results": 1,
            },
            ValueError,
        ),
        ({"requirements": [], "max_results": "1"}, TypeError),
    ],
)
def test_search_endpoint_propagates_payload_validation_errors(
    payload: object,
    expected_error: type[Exception],
) -> None:
    application = create_app()
    application.state.catalog = tiny_catalog()
    route = route_for_path(application, "/search")

    with pytest.raises(expected_error):
        call_route_endpoint(
            route,
            request=fake_request(application),
            payload=payload,
        )


def test_create_app_state_is_isolated_between_instances() -> None:
    first = create_app()
    second = create_app()

    first.state.catalog = tiny_catalog()

    assert hasattr(first.state, "catalog")
    assert not hasattr(second.state, "catalog")


def test_module_level_app_has_no_catalog_configured() -> None:
    assert not hasattr(app.state, "catalog")

    route = route_for_path(app, "/search")
    with pytest.raises(HTTPException) as exc_info:
        call_route_endpoint(
            route,
            request=fake_request(app),
            payload=valid_search_payload(),
        )

    assert exc_info.value.status_code == 503


def test_app_source_stays_minimal() -> None:
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    assert "load_catalog" not in source
    assert "os.environ" not in source
    assert "basemodel" not in lowered_source
    assert "pydantic" not in lowered_source
    assert "APIRouter" not in source
    assert "Depends" not in source
    assert "CORSMiddleware" not in source
    assert "StaticFiles" not in source
    assert "React" not in source
    assert "TestClient" not in source
