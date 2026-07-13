from __future__ import annotations

import ast
import copy
import importlib
import inspect
import json
from pathlib import Path

import pytest

import mhwilds_skill_sim.api.search_service as api_search_service_module
import mhwilds_skill_sim.solver.build as build_module
import mhwilds_skill_sim.solver.catalog_search as catalog_search_module
import mhwilds_skill_sim.solver.decoration as decoration_module
import mhwilds_skill_sim.solver.equipment as equipment_module
import mhwilds_skill_sim.solver.search_result as search_result_module
import scripts.profile_cp_sat_search as script_module
from mhwilds_skill_sim.api.search_request import (
    SearchRequest,
    decode_search_request_payload,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import WeaponKind
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.cp_sat_search import (
    CpSatBuildSearchResult,
    search_catalog_build_candidates_with_cp_sat,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement
from scripts.profile_cp_sat_search import main, profile_cp_sat_search


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"
SCRIPT_PATH = ROOT / "scripts" / "profile_cp_sat_search.py"


class IntSubclass(int):
    pass


class FloatSubclass(float):
    pass


def empty_catalog() -> Catalog:
    return Catalog(schema_version=1, equipment=(), decorations=())


def empty_candidate() -> BuildCandidate:
    return BuildCandidate(equipment=(), placements=(), skill_levels=())


def write_request(
    *,
    tmp_path: Path,
    payload: object,
    name: str = "request.json",
) -> Path:
    request_path = tmp_path / name
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    return request_path


def fail_if_called(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("unexpected call")


def assert_json_primitives(value: object) -> None:
    if type(value) in (str, int, float, bool) or value is None:
        return
    if type(value) is list:
        for item in value:
            assert_json_primitives(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            assert type(key) is str
            assert_json_primitives(item)
        return
    raise AssertionError(f"non-JSON value remains: {type(value).__name__}")


def cli_report(*, timed_out: bool) -> dict[str, object]:
    return {
        "catalog": {
            "schema_version": 1,
            "equipment_count": 0,
            "decoration_count": 0,
            "skill_count": 0,
            "appraisal_charm_skill_group_count": 0,
            "appraisal_charm_pattern_count": 0,
        },
        "request": {
            "requirements": [{"skill_id": "skill:日本語", "min_level": 1}],
            "max_results": 1,
            "weapon_kind": None,
            "timeout_seconds": 10.0,
        },
        "timing_seconds": {
            "catalog_load": 0.0,
            "search": 0.0,
            "total": 0.0,
        },
        "result": {
            "candidate_count": 0,
            "exhausted": False,
            "timed_out": timed_out,
        },
    }


def test_profile_function_has_exact_keyword_only_signature() -> None:
    signature = inspect.signature(profile_cp_sat_search)
    parameters = signature.parameters

    assert tuple(parameters) == (
        "catalog_path",
        "request_path",
        "timeout_seconds",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert parameters["catalog_path"].default is inspect.Parameter.empty
    assert parameters["request_path"].default is inspect.Parameter.empty
    assert parameters["timeout_seconds"].default == 10.0

    with pytest.raises(TypeError):
        profile_cp_sat_search(  # type: ignore[misc]
            Path("catalog.json"),
            Path("request.json"),
        )


def test_main_has_exact_signature() -> None:
    signature = inspect.signature(main)
    parameters = signature.parameters

    assert tuple(parameters) == ("argv",)
    assert parameters["argv"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["argv"].default is None


@pytest.mark.parametrize("timeout_seconds", [1, 0.25])
def test_accepts_paths_and_positive_exact_numeric_timeouts_as_float(
    timeout_seconds: int | float,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = write_request(
        tmp_path=tmp_path,
        payload={"requirements": [], "max_results": 0},
    )
    passed_timeouts: list[float] = []

    monkeypatch.setattr(script_module, "load_catalog", lambda *, path: empty_catalog())
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)

    def fake_solver(**kwargs: object) -> CpSatBuildSearchResult:
        passed_timeout = kwargs["timeout_seconds"]
        assert type(passed_timeout) is float
        passed_timeouts.append(passed_timeout)
        return CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)

    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fake_solver,
    )

    report = profile_cp_sat_search(
        catalog_path=Path("catalog.json"),
        request_path=request_path,
        timeout_seconds=timeout_seconds,
    )

    assert passed_timeouts == [float(timeout_seconds)]
    assert report["request"]["timeout_seconds"] == float(timeout_seconds)  # type: ignore[index]


@pytest.mark.parametrize("catalog_path", [None, "catalog.json", 1, object()])
def test_rejects_invalid_catalog_path_before_loading(
    catalog_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(script_module, "load_catalog", fail_if_called)

    with pytest.raises(TypeError, match="catalog_path"):
        profile_cp_sat_search(
            catalog_path=catalog_path,  # type: ignore[arg-type]
            request_path=Path("request.json"),
        )


@pytest.mark.parametrize("request_path", [None, "request.json", 1, object()])
def test_rejects_invalid_request_path_before_loading(
    request_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(script_module, "load_catalog", fail_if_called)

    with pytest.raises(TypeError, match="request_path"):
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=request_path,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [True, False, "1", None, IntSubclass(1), FloatSubclass(1.0)],
)
def test_rejects_invalid_timeout_types_before_loading(
    timeout_seconds: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(script_module, "load_catalog", fail_if_called)

    with pytest.raises(TypeError, match="timeout_seconds"):
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=Path("request.json"),
            timeout_seconds=timeout_seconds,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [0, 0.0, -1, -0.25, float("nan"), float("inf"), float("-inf")],
)
def test_rejects_non_positive_or_non_finite_timeout_before_loading(
    timeout_seconds: int | float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(script_module, "load_catalog", fail_if_called)

    with pytest.raises(ValueError, match="timeout_seconds"):
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=Path("request.json"),
            timeout_seconds=timeout_seconds,
        )


def test_composition_timing_report_order_and_input_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {
        "requirements": [
            {"skill_id": "skill:attack-boost", "min_level": 1},
            {"skill_id": "skill:critical-eye", "min_level": 2},
        ],
        "max_results": 4,
        "weapon_kind": "bow",
    }
    request_path = write_request(tmp_path=tmp_path, payload=payload)
    catalog_path = Path("normalized/catalog.json")
    catalog = load_catalog(path=FIXTURE_PATH)
    candidate = empty_candidate()
    solver_result = CpSatBuildSearchResult(
        candidates=(candidate, candidate),
        exhausted=False,
        timed_out=True,
    )
    catalog_before = copy.deepcopy(catalog)
    result_before = copy.deepcopy(solver_result)
    payload_before = copy.deepcopy(payload)
    events: list[tuple[object, ...]] = []
    decoded_requests: list[SearchRequest] = []
    solver_calls: list[tuple[Catalog, tuple[SkillRequirement, ...]]] = []
    clock_values = iter((10.0, 11.1234567, 15.0, 17.7654321))
    original_json_load = json.load

    def fake_perf_counter() -> float:
        value = next(clock_values)
        events.append(("clock", value))
        return value

    def fake_load_catalog(*, path: Path) -> Catalog:
        events.append(("load", path))
        return catalog

    def recording_json_load(request_file: object) -> object:
        events.append(
            (
                "request_read",
                getattr(request_file, "mode"),
                getattr(request_file, "encoding").lower(),
            )
        )
        return original_json_load(request_file)  # type: ignore[arg-type]

    def recording_decoder(*, payload: object) -> SearchRequest:
        events.append(("decode", payload))
        decoded = decode_search_request_payload(payload=payload)
        decoded_requests.append(decoded)
        return decoded

    def fake_solver(
        *,
        catalog: Catalog,
        requirements: tuple[SkillRequirement, ...],
        max_results: int,
        weapon_kind: WeaponKind | None,
        timeout_seconds: float,
    ) -> CpSatBuildSearchResult:
        solver_calls.append((catalog, requirements))
        events.append(
            (
                "solver",
                catalog,
                requirements,
                max_results,
                weapon_kind,
                timeout_seconds,
            )
        )
        return solver_result

    monkeypatch.setattr(script_module, "perf_counter", fake_perf_counter)
    monkeypatch.setattr(script_module, "load_catalog", fake_load_catalog)
    monkeypatch.setattr(script_module.json, "load", recording_json_load)
    monkeypatch.setattr(
        script_module,
        "decode_search_request_payload",
        recording_decoder,
    )
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fake_solver,
    )

    report = profile_cp_sat_search(
        catalog_path=catalog_path,
        request_path=request_path,
        timeout_seconds=7,
    )

    assert len(decoded_requests) == 1
    assert len(solver_calls) == 1
    assert solver_calls[0][0] is catalog
    assert solver_calls[0][1] is decoded_requests[0].requirements
    assert events == [
        ("clock", 10.0),
        ("load", catalog_path),
        ("clock", 11.1234567),
        ("request_read", "r", "utf-8"),
        ("decode", payload),
        ("clock", 15.0),
        (
            "solver",
            catalog,
            decoded_requests[0].requirements,
            4,
            WeaponKind.BOW,
            7.0,
        ),
        ("clock", 17.7654321),
    ]
    with pytest.raises(StopIteration):
        next(clock_values)

    assert list(report) == ["catalog", "request", "timing_seconds", "result"]
    assert list(report["catalog"]) == [  # type: ignore[arg-type]
        "schema_version",
        "equipment_count",
        "decoration_count",
        "skill_count",
        "appraisal_charm_skill_group_count",
        "appraisal_charm_pattern_count",
    ]
    assert list(report["request"]) == [  # type: ignore[arg-type]
        "requirements",
        "max_results",
        "weapon_kind",
        "timeout_seconds",
    ]
    assert list(report["timing_seconds"]) == [  # type: ignore[arg-type]
        "catalog_load",
        "search",
        "total",
    ]
    assert list(report["result"]) == [  # type: ignore[arg-type]
        "candidate_count",
        "exhausted",
        "timed_out",
    ]
    assert report == {
        "catalog": {
            "schema_version": 1,
            "equipment_count": 9,
            "decoration_count": 5,
            "skill_count": 6,
            "appraisal_charm_skill_group_count": 3,
            "appraisal_charm_pattern_count": 3,
        },
        "request": {
            "requirements": [
                {"skill_id": "skill:attack-boost", "min_level": 1},
                {"skill_id": "skill:critical-eye", "min_level": 2},
            ],
            "max_results": 4,
            "weapon_kind": "bow",
            "timeout_seconds": 7.0,
        },
        "timing_seconds": {
            "catalog_load": 1.123457,
            "search": 2.765432,
            "total": 7.765432,
        },
        "result": {
            "candidate_count": 2,
            "exhausted": False,
            "timed_out": True,
        },
    }
    requirements_report = report["request"]["requirements"]  # type: ignore[index]
    assert [list(requirement) for requirement in requirements_report] == [
        ["skill_id", "min_level"],
        ["skill_id", "min_level"],
    ]
    assert "candidates" not in report["result"]  # type: ignore[operator]
    assert_json_primitives(report)
    assert json.loads(json.dumps(report, ensure_ascii=False)) == report
    assert catalog == catalog_before
    assert solver_result == result_before
    assert payload == payload_before


def test_report_uses_fresh_containers_and_null_weapon_kind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {
        "requirements": [
            {"skill_id": "skill:attack-boost", "min_level": 1},
        ],
        "max_results": 0,
    }
    request_path = write_request(tmp_path=tmp_path, payload=payload)
    catalog = empty_catalog()
    result = CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)
    monkeypatch.setattr(script_module, "load_catalog", lambda **_kwargs: catalog)
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        lambda **_kwargs: result,
    )

    first = profile_cp_sat_search(
        catalog_path=Path("catalog.json"),
        request_path=request_path,
    )
    second = profile_cp_sat_search(
        catalog_path=Path("catalog.json"),
        request_path=request_path,
    )

    assert first == second
    assert first is not second
    for section in ("catalog", "request", "timing_seconds", "result"):
        assert first[section] is not second[section]
    first_requirements = first["request"]["requirements"]  # type: ignore[index]
    second_requirements = second["request"]["requirements"]  # type: ignore[index]
    assert first_requirements is not second_requirements
    assert first_requirements[0] is not second_requirements[0]
    assert first["request"]["weapon_kind"] is None  # type: ignore[index]
    assert json.loads(request_path.read_text(encoding="utf-8")) == payload


def test_script_aliases_are_the_required_existing_boundaries() -> None:
    assert script_module.load_catalog is load_catalog
    assert script_module.decode_search_request_payload is decode_search_request_payload
    assert (
        script_module.search_catalog_build_candidates_with_cp_sat
        is search_catalog_build_candidates_with_cp_sat
    )


def test_profile_does_not_route_through_exhaustive_or_api_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = write_request(
        tmp_path=tmp_path,
        payload={"requirements": [], "max_results": 0},
    )
    monkeypatch.setattr(
        api_search_service_module,
        "search_catalog_build_candidates_from_payload",
        fail_if_called,
    )
    monkeypatch.setattr(
        api_search_service_module,
        "search_catalog_build_candidates_with_cp_sat_from_payload",
        fail_if_called,
    )
    monkeypatch.setattr(
        catalog_search_module,
        "search_catalog_build_candidates_by_skill_requirements",
        fail_if_called,
    )
    monkeypatch.setattr(
        search_result_module,
        "search_limited_catalog_build_candidates_by_skill_requirements",
        fail_if_called,
    )
    monkeypatch.setattr(build_module, "enumerate_build_candidates", fail_if_called)
    monkeypatch.setattr(
        equipment_module,
        "enumerate_equipment_selections",
        fail_if_called,
    )
    monkeypatch.setattr(
        decoration_module,
        "enumerate_decoration_placement_combinations",
        fail_if_called,
    )
    monkeypatch.setattr(
        script_module, "load_catalog", lambda **_kwargs: empty_catalog()
    )
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        lambda **_kwargs: CpSatBuildSearchResult(
            candidates=(),
            exhausted=True,
            timed_out=False,
        ),
    )

    report = profile_cp_sat_search(
        catalog_path=Path("catalog.json"),
        request_path=request_path,
    )

    assert report["result"] == {
        "candidate_count": 0,
        "exhausted": True,
        "timed_out": False,
    }


def test_loader_exception_is_propagated_by_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RuntimeError("catalog load failed")

    def fail_load(**_kwargs: object) -> Catalog:
        raise error

    monkeypatch.setattr(script_module, "load_catalog", fail_load)
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "decode_search_request_payload",
        fail_if_called,
    )
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_if_called,
    )

    with pytest.raises(RuntimeError) as exc_info:
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=Path("request.json"),
        )

    assert exc_info.value is error


