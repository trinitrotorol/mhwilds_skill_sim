from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

import pytest

import mhwilds_skill_sim.catalog as catalog_package
import mhwilds_skill_sim.catalog.mhdb_sync as sync_module
from mhwilds_skill_sim.catalog.decoder import decode_catalog
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.mhdb_sync import (
    MhdbSnapshotFetchError,
    build_catalog_document_from_mhdb_snapshot_bundle,
    fetch_json_url,
    fetch_mhdb_snapshot_bundle,
    write_mhdb_sync_outputs,
)
from mhwilds_skill_sim.domain.equipment import EquipmentPart

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
SNAPSHOT_KEYS = tuple(SNAPSHOT_FIXTURES)
RAW_FILENAMES = (
    "metadata.json",
    "skills.json",
    "decorations.json",
    "armor_sets.json",
    "armor.json",
    "weapons.json",
    "charms.json",
)


class StringSubclass(str):
    pass


class ListSubclass(list[object]):
    pass


class DictSubclass(dict[str, object]):
    pass


class FakeResponse:
    def __init__(self, body: bytes, *, read_error: Exception | None = None) -> None:
        self.body = body
        self.read_error = read_error
        self.entered = False
        self.exited = False
        self.read_count = 0

    def __enter__(self) -> FakeResponse:
        self.entered = True
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object,
    ) -> None:
        self.exited = True

    def read(self) -> bytes:
        self.read_count += 1
        if self.read_error is not None:
            raise self.read_error
        return self.body


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_bundle() -> dict[str, object]:
    return {
        "version": "2026.07.12-test",
        "locale": "ja",
        **{key: load_json(path) for key, path in SNAPSHOT_FIXTURES.items()},
    }


def endpoint_urls(locale: str = "ja") -> list[str]:
    base = "https://wilds.mhdb.io"
    return [
        f"{base}/version",
        f"{base}/{locale}/skills",
        f"{base}/{locale}/decorations",
        f"{base}/{locale}/armor/sets",
        f"{base}/{locale}/armor",
        f"{base}/{locale}/weapons",
        f"{base}/{locale}/charms",
    ]


def bundle_fetch_responses() -> list[object]:
    return [
        {"version": "2026.07.12", "future": "ignored"},
        [{"name": "攻撃力強化"}],
        [{"name": "攻撃珠"}],
        [{"name": "シリーズα"}],
        [{"name": "ヘルムα"}],
        [{"name": "大剣"}],
        [{"name": "護石"}],
    ]


def install_fake_bundle_fetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    responses: list[object] | None = None,
) -> tuple[list[tuple[str, int | float]], list[object]]:
    if responses is None:
        responses = bundle_fetch_responses()
    calls: list[tuple[str, int | float]] = []

    def fake_fetch_json_url(*, url: str, timeout_seconds: float) -> object:
        calls.append((url, timeout_seconds))
        return responses[len(calls) - 1]

    monkeypatch.setattr(sync_module, "fetch_json_url", fake_fetch_json_url)
    return calls, responses


def test_fetch_json_url_builds_exact_request_and_parses_utf8_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse('{"name":"攻撃の護石"}'.encode())
    captured: dict[str, object] = {}

    def fake_urlopen(
        request: urllib_request.Request,
        *,
        timeout: int | float,
    ) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr(sync_module.urllib_request, "urlopen", fake_urlopen)

    result = fetch_json_url(
        url="https://example.test/ja/charms",
        timeout_seconds=12.5,
    )

    request = captured["request"]
    assert isinstance(request, urllib_request.Request)
    assert request.full_url == "https://example.test/ja/charms"
    assert {key.lower(): value for key, value in request.header_items()} == {
        "accept": "application/json",
        "accept-encoding": "identity",
        "user-agent": "mhwilds-skill-sim/0.1",
    }
    assert captured["timeout"] == 12.5
    assert result == {"name": "攻撃の護石"}
    assert response.entered is True
    assert response.exited is True
    assert response.read_count == 1


