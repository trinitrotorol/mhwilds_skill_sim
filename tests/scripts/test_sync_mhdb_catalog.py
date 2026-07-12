from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import pytest

import mhwilds_skill_sim.catalog.mhdb_sync as sync_module
import scripts.sync_mhdb_catalog as script_module
from mhwilds_skill_sim.catalog.loader import load_catalog
from scripts.sync_mhdb_catalog import main, sync_files

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIRECTORY = ROOT / "data" / "fixtures"
SNAPSHOT_FIXTURES = {
    "skills": FIXTURE_DIRECTORY / "mhdb_skills_raw.json",
    "decorations": FIXTURE_DIRECTORY / "mhdb_decorations_raw.json",
    "armor_sets": FIXTURE_DIRECTORY / "mhdb_armor_sets_raw.json",
    "armor": FIXTURE_DIRECTORY / "mhdb_armor_raw.json",
    "weapons": FIXTURE_DIRECTORY / "mhdb_weapons_raw.json",
    "charms": FIXTURE_DIRECTORY / "mhdb_charms_raw.json",
}
RAW_FILENAMES = (
    "metadata.json",
    "skills.json",
    "decorations.json",
    "armor_sets.json",
    "armor.json",
    "weapons.json",
    "charms.json",
)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_bundle() -> dict[str, object]:
    return {
        "version": "2026.07.12-cli-test",
        "locale": "ja",
        **{key: load_json(path) for key, path in SNAPSHOT_FIXTURES.items()},
    }


def install_fixture_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, float]]:
    calls: list[tuple[str, float]] = []

    def fake_fetch_mhdb_snapshot_bundle(
        *,
        locale: str = "ja",
        timeout_seconds: float = 30.0,
    ) -> dict[str, object]:
        calls.append((locale, timeout_seconds))
        bundle = fixture_bundle()
        bundle["locale"] = locale
        return bundle

    monkeypatch.setattr(
        script_module,
        "fetch_mhdb_snapshot_bundle",
        fake_fetch_mhdb_snapshot_bundle,
    )
    return calls


def test_sync_files_delegates_locale_timeout_bundle_and_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle = fixture_bundle()
    calls: list[tuple[object, ...]] = []
    raw_directory = tmp_path / "raw"
    catalog_output = tmp_path / "catalog.json"

    def fake_fetch(
        *,
        locale: str = "ja",
        timeout_seconds: float = 30.0,
    ) -> dict[str, object]:
        calls.append(("fetch", locale, timeout_seconds))
        return bundle

    def fake_write(
        *,
        bundle: object,
        raw_directory: Path,
        catalog_output_path: Path,
    ) -> None:
        calls.append(("write", bundle, raw_directory, catalog_output_path))

    monkeypatch.setattr(script_module, "fetch_mhdb_snapshot_bundle", fake_fetch)
    monkeypatch.setattr(script_module, "write_mhdb_sync_outputs", fake_write)

    sync_files(
        raw_directory=raw_directory,
        catalog_output_path=catalog_output,
        locale="en",
        timeout_seconds=8.5,
    )

    assert calls == [
        ("fetch", "en", 8.5),
        ("write", bundle, raw_directory, catalog_output),
    ]


def test_sync_files_writes_all_raw_files_and_loadable_catalog(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = install_fixture_fetch(monkeypatch)
    raw_directory = tmp_path / "nested" / "raw"
    catalog_output = tmp_path / "another" / "nested" / "catalog.json"

    sync_files(
        raw_directory=raw_directory,
        catalog_output_path=catalog_output,
    )

    assert calls == [("ja", 30.0)]
    assert {path.name for path in raw_directory.iterdir()} == set(RAW_FILENAMES)
    catalog = load_catalog(path=catalog_output)
    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 12
    assert len(catalog.decorations) == 3
    assert tmp_path.resolve() in raw_directory.resolve().parents
    assert tmp_path.resolve() in catalog_output.resolve().parents
    assert ROOT.resolve() not in raw_directory.resolve().parents


def test_main_uses_default_locale_and_timeout_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = install_fixture_fetch(monkeypatch)
    raw_directory = tmp_path / "raw"
    catalog_output = tmp_path / "catalog.json"

    result = main([str(raw_directory), str(catalog_output)])

    assert result == 0
    assert calls == [("ja", 30.0)]
    assert len(load_catalog(path=catalog_output).equipment) == 12


def test_main_passes_explicit_locale_and_float_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = install_fixture_fetch(monkeypatch)
    raw_directory = tmp_path / "raw"
    catalog_output = tmp_path / "catalog.json"

    result = main(
        [
            str(raw_directory),
            str(catalog_output),
            "--locale",
            "en",
            "--timeout-seconds",
            "4.25",
        ]
    )

    assert result == 0
    assert calls == [("en", 4.25)]
    assert load_json(raw_directory / "metadata.json") == {
        "source": "https://wilds.mhdb.io",
        "locale": "en",
        "version": "2026.07.12-cli-test",
        "files": {
            "skills": "skills.json",
            "decorations": "decorations.json",
            "armor_sets": "armor_sets.json",
            "armor": "armor.json",
            "weapons": "weapons.json",
            "charms": "charms.json",
        },
    }


def test_sync_files_output_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_fixture_fetch(monkeypatch)
    first_raw = tmp_path / "first" / "raw"
    first_catalog = tmp_path / "first" / "catalog.json"
    second_raw = tmp_path / "second" / "raw"
    second_catalog = tmp_path / "second" / "catalog.json"

    sync_files(
        raw_directory=first_raw,
        catalog_output_path=first_catalog,
    )
    sync_files(
        raw_directory=second_raw,
        catalog_output_path=second_catalog,
    )

    assert first_catalog.read_bytes() == second_catalog.read_bytes()
    for filename in RAW_FILENAMES:
        assert (first_raw / filename).read_bytes() == (
            second_raw / filename
        ).read_bytes()


def test_sync_files_requires_keyword_arguments_and_has_exact_defaults() -> None:
    signature = inspect.signature(sync_files)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert signature.parameters["locale"].default == "ja"
    assert signature.parameters["timeout_seconds"].default == 30.0
    with pytest.raises(TypeError):
        sync_files(Path("raw"), Path("catalog.json"))  # type: ignore[call-arg]


def test_script_has_no_third_party_http_imports_or_logging() -> None:
    source = (ROOT / "scripts" / "sync_mhdb_catalog.py").read_text(encoding="utf-8")
    lowered = source.lower()

    for forbidden in (
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "logging",
        "print(",
    ):
        assert forbidden not in lowered


def test_importing_script_does_not_open_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("network must not be called while importing")

    monkeypatch.setattr(sync_module.urllib_request, "urlopen", fail_if_called)

    reloaded = importlib.reload(script_module)

    assert reloaded is script_module
    assert calls == []
