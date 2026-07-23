from __future__ import annotations

import gzip
import importlib
import inspect
import json
from pathlib import Path
from types import ModuleType

import pytest

import scripts.export_browser_solver_catalog as export_script_module
import scripts.profile_browser_solver_oracle as oracle_script_module
import scripts.validate_browser_solver_report as validator_script_module
from mhwilds_skill_sim.browser.catalog_export import BrowserCatalogSizeError
from scripts.export_browser_solver_catalog import (
    export_browser_solver_catalog,
    main,
)


ROOT = Path(__file__).resolve().parents[2]
TINY_CATALOG_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"
SCRIPT_MODULES = (
    export_script_module,
    oracle_script_module,
    validator_script_module,
)
SCRIPT_PATHS = tuple(
    ROOT / "scripts" / f"{module.__name__.rsplit('.', maxsplit=1)[-1]}.py"
    for module in SCRIPT_MODULES
)


def test_export_function_has_keyword_only_signature() -> None:
    signature = inspect.signature(export_browser_solver_catalog)
    assert tuple(signature.parameters) == (
        "catalog_path",
        "output_path",
        "maximum_expanded_equipment",
        "pretty",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


@pytest.mark.parametrize("pretty", [False, True])
def test_export_cli_function_writes_catalog_and_exact_size_summary(
    pretty: bool,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "nested" / "browser-catalog.json"

    summary = export_browser_solver_catalog(
        catalog_path=TINY_CATALOG_PATH,
        output_path=output_path,
        pretty=pretty,
    )
    output_bytes = output_path.read_bytes()
    value = json.loads(output_bytes)

    assert output_bytes.endswith(b"\n")
    assert summary["raw_bytes"] == len(output_bytes)
    assert summary["gzip_bytes"] == len(gzip.compress(output_bytes, mtime=0))
    assert summary["expanded_equipment_count"] == 17
    assert summary["part_counts"] == {
        "weapon": 1,
        "head": 2,
        "chest": 1,
        "arms": 1,
        "waist": 1,
        "legs": 1,
        "charm": 10,
    }
    assert value["source_catalog"]["sha256"] == summary["source_sha256"]
    if pretty:
        assert b'\n  "source_catalog"' in output_bytes
    else:
        assert b"\n" not in output_bytes[:-1]


def test_export_limit_error_does_not_create_output(tmp_path: Path) -> None:
    output_path = tmp_path / "browser-catalog.json"

    with pytest.raises(BrowserCatalogSizeError):
        export_browser_solver_catalog(
            catalog_path=TINY_CATALOG_PATH,
            output_path=output_path,
            maximum_expanded_equipment=16,
        )

    assert not output_path.exists()


def test_export_refuses_to_overwrite_source_catalog() -> None:
    before = TINY_CATALOG_PATH.read_bytes()

    with pytest.raises(ValueError, match="overwrite catalog_path"):
        export_browser_solver_catalog(
            catalog_path=TINY_CATALOG_PATH,
            output_path=TINY_CATALOG_PATH,
        )

    assert TINY_CATALOG_PATH.read_bytes() == before


def test_main_prints_summary_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "browser-catalog.json"

    exit_code = main([str(TINY_CATALOG_PATH), str(output_path)])

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert exit_code == 0
    assert summary["raw_bytes"] == output_path.stat().st_size
    assert "equipment_by_part" not in summary


@pytest.mark.parametrize(
    "script_path",
    SCRIPT_PATHS,
    ids=lambda path: path.stem,
)
def test_browser_solver_cli_has_no_network_dependencies(script_path: Path) -> None:
    lowered = script_path.read_text(encoding="utf-8").lower()

    for forbidden in (
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "socket",
        "fetch(",
    ):
        assert forbidden not in lowered


@pytest.mark.parametrize(
    "script_module",
    SCRIPT_MODULES,
    ids=lambda module: module.__name__.rsplit(".", maxsplit=1)[-1],
)
def test_importing_browser_solver_cli_performs_no_file_work(
    script_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    def record_and_fail(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("import must not read or generate files")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", record_and_fail)
            patch.setattr(Path, "read_bytes", record_and_fail)
            patch.setattr(Path, "write_bytes", record_and_fail)
            patch.setattr(Path, "mkdir", record_and_fail)

            reloaded = importlib.reload(script_module)

            assert reloaded is script_module
            assert calls == []
    finally:
        importlib.reload(script_module)


def test_generated_benchmark_artifacts_are_covered_by_build_ignore() -> None:
    ignored_entries = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    generated_paths = tuple(
        ROOT / ".build" / "browser-solver" / name
        for name in (
            "browser-catalog.json",
            "oracle.json",
            "node-report.json",
            "tiny-browser-catalog.json",
            "tiny-oracle.json",
            "tiny-browser-report.json",
            "live-catalog.json",
        )
    )

    assert ".build/" in ignored_entries
    assert all(
        path.relative_to(ROOT).parts[:2] == (".build", "browser-solver")
        for path in generated_paths
    )