def test_fetch_json_url_requires_keyword_arguments() -> None:
    signature = inspect.signature(fetch_json_url)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        fetch_json_url("https://example.test", 1.0)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("url", "cause"),
    [
        (None, TypeError),
        (1, TypeError),
        (StringSubclass("https://example.test"), TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" https://example.test", ValueError),
        ("https://example.test ", ValueError),
        ("http://example.test", ValueError),
        ("example.test", ValueError),
    ],
)
def test_fetch_json_url_rejects_invalid_url(
    url: object,
    cause: type[Exception],
) -> None:
    with pytest.raises(cause, match="url"):
        fetch_json_url(url=url, timeout_seconds=1.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("timeout", "cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (None, TypeError),
        ("30", TypeError),
        (0, ValueError),
        (0.0, ValueError),
        (-1, ValueError),
        (-0.1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (float("-inf"), ValueError),
    ],
)
def test_fetch_json_url_rejects_invalid_timeout(
    timeout: object,
    cause: type[Exception],
) -> None:
    with pytest.raises(cause, match="timeout_seconds"):
        fetch_json_url(
            url="https://example.test/data",
            timeout_seconds=timeout,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "fetch_error",
    [
        urllib_error.HTTPError(
            "https://example.test/data",
            503,
            "unavailable",
            hdrs=None,
            fp=None,
        ),
        urllib_error.URLError("offline"),
        TimeoutError("timed out"),
        OSError("socket failed"),
    ],
)
def test_fetch_json_url_wraps_transport_failures_with_url_and_cause(
    fetch_error: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_urlopen(
        request: urllib_request.Request,
        *,
        timeout: int | float,
    ) -> FakeResponse:
        del request, timeout
        raise fetch_error

    monkeypatch.setattr(sync_module.urllib_request, "urlopen", fail_urlopen)

    with pytest.raises(MhdbSnapshotFetchError) as exc_info:
        fetch_json_url(
            url="https://example.test/data",
            timeout_seconds=2.0,
        )

    assert "https://example.test/data" in str(exc_info.value)
    assert exc_info.value.__cause__ is fetch_error


def test_fetch_json_url_wraps_response_read_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_error = OSError("read failed")
    response = FakeResponse(b"", read_error=read_error)
    monkeypatch.setattr(
        sync_module.urllib_request,
        "urlopen",
        lambda request, *, timeout: response,
    )

    with pytest.raises(MhdbSnapshotFetchError) as exc_info:
        fetch_json_url(
            url="https://example.test/data",
            timeout_seconds=1,
        )

    assert exc_info.value.__cause__ is read_error
    assert response.exited is True


@pytest.mark.parametrize(
    ("body", "cause"),
    [
        (b"\xff", UnicodeDecodeError),
        (b'{"broken":', json.JSONDecodeError),
    ],
)
def test_fetch_json_url_wraps_invalid_utf8_and_json(
    body: bytes,
    cause: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(body)
    monkeypatch.setattr(
        sync_module.urllib_request,
        "urlopen",
        lambda request, *, timeout: response,
    )

    with pytest.raises(MhdbSnapshotFetchError) as exc_info:
        fetch_json_url(
            url="https://example.test/data",
            timeout_seconds=1.0,
        )

    assert "https://example.test/data" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, cause)


def test_fetch_bundle_uses_exact_order_defaults_and_preserves_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, responses = install_fake_bundle_fetch(monkeypatch)
    before = copy.deepcopy(responses)

    bundle = fetch_mhdb_snapshot_bundle()

    assert calls == [(url, 30.0) for url in endpoint_urls()]
    assert list(bundle) == [
        "version",
        "locale",
        "skills",
        "decorations",
        "armor_sets",
        "armor",
        "weapons",
        "charms",
    ]
    assert bundle["version"] == "2026.07.12"
    assert bundle["locale"] == "ja"
    for index, key in enumerate(SNAPSHOT_KEYS, start=1):
        assert bundle[key] is responses[index]
    assert responses == before


def test_fetch_bundle_accepts_another_locale_and_same_integer_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, _ = install_fake_bundle_fetch(monkeypatch)

    bundle = fetch_mhdb_snapshot_bundle(locale="en", timeout_seconds=7)

    assert bundle["locale"] == "en"
    assert calls == [(url, 7) for url in endpoint_urls("en")]


def test_fetch_bundle_accepts_empty_endpoint_arrays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[object] = [{"version": "1"}, [], [], [], [], [], []]
    install_fake_bundle_fetch(monkeypatch, responses=responses)

    bundle = fetch_mhdb_snapshot_bundle()

    assert all(bundle[key] == [] for key in SNAPSHOT_KEYS)


@pytest.mark.parametrize(
    "locale",
    [
        None,
        1,
        StringSubclass("ja"),
        "",
        "j",
        "jap",
        "JA",
        "Ja",
        " j",
        "j ",
        "j-",
        "j1",
        "日本",
    ],
)
def test_fetch_bundle_rejects_invalid_locale_without_requests(locale: object) -> None:
    with pytest.raises((TypeError, ValueError), match="locale"):
        fetch_mhdb_snapshot_bundle(locale=locale)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "version_response",
    [
        None,
        [],
        DictSubclass({"version": "1"}),
        {},
        {"version": None},
        {"version": StringSubclass("1")},
        {"version": ""},
        {"version": "   "},
        {"version": " 1"},
        {"version": "1 "},
    ],
)
def test_fetch_bundle_wraps_invalid_version_response(
    version_response: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_fetch(*, url: str, timeout_seconds: float) -> object:
        del timeout_seconds
        calls.append(url)
        return version_response

    monkeypatch.setattr(sync_module, "fetch_json_url", fake_fetch)

    with pytest.raises(MhdbSnapshotFetchError) as exc_info:
        fetch_mhdb_snapshot_bundle()

    assert "https://wilds.mhdb.io/version" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, (TypeError, ValueError))
    assert calls == ["https://wilds.mhdb.io/version"]


@pytest.mark.parametrize("endpoint_index", range(6))
@pytest.mark.parametrize("invalid_root", [None, {}, (), ListSubclass()])
def test_fetch_bundle_wraps_non_list_endpoint_root(
    endpoint_index: int,
    invalid_root: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = bundle_fetch_responses()
    responses[endpoint_index + 1] = invalid_root
    calls, _ = install_fake_bundle_fetch(monkeypatch, responses=responses)

    with pytest.raises(MhdbSnapshotFetchError) as exc_info:
        fetch_mhdb_snapshot_bundle()

    failing_url = endpoint_urls()[endpoint_index + 1]
    assert failing_url in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, TypeError)
    assert [url for url, _ in calls] == endpoint_urls()[: endpoint_index + 2]


def test_fetch_bundle_propagates_fetch_error_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = MhdbSnapshotFetchError("sentinel fetch failure")

    def fail_fetch(*, url: str, timeout_seconds: float) -> object:
        del url, timeout_seconds
        raise error

    monkeypatch.setattr(sync_module, "fetch_json_url", fail_fetch)

    with pytest.raises(MhdbSnapshotFetchError) as exc_info:
        fetch_mhdb_snapshot_bundle()

    assert exc_info.value is error


def test_repeated_bundle_fetches_return_independent_top_level_containers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = bundle_fetch_responses()
    call_index = 0

    def fake_fetch(*, url: str, timeout_seconds: float) -> object:
        nonlocal call_index
        del url, timeout_seconds
        response = responses[call_index % len(responses)]
        call_index += 1
        return response

    monkeypatch.setattr(sync_module, "fetch_json_url", fake_fetch)

    first = fetch_mhdb_snapshot_bundle()
    second = fetch_mhdb_snapshot_bundle()

    assert first == second
    assert first is not second
    assert first["skills"] is responses[1]
    assert second["skills"] is responses[1]
    first["locale"] = "en"
    assert second["locale"] == "ja"


def test_build_catalog_from_fixture_bundle_preserves_expected_catalog() -> None:
    bundle = fixture_bundle()

    document = build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)
    catalog = decode_catalog(value=document)

    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 12
    assert len(catalog.decorations) == 3
    assert all(
        equipment.part is EquipmentPart.WEAPON for equipment in catalog.equipment[:3]
    )
    assert all(
        equipment.part not in (EquipmentPart.WEAPON, EquipmentPart.CHARM)
        for equipment in catalog.equipment[3:9]
    )
    assert all(
        equipment.part is EquipmentPart.CHARM for equipment in catalog.equipment[9:]
    )
    assert [equipment.equipment_id for equipment in catalog.equipment[9:]] == [
        "mhdb:charm:-5001:rank-1",
        "mhdb:charm:-5001:rank-2",
        "mhdb:charm:5002:rank-1",
    ]
    assert all("5003" not in equipment.equipment_id for equipment in catalog.equipment)
    assert catalog.equipment[1].allows_series_skill_assignment is True
    assert catalog.equipment[1].allows_group_skill_assignment is True
    assert "appraisal_charm_skill_groups" not in document
    assert "appraisal_charm_patterns" not in document