def test_real_catalog_file_read_error_contract_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = write_request(
        tmp_path=tmp_path,
        payload={"requirements": [], "max_results": 0},
    )
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_if_called,
    )

    with pytest.raises(CatalogDecodeError, match="cannot read catalog JSON file"):
        profile_cp_sat_search(
            catalog_path=tmp_path / "missing-catalog.json",
            request_path=request_path,
        )


def test_missing_request_file_error_is_propagated_without_solver(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        script_module, "load_catalog", lambda **_kwargs: empty_catalog()
    )
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_if_called,
    )

    with pytest.raises(FileNotFoundError):
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=tmp_path / "missing-request.json",
        )


def test_request_read_error_is_propagated_by_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    error = OSError("request read failed")
    original_open = Path.open

    def fail_request_open(path: Path, *args: object, **kwargs: object) -> object:
        if path == request_path:
            raise error
        return original_open(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", fail_request_open)
    monkeypatch.setattr(
        script_module, "load_catalog", lambda **_kwargs: empty_catalog()
    )
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_if_called,
    )

    with pytest.raises(OSError) as exc_info:
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=request_path,
        )

    assert exc_info.value is error


def test_invalid_json_error_is_propagated_without_solver(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(
        script_module, "load_catalog", lambda **_kwargs: empty_catalog()
    )
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_if_called,
    )

    with pytest.raises(json.JSONDecodeError):
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=request_path,
        )


