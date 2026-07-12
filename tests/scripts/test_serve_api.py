from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

import scripts.serve_api as script_module
from mhwilds_skill_sim.catalog.model import Catalog
from scripts.serve_api import main, serve_catalog_api

ROOT = Path(__file__).resolve().parents[2]


def empty_catalog() -> Catalog:
    return Catalog(
        schema_version=1,
        equipment=(),
        decorations=(),
    )


def test_serve_catalog_api_requires_keyword_arguments_and_has_exact_defaults() -> None:
    signature = inspect.signature(serve_catalog_api)

    assert list(signature.parameters) == ["catalog_path", "host", "port"]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert signature.parameters["host"].default == "127.0.0.1"
    assert signature.parameters["port"].default == 8000
    with pytest.raises(TypeError):
        serve_catalog_api(Path("catalog.json"))  # type: ignore[misc]


def test_serve_catalog_api_loads_creates_and_runs_in_order_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = Path("requested/catalog.json")
    catalog = empty_catalog()
    application = object()
    calls: list[tuple[object, ...]] = []

    def fake_load_catalog(*, path: Path) -> Catalog:
        calls.append(("load", path))
        return catalog

    def fake_create_app(*, catalog: Catalog) -> object:
        calls.append(("create", catalog))
        return application

    def fake_run(app: object, *, host: str, port: int) -> None:
        calls.append(("run", app, host, port))

    monkeypatch.setattr(script_module, "load_catalog", fake_load_catalog)
    monkeypatch.setattr(script_module, "create_app", fake_create_app)
    monkeypatch.setattr(script_module.uvicorn, "run", fake_run)

    result = serve_catalog_api(catalog_path=catalog_path)

    assert result is None
    assert calls == [
        ("load", catalog_path),
        ("create", catalog),
        ("run", application, "127.0.0.1", 8000),
    ]


def test_serve_catalog_api_passes_explicit_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = Path("catalog.json")
    catalog = empty_catalog()
    application = object()
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(script_module, "load_catalog", lambda *, path: catalog)
    monkeypatch.setattr(
        script_module,
        "create_app",
        lambda *, catalog: application,
    )

    def fake_run(app: object, *, host: str, port: int) -> None:
        calls.append((app, host, port))

    monkeypatch.setattr(script_module.uvicorn, "run", fake_run)

    serve_catalog_api(
        catalog_path=catalog_path,
        host="0.0.0.0",
        port=4321,
    )

    assert calls == [(application, "0.0.0.0", 4321)]


def test_serve_catalog_api_preserves_catalog_identity_with_real_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = empty_catalog()
    applications: list[object] = []

    monkeypatch.setattr(
        script_module,
        "load_catalog",
        lambda *, path: catalog,
    )
    monkeypatch.setattr(
        script_module.uvicorn,
        "run",
        lambda application, **kwargs: applications.append(application),
    )

    serve_catalog_api(catalog_path=Path("catalog.json"))

    assert len(applications) == 1
    assert applications[0].state.catalog is catalog