def test_catalog_build_does_not_mutate_bundle_and_returns_independent_outputs() -> None:
    bundle = fixture_bundle()
    before = copy.deepcopy(bundle)

    first = build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)
    second = build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)

    assert bundle == before
    assert first == second
    assert first is not second
    assert first["skills"] is not second["skills"]
    assert first["equipment"] is not second["equipment"]
    assert first["equipment"][0] is not second["equipment"][0]
    assert first["decorations"] is not second["decorations"]


def test_catalog_build_requires_keyword_argument() -> None:
    signature = inspect.signature(build_catalog_document_from_mhdb_snapshot_bundle)

    assert signature.parameters["bundle"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        build_catalog_document_from_mhdb_snapshot_bundle(  # type: ignore[call-arg]
            fixture_bundle()
        )


@pytest.mark.parametrize("bundle", [None, [], (), "bundle", DictSubclass()])
def test_catalog_build_rejects_non_exact_dict_bundle(bundle: object) -> None:
    with pytest.raises(TypeError, match="bundle"):
        build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)


def test_catalog_build_reports_all_missing_and_extra_keys_deterministically() -> None:
    bundle = fixture_bundle()
    del bundle["skills"]
    del bundle["charms"]
    bundle["z_future"] = []
    bundle["a_future"] = []

    with pytest.raises(ValueError) as exc_info:
        build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)

    assert str(exc_info.value) == (
        "bundle has missing keys: skills, charms; unexpected keys: a_future, z_future"
    )