@pytest.mark.parametrize(
    ("payload", "expected_error", "message"),
    [
        ({}, ValueError, "requirements"),
        ("not-an-object", TypeError, "payload"),
        (
            {
                "requirements": [
                    {"skill_id": "skill:duplicate", "min_level": 1},
                    {"skill_id": "skill:duplicate", "min_level": 2},
                ],
                "max_results": 1,
            },
            ValueError,
            "requirements",
        ),
        ({"requirements": [], "max_results": True}, TypeError, "max_results"),
        ({"requirements": [], "max_results": -1}, ValueError, "max_results"),
        (
            {"requirements": [], "max_results": 1, "weapon_kind": "invalid"},
            ValueError,
            "weapon_kind",
        ),
        (
            {"requirements": [], "max_results": 1, "weapon_kind": 1},
            TypeError,
            "weapon_kind",
        ),
    ],
)
def test_request_decoder_errors_are_propagated_without_solver(
    payload: object,
    expected_error: type[Exception],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = write_request(tmp_path=tmp_path, payload=payload)
    monkeypatch.setattr(
        script_module, "load_catalog", lambda **_kwargs: empty_catalog()
    )
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_if_called,
    )

    with pytest.raises(expected_error, match=message):
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=request_path,
        )


def test_solver_exception_is_propagated_by_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request_path = write_request(
        tmp_path=tmp_path,
        payload={"requirements": [], "max_results": 1},
    )
    error = RuntimeError("solver failed")

    def fail_solver(**_kwargs: object) -> CpSatBuildSearchResult:
        raise error

    monkeypatch.setattr(
        script_module, "load_catalog", lambda **_kwargs: empty_catalog()
    )
    monkeypatch.setattr(script_module, "perf_counter", lambda: 1.0)
    monkeypatch.setattr(
        script_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail_solver,
    )

    with pytest.raises(RuntimeError) as exc_info:
        profile_cp_sat_search(
            catalog_path=Path("catalog.json"),
            request_path=request_path,
        )

    assert exc_info.value is error


