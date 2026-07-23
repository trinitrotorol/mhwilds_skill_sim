from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import mhwilds_skill_sim.browser.oracle as oracle_module
from mhwilds_skill_sim.browser.oracle import (
    build_browser_solver_oracle_report,
    build_representative_browser_solver_cases,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.solver.cp_sat_search import CpSatBuildSearchResult


ROOT = Path(__file__).resolve().parents[2]
TINY_CATALOG_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"
COMMITTED_TINY_ORACLE = (
    ROOT / "apps" / "web" / "src" / "browser-solver" / "fixtures" / "tiny-oracle.json"
)


def test_representative_cases_are_deterministic_and_top_one(
    tiny_catalog: Catalog,
) -> None:
    first = build_representative_browser_solver_cases(catalog=tiny_catalog)
    second = build_representative_browser_solver_cases(catalog=tiny_catalog)

    assert first == second
    assert [case["name"] for case in first] == [
        "empty",
        "normal-required",
        "normal-preferred",
        "mixed-ranked",
        "series-required",
        "group-preferred",
        "impossible-stress",
    ]
    assert all(case["request"]["max_results"] == 1 for case in first)  # type: ignore[index]
    assert first[-1]["request"]["requirements"] == [  # type: ignore[index]
        {"skill_id": "skill:attack-boost", "min_level": 4}
    ]


def test_representative_cases_omit_unavailable_kinds() -> None:
    catalog = Catalog(schema_version=1, equipment=(), decorations=())

    assert build_representative_browser_solver_cases(catalog=catalog) == (
        {
            "name": "empty",
            "request": {
                "requirements": [],
                "preferences": [],
                "max_results": 1,
            },
        },
    )


def test_oracle_signature_is_keyword_only() -> None:
    signature = inspect.signature(build_browser_solver_oracle_report)
    assert tuple(signature.parameters) == (
        "catalog",
        "cases",
        "timeout_seconds",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_oracle_calls_existing_ranked_solver_directly_with_top_one(
    monkeypatch: pytest.MonkeyPatch,
    tiny_catalog: Catalog,
) -> None:
    cases = (
        {
            "name": "probe",
            "request": {
                "requirements": [],
                "preferences": [],
                "max_results": 1,
            },
        },
    )
    calls: list[dict[str, object]] = []

    def fake_solver(**kwargs: object) -> CpSatBuildSearchResult:
        calls.append(kwargs)
        return CpSatBuildSearchResult(
            candidates=(),
            exhausted=True,
            timed_out=False,
        )

    clock = iter((10.0, 10.1250004))
    monkeypatch.setattr(
        oracle_module,
        "search_catalog_ranked_build_candidates_with_cp_sat",
        fake_solver,
    )
    monkeypatch.setattr(oracle_module, "perf_counter", lambda: next(clock))

    report = build_browser_solver_oracle_report(
        catalog=tiny_catalog,
        cases=cases,
        timeout_seconds=7,
    )

    assert len(calls) == 1
    assert calls[0]["catalog"] is tiny_catalog
    assert calls[0]["max_results"] == 1
    assert calls[0]["timeout_seconds"] == 7.0
    assert report["cases"] == [
        {
            "name": "probe",
            "request": {
                "requirements": [],
                "preferences": [],
                "max_results": 1,
            },
            "elapsed_seconds": 0.125,
            "status": "infeasible",
            "candidate_exists": False,
            "preference_score": None,
            "decoration_count": None,
            "equipment_signature": [],
        }
    ]


def test_oracle_records_timed_out_without_hiding_partial_state(
    monkeypatch: pytest.MonkeyPatch,
    tiny_catalog: Catalog,
) -> None:
    cases = (
        {
            "name": "timeout",
            "request": {
                "requirements": [],
                "preferences": [],
                "max_results": 1,
            },
        },
    )
    monkeypatch.setattr(
        oracle_module,
        "search_catalog_ranked_build_candidates_with_cp_sat",
        lambda **_kwargs: CpSatBuildSearchResult(
            candidates=(),
            exhausted=False,
            timed_out=True,
        ),
    )
    monkeypatch.setattr(oracle_module, "perf_counter", lambda: 1.0)

    report = build_browser_solver_oracle_report(
        catalog=tiny_catalog,
        cases=cases,
    )

    assert report["cases"][0]["status"] == "timed-out"  # type: ignore[index]
    assert report["cases"][0]["candidate_exists"] is False  # type: ignore[index]


def test_real_tiny_oracle_records_objective_signature_and_omission(
    tiny_catalog: Catalog,
) -> None:
    cases = (
        {
            "name": "normal-preferred",
            "request": {
                "requirements": [],
                "preferences": [
                    {"skill_id": "skill:attack-boost", "target_level": 1},
                ],
                "max_results": 1,
            },
        },
    )
    before = copy.deepcopy(cases)

    report = build_browser_solver_oracle_report(
        catalog=tiny_catalog,
        cases=cases,
        timeout_seconds=5,
    )

    case = report["cases"][0]  # type: ignore[index]
    assert case["status"] == "optimal"
    assert case["candidate_exists"] is True
    assert case["preference_score"] == 1
    assert type(case["decoration_count"]) is int
    assert len(case["equipment_signature"]) == 7
    assert list(case["equipment_signature"][0]) == [
        "equipment_id",
        "part",
        "series_skill_id",
        "additional_series_skill_ids",
        "group_skill_id",
        "additional_group_skill_ids",
    ]
    omitted = {entry["name"] for entry in report["omitted_cases"]}  # type: ignore[index]
    assert "weapon-filter" in omitted
    assert cases == before


def test_oracle_rejects_non_top_one_workload_before_solver(
    monkeypatch: pytest.MonkeyPatch,
    tiny_catalog: Catalog,
) -> None:
    monkeypatch.setattr(
        oracle_module,
        "search_catalog_ranked_build_candidates_with_cp_sat",
        lambda **_kwargs: pytest.fail("solver must not run"),
    )
    with pytest.raises(ValueError, match="exactly 1"):
        build_browser_solver_oracle_report(
            catalog=tiny_catalog,
            cases=(
                {
                    "name": "bad",
                    "request": {
                        "requirements": [],
                        "preferences": [],
                        "max_results": 2,
                    },
                },
            ),
        )


def test_oracle_source_does_not_use_exhaustive_search() -> None:
    source = Path(oracle_module.__file__).read_text(encoding="utf-8")
    assert "enumerate_build_candidates" not in source
    assert "search_catalog_build_candidates_by_skill_requirements" not in source


def test_committed_tiny_oracle_structurally_regenerates(
    tiny_catalog: Catalog,
) -> None:
    cases = build_representative_browser_solver_cases(catalog=tiny_catalog)
    body = build_browser_solver_oracle_report(
        catalog=tiny_catalog,
        cases=cases,
        timeout_seconds=30,
    )
    regenerated = {
        "format_version": body["format_version"],
        "source_catalog_sha256": hashlib.sha256(
            TINY_CATALOG_PATH.read_bytes()
        ).hexdigest(),
        "timeout_seconds": body["timeout_seconds"],
        "omitted_cases": body["omitted_cases"],
        "cases": body["cases"],
    }
    committed = json.loads(COMMITTED_TINY_ORACLE.read_text(encoding="utf-8"))

    for report in (regenerated, committed):
        for case in report["cases"]:
            case["elapsed_seconds"] = 0.0

    assert regenerated == committed