@pytest.mark.parametrize(
    ("key", "invalid_value", "cause"),
    [
        ("version", None, TypeError),
        ("version", StringSubclass("1"), TypeError),
        ("version", "", ValueError),
        ("version", "   ", ValueError),
        ("version", " 1", ValueError),
        ("version", "1 ", ValueError),
        ("locale", None, TypeError),
        ("locale", StringSubclass("ja"), TypeError),
        ("locale", "JA", ValueError),
        ("locale", "j", ValueError),
        ("locale", "j-", ValueError),
    ],
)
def test_catalog_build_rejects_invalid_bundle_text(
    key: str,
    invalid_value: object,
    cause: type[Exception],
) -> None:
    bundle = fixture_bundle()
    bundle[key] = invalid_value

    with pytest.raises(cause, match=f"bundle.{key}"):
        build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)


@pytest.mark.parametrize("key", SNAPSHOT_KEYS)
@pytest.mark.parametrize("invalid_value", [None, {}, (), ListSubclass()])
def test_catalog_build_requires_exact_list_for_every_snapshot(
    key: str,
    invalid_value: object,
) -> None:
    bundle = fixture_bundle()
    bundle[key] = invalid_value

    with pytest.raises(TypeError, match=f"bundle.{key}"):
        build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)


def test_writer_creates_exact_raw_bundle_and_loadable_catalog(tmp_path: Path) -> None:
    bundle = fixture_bundle()
    before = copy.deepcopy(bundle)
    raw_directory = tmp_path / "raw" / "ja"
    catalog_output = tmp_path / "normalized" / "catalog.json"

    write_mhdb_sync_outputs(
        bundle=bundle,
        raw_directory=raw_directory,
        catalog_output_path=catalog_output,
    )

    assert bundle == before
    assert {path.name for path in raw_directory.iterdir()} == set(RAW_FILENAMES)
    metadata = load_json(raw_directory / "metadata.json")
    assert metadata == {
        "source": "https://wilds.mhdb.io",
        "locale": "ja",
        "version": "2026.07.12-test",
        "files": {
            "skills": "skills.json",
            "decorations": "decorations.json",
            "armor_sets": "armor_sets.json",
            "armor": "armor.json",
            "weapons": "weapons.json",
            "charms": "charms.json",
        },
    }
    assert list(metadata) == ["source", "locale", "version", "files"]
    assert list(metadata["files"]) == list(SNAPSHOT_KEYS)
    for key in SNAPSHOT_KEYS:
        assert load_json(raw_directory / f"{key}.json") == bundle[key]

    catalog = load_catalog(path=catalog_output)
    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 12
    assert len(catalog.decorations) == 3


