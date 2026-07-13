from __future__ import annotations

import asyncio
import copy
import importlib
import inspect
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException

from mhwilds_skill_sim.api.app import app, create_app
from mhwilds_skill_sim.api.catalog_response import (
    build_catalog_metadata_response,
)
from mhwilds_skill_sim.api.search_service import (
    search_catalog_build_candidates_from_payload,
    search_catalog_build_candidates_with_cp_sat_from_payload,
)
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


def empty_catalog() -> Catalog:
    return Catalog(schema_version=1, equipment=(), decorations=())


def valid_search_payload(max_results: int = 1) -> dict[str, object]:
    return {
        "requirements": [],
        "max_results": max_results,
    }


def test_project_dependencies_include_fastapi_runtime_dependency() -> None:
    dependencies = project_dependencies()

    assert "fastapi>=0.115,<1" in dependencies


def test_project_dependencies_include_uvicorn_runtime_dependency() -> None:
    dependencies = project_dependencies()

    assert "uvicorn>=0.51,<1" in dependencies


def test_project_dependencies_do_not_add_client_or_model_dependencies() -> None:
    names = dependency_names(project_dependencies())

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


def test_create_app_has_exact_catalog_keyword_only_signature() -> None:
    signature = inspect.signature(create_app)
    parameters = signature.parameters

    assert list(parameters) == ["catalog"]
    assert parameters["catalog"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["catalog"].default is None
    assert isinstance(create_app(), FastAPI)


def test_create_app_rejects_positional_catalog() -> None:
    with pytest.raises(TypeError):
        create_app(tiny_catalog())  # type: ignore[call-arg]


def test_create_app_stores_exact_injected_catalog() -> None:
    catalog = tiny_catalog()

    application = create_app(catalog=catalog)

    assert application.state.catalog is catalog


def test_create_app_accepts_catalog_subclass() -> None:
    class CatalogSubclass(Catalog):
        pass

    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())

    application = create_app(catalog=catalog)

    assert application.state.catalog is catalog


@pytest.mark.parametrize(
    "invalid_catalog",
    [object(), "catalog", 0, True, SimpleNamespace()],
)
def test_create_app_rejects_invalid_catalog_values(invalid_catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        create_app(catalog=invalid_catalog)  # type: ignore[arg-type]


def test_create_app_without_catalog_does_not_create_catalog_state() -> None:
    application = create_app()

    assert not hasattr(application.state, "catalog")


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


def test_catalog_metadata_route_is_get_only_without_request_body() -> None:
    application = create_app()
    route = route_for_path(application, "/catalog/metadata")
    operation = application.openapi()["paths"]["/catalog/metadata"]

    assert "GET" in route.methods
    assert "POST" not in route.methods
    assert route.body_field is None
    assert "get" in operation
    assert "post" not in operation
    assert "requestBody" not in operation["get"]


def test_catalog_metadata_endpoint_uses_injected_catalog() -> None:
    catalog = tiny_catalog()
    catalog_before = copy.deepcopy(catalog)
    application = create_app(catalog=catalog)
    route = route_for_path(application, "/catalog/metadata")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
    )

    assert isinstance(response, dict)
    assert response == build_catalog_metadata_response(catalog=catalog)
    json.dumps(response)
    assert application.state.catalog is catalog
    assert catalog == catalog_before


def test_catalog_metadata_endpoint_uses_manually_assigned_catalog() -> None:
    catalog = tiny_catalog()
    application = create_app()
    application.state.catalog = catalog
    route = route_for_path(application, "/catalog/metadata")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
    )

    assert response == build_catalog_metadata_response(catalog=catalog)


def test_catalog_metadata_endpoint_accepts_catalog_subclass() -> None:
    class CatalogSubclass(Catalog):
        pass

    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())
    application = create_app(catalog=catalog)
    route = route_for_path(application, "/catalog/metadata")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
    )

    assert response == build_catalog_metadata_response(catalog=catalog)


def test_catalog_metadata_endpoint_stays_read_only() -> None:
    route = route_for_path(create_app(), "/catalog/metadata")
    source = inspect.getsource(route.endpoint).lower()

    for forbidden in (
        "load_catalog",
        "synchroniz",
        "search_catalog",
        "solver",
        "pathlib",
        "read_text",
        "read_bytes",
        "open(",
    ):
        assert forbidden not in source