def test_main_outputs_compact_json_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = cli_report(timed_out=False)
    calls: list[dict[str, object]] = []

    def fake_profile(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return report

    monkeypatch.setattr(script_module, "profile_cp_sat_search", fake_profile)

    exit_code = main(["nested/catalog.json", "nested/request.json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        {
            "catalog_path": Path("nested/catalog.json"),
            "request_path": Path("nested/request.json"),
            "timeout_seconds": 10.0,
        }
    ]
    assert captured.out == json.dumps(report, ensure_ascii=False) + "\n"
    assert captured.err == ""


def test_main_outputs_pretty_timeout_report_and_returns_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = cli_report(timed_out=True)
    calls: list[dict[str, object]] = []

    def fake_profile(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return report

    monkeypatch.setattr(script_module, "profile_cp_sat_search", fake_profile)

    exit_code = main(
        [
            "catalog.json",
            "request.json",
            "--timeout-seconds",
            "2.5",
            "--pretty",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert calls == [
        {
            "catalog_path": Path("catalog.json"),
            "request_path": Path("request.json"),
            "timeout_seconds": 2.5,
        }
    ]
    assert captured.out == json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    assert captured.err == ""


def test_importing_script_performs_no_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader_module = importlib.import_module("mhwilds_skill_sim.catalog.loader")
    request_module = importlib.import_module("mhwilds_skill_sim.api.search_request")
    solver_module = importlib.import_module("mhwilds_skill_sim.solver.cp_sat_search")
    calls: list[tuple[object, ...]] = []

    def record_and_fail(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("import must not perform profile work")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", record_and_fail)
            patch.setattr(Path, "read_text", record_and_fail)
            patch.setattr(loader_module, "load_catalog", record_and_fail)
            patch.setattr(
                request_module,
                "decode_search_request_payload",
                record_and_fail,
            )
            patch.setattr(
                solver_module,
                "search_catalog_build_candidates_with_cp_sat",
                record_and_fail,
            )

            reloaded = importlib.reload(script_module)

            assert reloaded is script_module
            assert calls == []
    finally:
        importlib.reload(script_module)


def test_script_source_has_no_network_writes_hidden_config_or_other_search() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    lowered = source.lower()

    for forbidden in (
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "socket",
        "fastapi",
        "uvicorn",
        "testclient",
        "write_text",
        "write_bytes",
        ".write(",
        "os.environ",
        "getenv",
        "enumerate_build_candidates",
        "enumerate_equipment_selections",
        "enumerate_decoration_placement_combinations",
        "search_catalog_build_candidates_by_skill_requirements",
        "search_limited_catalog_build_candidates_by_skill_requirements",
        "search_catalog_build_candidates_from_payload",
        "search_catalog_build_candidates_with_cp_sat_from_payload",
        "build_cp_sat_search_result_to_response",
        "create_app",
    ):
        assert forbidden not in lowered


def test_print_is_only_in_main_and_module_has_entrypoint() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_node = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    )
    main_nodes = set(ast.walk(main_node))
    print_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]

    assert len(print_calls) == 1
    assert print_calls[0] in main_nodes
    assert 'if __name__ == "__main__":' in source
    assert "raise SystemExit(main())" in source


def test_real_tiny_fixture_integration_returns_candidate_without_timeout(
    tmp_path: Path,
) -> None:
    request_path = write_request(
        tmp_path=tmp_path,
        payload={
            "requirements": [
                {"skill_id": "skill:attack-boost", "min_level": 1},
            ],
            "max_results": 1,
        },
    )

    report = profile_cp_sat_search(
        catalog_path=FIXTURE_PATH,
        request_path=request_path,
        timeout_seconds=10.0,
    )

    result = report["result"]
    assert result["candidate_count"] == 1  # type: ignore[index]
    assert result["candidate_count"] <= 1  # type: ignore[index,operator]
    assert result["timed_out"] is False  # type: ignore[index]
    assert not (result["exhausted"] and result["timed_out"])  # type: ignore[index]
    assert_json_primitives(report)
    json.dumps(report, ensure_ascii=False)