def test_writer_uses_deterministic_utf8_indentation_and_lf_newline(
    tmp_path: Path,
) -> None:
    raw_directory = tmp_path / "raw"
    catalog_output = tmp_path / "catalog.json"

    write_mhdb_sync_outputs(
        bundle=fixture_bundle(),
        raw_directory=raw_directory,
        catalog_output_path=catalog_output,
    )

    for path in (
        *tuple(raw_directory / name for name in RAW_FILENAMES),
        catalog_output,
    ):
        content = path.read_bytes()
        text = content.decode("utf-8")
        assert content.endswith(b"\n")
        assert not content.endswith(b"\n\n")
        assert b"\r\n" not in content
        assert "\n  " in text
    assert "攻撃力強化（テスト）" in (raw_directory / "skills.json").read_text(
        encoding="utf-8"
    )
    assert "\\u653b" not in (raw_directory / "skills.json").read_text(encoding="utf-8")
    assert "攻撃の護石Ⅰ（テスト）" in catalog_output.read_text(encoding="utf-8")


def test_writer_preserves_raw_then_catalog_write_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    writes: list[Path] = []

    def fake_write_json_file(*, path: Path, value: object) -> None:
        del value
        writes.append(path)

    monkeypatch.setattr(sync_module, "_write_json_file", fake_write_json_file)

    write_mhdb_sync_outputs(
        bundle=fixture_bundle(),
        raw_directory=tmp_path / "raw",
        catalog_output_path=tmp_path / "catalog.json",
    )

    assert [path.name for path in writes] == [*RAW_FILENAMES, "catalog.json"]


def test_writer_repeated_outputs_are_byte_for_byte_deterministic(
    tmp_path: Path,
) -> None:
    first_raw = tmp_path / "first" / "raw"
    first_catalog = tmp_path / "first" / "catalog.json"
    second_raw = tmp_path / "second" / "raw"
    second_catalog = tmp_path / "second" / "catalog.json"

    write_mhdb_sync_outputs(
        bundle=fixture_bundle(),
        raw_directory=first_raw,
        catalog_output_path=first_catalog,
    )
    write_mhdb_sync_outputs(
        bundle=fixture_bundle(),
        raw_directory=second_raw,
        catalog_output_path=second_catalog,
    )

    assert first_catalog.read_bytes() == second_catalog.read_bytes()
    for filename in RAW_FILENAMES:
        assert (first_raw / filename).read_bytes() == (
            second_raw / filename
        ).read_bytes()


