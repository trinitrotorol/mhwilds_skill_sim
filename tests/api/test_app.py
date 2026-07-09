from __future__ import annotations

import asyncio
import importlib
import inspect
import tomllib
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from mhwilds_skill_sim.api.app import app, create_app


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT / "pyproject.toml"
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


def call_route_endpoint(route: Any) -> object:
    value = route.endpoint()
    if inspect.isawaitable(value):
        return asyncio.run(value)

    return value


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


def test_no_search_route_exists() -> None:
    paths = {getattr(route, "path", None) for route in create_app().routes}

    assert "/search" not in paths


def test_app_source_stays_minimal() -> None:
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    assert "search_catalog_build_candidates_from_payload" not in source
    assert "load_catalog" not in source
    assert "basemodel" not in lowered_source
    assert "pydantic" not in lowered_source
    assert "APIRouter" not in source
    assert "CORSMiddleware" not in source
    assert "StaticFiles" not in source
    assert "React" not in source