@pytest.mark.parametrize("catalog_path", [None, "catalog.json", 1, object()])
def test_serve_catalog_api_rejects_invalid_catalog_path(
    catalog_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        script_module,
        "load_catalog",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(
        script_module.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(TypeError, match="catalog_path"):
        serve_catalog_api(catalog_path=catalog_path)  # type: ignore[arg-type]

    assert calls == []


class HostSubclass(str):
    pass


@pytest.mark.parametrize("host", [None, 1, True, Path("localhost"), HostSubclass("x")])
def test_serve_catalog_api_rejects_invalid_host_types(
    host: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        script_module,
        "load_catalog",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(TypeError, match="host"):
        serve_catalog_api(  # type: ignore[arg-type]
            catalog_path=Path("catalog.json"),
            host=host,
        )

    assert calls == []


@pytest.mark.parametrize("host", ["", " ", "\t", " localhost", "localhost "])
def test_serve_catalog_api_rejects_invalid_host_text(
    host: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        script_module,
        "load_catalog",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(ValueError, match="host"):
        serve_catalog_api(catalog_path=Path("catalog.json"), host=host)

    assert calls == []


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0", "localhost"])
def test_serve_catalog_api_accepts_supported_host_text_without_normalizing(
    host: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = empty_catalog()
    calls: list[tuple[object, str, int]] = []
    monkeypatch.setattr(script_module, "load_catalog", lambda **kwargs: catalog)
    monkeypatch.setattr(script_module, "create_app", lambda **kwargs: object())
    monkeypatch.setattr(
        script_module.uvicorn,
        "run",
        lambda app, *, host, port: calls.append((app, host, port)),
    )

    serve_catalog_api(catalog_path=Path("catalog.json"), host=host)

    assert len(calls) == 1
    assert calls[0][1:] == (host, 8000)


@pytest.mark.parametrize("port", [None, "8000", 1.0, True, False])
def test_serve_catalog_api_rejects_invalid_port_types(
    port: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        script_module,
        "load_catalog",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(TypeError, match="port"):
        serve_catalog_api(  # type: ignore[arg-type]
            catalog_path=Path("catalog.json"),
            port=port,
        )

    assert calls == []


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_serve_catalog_api_rejects_out_of_range_ports(
    port: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        script_module,
        "load_catalog",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(ValueError, match="port"):
        serve_catalog_api(catalog_path=Path("catalog.json"), port=port)

    assert calls == []


def test_serve_catalog_api_propagates_load_error_without_creating_or_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RuntimeError("load failed")
    calls: list[object] = []

    def fail_load(*, path: Path) -> Catalog:
        calls.append(("load", path))
        raise error

    monkeypatch.setattr(script_module, "load_catalog", fail_load)
    monkeypatch.setattr(
        script_module,
        "create_app",
        lambda **kwargs: calls.append(("create", kwargs)),
    )
    monkeypatch.setattr(
        script_module.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append(("run", args, kwargs)),
    )

    with pytest.raises(RuntimeError) as exc_info:
        serve_catalog_api(catalog_path=Path("catalog.json"))

    assert exc_info.value is error
    assert calls == [("load", Path("catalog.json"))]


def test_serve_catalog_api_propagates_factory_error_without_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RuntimeError("factory failed")
    catalog = empty_catalog()
    calls: list[object] = []

    def fail_create_app(*, catalog: Catalog) -> object:
        calls.append(("create", catalog))
        raise error

    monkeypatch.setattr(script_module, "load_catalog", lambda **kwargs: catalog)
    monkeypatch.setattr(script_module, "create_app", fail_create_app)
    monkeypatch.setattr(
        script_module.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append(("run", args, kwargs)),
    )

    with pytest.raises(RuntimeError) as exc_info:
        serve_catalog_api(catalog_path=Path("catalog.json"))

    assert exc_info.value is error
    assert calls == [("create", catalog)]


def test_serve_catalog_api_propagates_uvicorn_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RuntimeError("server failed")
    catalog = empty_catalog()
    application = object()

    monkeypatch.setattr(script_module, "load_catalog", lambda **kwargs: catalog)
    monkeypatch.setattr(script_module, "create_app", lambda **kwargs: application)

    def fail_run(app: object, *, host: str, port: int) -> None:
        assert app is application
        assert host == "127.0.0.1"
        assert port == 8000
        raise error

    monkeypatch.setattr(script_module.uvicorn, "run", fail_run)

    with pytest.raises(RuntimeError) as exc_info:
        serve_catalog_api(catalog_path=Path("catalog.json"))

    assert exc_info.value is error


def test_main_passes_path_and_defaults_to_serving_function_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        script_module,
        "serve_catalog_api",
        lambda **kwargs: calls.append(kwargs),
    )

    result = main(["nested/catalog.json"])

    assert result == 0
    assert calls == [
        {
            "catalog_path": Path("nested/catalog.json"),
            "host": "127.0.0.1",
            "port": 8000,
        }
    ]


def test_main_passes_explicit_host_and_integer_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        script_module,
        "serve_catalog_api",
        lambda **kwargs: calls.append(kwargs),
    )

    result = main(["catalog.json", "--host", "localhost", "--port", "65535"])

    assert result == 0
    assert calls == [
        {
            "catalog_path": Path("catalog.json"),
            "host": "localhost",
            "port": 65535,
        }
    ]


def test_script_uses_no_other_network_client_test_client_or_file_writes() -> None:
    source = (ROOT / "scripts" / "serve_api.py").read_text(encoding="utf-8")
    lowered = source.lower()

    assert "import uvicorn" in source
    for forbidden in (
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "socket",
        "testclient",
        "write_text",
        "write_bytes",
        ".write(",
        ".open(",
        "os.environ",
    ):
        assert forbidden not in lowered


def test_importing_script_performs_no_serving_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_module = importlib.import_module("mhwilds_skill_sim.api.app")
    loader_module = importlib.import_module("mhwilds_skill_sim.catalog.loader")
    calls: list[tuple[object, ...]] = []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("import must not load a catalog or start a server")

    with monkeypatch.context() as patch:
        patch.setattr(loader_module, "load_catalog", fail_if_called)
        patch.setattr(app_module, "create_app", fail_if_called)
        patch.setattr(script_module.uvicorn, "run", fail_if_called)

        reloaded = importlib.reload(script_module)

        assert reloaded is script_module
        assert calls == []

    importlib.reload(script_module)