def test_writer_invalid_bundle_writes_nothing(tmp_path: Path) -> None:
    bundle = fixture_bundle()
    del bundle["skills"]
    raw_directory = tmp_path / "missing" / "raw"
    catalog_output = tmp_path / "missing" / "catalog.json"

    with pytest.raises(ValueError, match="bundle"):
        write_mhdb_sync_outputs(
            bundle=bundle,
            raw_directory=raw_directory,
            catalog_output_path=catalog_output,
        )

    assert not raw_directory.exists()
    assert not catalog_output.exists()
    assert not catalog_output.parent.exists()


def test_writer_normalization_failure_writes_nothing(tmp_path: Path) -> None:
    bundle = fixture_bundle()
    bundle["skills"] = []
    raw_directory = tmp_path / "raw"
    catalog_output = tmp_path / "normalized" / "catalog.json"

    with pytest.raises(CatalogDecodeError):
        write_mhdb_sync_outputs(
            bundle=bundle,
            raw_directory=raw_directory,
            catalog_output_path=catalog_output,
        )

    assert not raw_directory.exists()
    assert not catalog_output.parent.exists()


def test_writer_rejects_raw_directory_that_is_a_file(tmp_path: Path) -> None:
    raw_file = tmp_path / "raw"
    raw_file.write_text("existing", encoding="utf-8")
    catalog_output = tmp_path / "catalog.json"

    with pytest.raises(ValueError, match="raw_directory"):
        write_mhdb_sync_outputs(
            bundle=fixture_bundle(),
            raw_directory=raw_file,
            catalog_output_path=catalog_output,
        )

    assert raw_file.read_text(encoding="utf-8") == "existing"
    assert not catalog_output.exists()


@pytest.mark.parametrize("filename", RAW_FILENAMES)
def test_writer_rejects_catalog_collision_with_each_reserved_raw_filename(
    filename: str,
    tmp_path: Path,
) -> None:
    raw_directory = tmp_path / "raw"

    with pytest.raises(ValueError, match="input|output"):
        write_mhdb_sync_outputs(
            bundle=fixture_bundle(),
            raw_directory=raw_directory,
            catalog_output_path=raw_directory / "." / filename,
        )

    assert not raw_directory.exists()


@pytest.mark.parametrize(
    ("raw_directory", "catalog_output", "field"),
    [
        ("raw", Path("catalog.json"), "raw_directory"),
        (Path("raw"), "catalog.json", "catalog_output_path"),
    ],
)
def test_writer_requires_path_instances(
    raw_directory: object,
    catalog_output: object,
    field: str,
) -> None:
    with pytest.raises(TypeError, match=field):
        write_mhdb_sync_outputs(
            bundle=fixture_bundle(),
            raw_directory=raw_directory,  # type: ignore[arg-type]
            catalog_output_path=catalog_output,  # type: ignore[arg-type]
        )


def test_writer_allows_nonreserved_catalog_inside_raw_directory(
    tmp_path: Path,
) -> None:
    raw_directory = tmp_path / "raw"
    catalog_output = raw_directory / "normalized" / "catalog.json"

    write_mhdb_sync_outputs(
        bundle=fixture_bundle(),
        raw_directory=raw_directory,
        catalog_output_path=catalog_output,
    )

    assert catalog_output.is_file()
    assert len(load_catalog(path=catalog_output).equipment) == 12


def test_writer_requires_keyword_arguments() -> None:
    signature = inspect.signature(write_mhdb_sync_outputs)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        write_mhdb_sync_outputs(  # type: ignore[call-arg]
            fixture_bundle(), Path("raw"), Path("catalog.json")
        )


def test_sync_module_symbols_are_not_exported_from_catalog_package() -> None:
    for name in (
        "MhdbSnapshotFetchError",
        "fetch_json_url",
        "fetch_mhdb_snapshot_bundle",
        "build_catalog_document_from_mhdb_snapshot_bundle",
        "write_mhdb_sync_outputs",
    ):
        assert not hasattr(catalog_package, name)