@pytest.mark.parametrize(
    "configure_invalid_catalog",
    [False, True],
    ids=["missing", "invalid"],
)
def test_catalog_metadata_catalog_errors_exactly_match_search(
    configure_invalid_catalog: bool,
) -> None:
    application = create_app()
    if configure_invalid_catalog:
        application.state.catalog = "catalog"

    metadata_route = route_for_path(application, "/catalog/metadata")
    search_route = route_for_path(application, "/search")

    with pytest.raises(HTTPException) as metadata_exc_info:
        call_route_endpoint(
            metadata_route,
            request=fake_request(application),
        )
    with pytest.raises(HTTPException) as search_exc_info:
        call_route_endpoint(
            search_route,
            request=fake_request(application),
            payload=valid_search_payload(),
        )

    assert metadata_exc_info.value.status_code == 503
    assert metadata_exc_info.value.detail == "catalog is not configured"
    assert search_exc_info.value.status_code == metadata_exc_info.value.status_code
    assert search_exc_info.value.detail == metadata_exc_info.value.detail


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


def test_search_endpoint_uses_injected_catalog() -> None:
    catalog = tiny_catalog()
    payload = valid_search_payload()
    application = create_app(catalog=catalog)
    route = route_for_path(application, "/search")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
        payload=payload,
    )

    assert application.state.catalog is catalog
    assert response == search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload,
    )


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


def test_cp_sat_search_route_is_post_only_with_required_openapi_body() -> None:
    application = create_app()
    route = route_for_path(application, "/search/cp-sat")
    operation = application.openapi()["paths"]["/search/cp-sat"]

    assert route.methods == {"POST"}
    assert route.body_field is not None
    assert "post" in operation
    assert "get" not in operation
    request_body = operation["post"]["requestBody"]
    assert request_body["required"] is True
    assert "application/json" in request_body["content"]


def test_cp_sat_search_endpoint_returns_serializable_response_from_state_catalog() -> (
    None
):
    application = create_app()
    catalog = empty_catalog()
    payload = valid_search_payload()
    catalog_before = copy.deepcopy(catalog)
    payload_before = copy.deepcopy(payload)
    application.state.catalog = catalog
    route = route_for_path(application, "/search/cp-sat")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
        payload=payload,
    )

    assert isinstance(response, dict)
    assert list(response) == ["candidates", "exhausted", "timed_out"]
    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }
    assert "total_count" not in response
    assert "truncated" not in response
    json.dumps(response)
    assert response == search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload,
    )
    assert catalog == catalog_before
    assert payload == payload_before


def test_cp_sat_search_endpoint_uses_injected_catalog() -> None:
    catalog = empty_catalog()
    payload = valid_search_payload()
    application = create_app(catalog=catalog)
    route = route_for_path(application, "/search/cp-sat")

    response = call_route_endpoint(
        route,
        request=fake_request(application),
        payload=payload,
    )

    assert application.state.catalog is catalog
    assert response == search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload,
    )


@pytest.mark.parametrize(
    "use_module_level_app",
    [False, True],
    ids=["factory-app", "module-level-app"],
)
@pytest.mark.parametrize(
    "configure_invalid_catalog",
    [False, True],
    ids=["missing", "invalid"],
)
def test_cp_sat_search_catalog_errors_exactly_match_existing_search(
    monkeypatch: pytest.MonkeyPatch,
    use_module_level_app: bool,
    configure_invalid_catalog: bool,
) -> None:
    application = app if use_module_level_app else create_app()
    assert not hasattr(application.state, "catalog")
    if configure_invalid_catalog:
        monkeypatch.setattr(
            application.state,
            "catalog",
            "catalog",
            raising=False,
        )

    cp_sat_route = route_for_path(application, "/search/cp-sat")
    search_route = route_for_path(application, "/search")

    with pytest.raises(HTTPException) as cp_sat_exc_info:
        call_route_endpoint(
            cp_sat_route,
            request=fake_request(application),
            payload=valid_search_payload(),
        )
    with pytest.raises(HTTPException) as search_exc_info:
        call_route_endpoint(
            search_route,
            request=fake_request(application),
            payload=valid_search_payload(),
        )

    assert cp_sat_exc_info.value.status_code == 503
    assert cp_sat_exc_info.value.detail == "catalog is not configured"
    assert cp_sat_exc_info.value.status_code == search_exc_info.value.status_code
    assert cp_sat_exc_info.value.detail == search_exc_info.value.detail


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
def test_cp_sat_search_endpoint_propagates_payload_validation_errors(
    payload: object,
    expected_error: type[Exception],
) -> None:
    application = create_app(catalog=empty_catalog())
    route = route_for_path(application, "/search/cp-sat")

    with pytest.raises(expected_error):
        call_route_endpoint(
            route,
            request=fake_request(application),
            payload=payload,
        )


def test_cp_sat_search_route_preserves_existing_route_contracts() -> None:
    catalog = empty_catalog()
    application = create_app(catalog=catalog)
    schema = application.openapi()

    health_response = call_route_endpoint(route_for_path(application, "/health"))
    metadata_response = call_route_endpoint(
        route_for_path(application, "/catalog/metadata"),
        request=fake_request(application),
    )
    search_response = call_route_endpoint(
        route_for_path(application, "/search"),
        request=fake_request(application),
        payload=valid_search_payload(),
    )

    assert health_response == {"status": "ok"}
    assert metadata_response == build_catalog_metadata_response(catalog=catalog)
    assert search_response == {
        "candidates": [],
        "total_count": 0,
        "truncated": False,
    }
    assert list(search_response) == ["candidates", "total_count", "truncated"]
    assert "get" in schema["paths"]["/health"]
    assert "post" not in schema["paths"]["/health"]
    assert "get" in schema["paths"]["/catalog/metadata"]
    assert "post" not in schema["paths"]["/catalog/metadata"]
    assert "post" in schema["paths"]["/search"]
    assert "get" not in schema["paths"]["/search"]


def test_create_app_state_is_isolated_between_instances() -> None:
    first = create_app()
    second = create_app()

    first.state.catalog = tiny_catalog()

    assert hasattr(first.state, "catalog")
    assert not hasattr(second.state, "catalog")


def test_injected_and_non_injected_app_state_is_independent() -> None:
    catalog = tiny_catalog()
    injected = create_app(catalog=catalog)
    non_injected = create_app()

    assert injected.state.catalog is catalog
    assert not hasattr(non_injected.state, "catalog")


def test_two_injected_apps_retain_their_respective_catalogs() -> None:
    first_catalog = tiny_catalog()
    second_catalog = Catalog(schema_version=1, equipment=(), decorations=())

    first = create_app(catalog=first_catalog)
    second = create_app(catalog=second_catalog)

    assert first_catalog is not second_catalog
    assert first.state.catalog is first_catalog
    assert second.state.catalog is second_catalog


def test_injected_catalog_does_not_change_health_or_openapi_behavior() -> None:
    application = create_app(catalog=tiny_catalog())
    health_route = route_for_path(application, "/health")
    schema = application.openapi()

    assert call_route_endpoint(health_route) == {"status": "ok"}
    assert "get" in schema["paths"]["/health"]
    assert "post" in schema["paths"]["/search"]


def test_module_level_app_has_no_catalog_configured() -> None:
    assert not hasattr(app.state, "catalog")

    search_route = route_for_path(app, "/search")
    with pytest.raises(HTTPException) as search_exc_info:
        call_route_endpoint(
            search_route,
            request=fake_request(app),
            payload=valid_search_payload(),
        )

    metadata_route = route_for_path(app, "/catalog/metadata")
    with pytest.raises(HTTPException) as metadata_exc_info:
        call_route_endpoint(
            metadata_route,
            request=fake_request(app),
        )

    assert search_exc_info.value.status_code == 503
    assert search_exc_info.value.detail == "catalog is not configured"
    assert metadata_exc_info.value.status_code == 503
    assert metadata_exc_info.value.detail == "catalog is not configured"


def test_app_source_stays_minimal() -> None:
    source = Path(app_module.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    assert "load_catalog" not in source
    assert "uvicorn" not in lowered_source
    assert "os.environ" not in source
    assert "getenv" not in lowered_source
    assert "pathlib" not in lowered_source
    assert "read_text" not in lowered_source
    assert "read_bytes" not in lowered_source
    assert "open(" not in lowered_source
    assert "basemodel" not in lowered_source
    assert "pydantic" not in lowered_source
    assert "APIRouter" not in source
    assert "Depends" not in source
    assert "CORSMiddleware" not in source
    assert "StaticFiles" not in source
    assert "middleware" not in lowered_source
    assert "React" not in source
    assert "TestClient" not in source
