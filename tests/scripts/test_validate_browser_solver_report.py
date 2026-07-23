from __future__ import annotations

import inspect
import hashlib
import json
from pathlib import Path

import pytest

from mhwilds_skill_sim.api.ranked_search_request import (
    decode_ranked_search_request_payload,
)
from mhwilds_skill_sim.api.search_response import build_candidate_to_response
from mhwilds_skill_sim.browser.catalog_export import (
    _prepare_expanded_equipment,
    build_browser_search_catalog,
)
from mhwilds_skill_sim.browser.oracle import build_browser_solver_oracle_report
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.solver.cp_sat_search import (
    search_catalog_ranked_build_candidates_with_cp_sat,
)
from mhwilds_skill_sim.solver.preferences import (
    calculate_skill_preference_score,
)
from scripts.validate_browser_solver_report import (
    main,
    validate_browser_solver_report_files,
)


ROOT = Path(__file__).resolve().parents[2]
TINY_CATALOG_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"


def _write_json(*, path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="module")
def report_inputs() -> tuple[
    dict[str, object],
    tuple[dict[str, object], dict[str, object]],
]:
    catalog = load_catalog(path=TINY_CATALOG_PATH)
    source_sha256 = hashlib.sha256(TINY_CATALOG_PATH.read_bytes()).hexdigest()
    browser_catalog = build_browser_search_catalog(
        catalog=catalog,
        source_catalog_sha256=source_sha256,
    )
    request_payload = {
        "requirements": [],
        "preferences": [
            {"skill_id": "skill:attack-boost", "target_level": 1},
        ],
        "max_results": 1,
    }
    oracle_body = build_browser_solver_oracle_report(
        catalog=catalog,
        cases=({"name": "normal-preferred", "request": request_payload},),
        timeout_seconds=5,
    )
    oracle_report = {
        "format_version": 1,
        "source_catalog_sha256": source_sha256,
        "timeout_seconds": 5.0,
        "omitted_cases": oracle_body["omitted_cases"],
        "cases": oracle_body["cases"],
    }
    request = decode_ranked_search_request_payload(payload=request_payload)
    search_result = search_catalog_ranked_build_candidates_with_cp_sat(
        catalog=catalog,
        requirements=request.requirements,
        preferences=request.preferences,
        max_results=1,
        timeout_seconds=5,
    )
    candidate = search_result.candidates[0]
    prepared = _prepare_expanded_equipment(
        catalog=catalog,
        maximum_expanded_equipment=500_000,
    )
    selected_variant_ids = [
        next(
            index
            for index, definition in enumerate(prepared.expanded)
            if definition == selected
        )
        for selected in candidate.equipment
    ]
    score = calculate_skill_preference_score(
        skill_levels=dict(candidate.skill_levels),
        preferences=request.preferences,
    )
    candidate_response = build_candidate_to_response(candidate=candidate)
    candidate_response["preference_score"] = score
    browser_report = {
        "format_version": 1,
        "source_catalog_sha256": source_sha256,
        "runtime": "node",
        "timeout_ms": 10_000,
        "repeats": 3,
        "cases": [
            {
                "name": "normal-preferred",
                "request": request_payload,
                "result": {
                    "status": "optimal",
                    "candidate": candidate_response,
                    "selected_variant_ids": selected_variant_ids,
                    "preference_score": score,
                    "decoration_count": len(candidate.placements),
                    "elapsed_ms": 1,
                    "visited_nodes": 1,
                    "pruned_nodes": 0,
                    "complete_equipment_selections": 1,
                },
                "timings_ms": {"min": 1, "median": 1, "max": 1},
                "deterministic": True,
                "parity": True,
            }
        ],
    }
    return browser_catalog, (oracle_report, browser_report)


def test_file_validator_has_keyword_only_signature() -> None:
    signature = inspect.signature(validate_browser_solver_report_files)
    assert tuple(signature.parameters) == (
        "catalog_path",
        "browser_catalog_path",
        "oracle_path",
        "browser_report_path",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_file_validator_loads_inputs_without_mutating_them(
    tmp_path: Path,
    report_inputs: tuple[
        dict[str, object],
        tuple[dict[str, object], dict[str, object]],
    ],
) -> None:
    tiny_browser_catalog, valid_report_bundle = report_inputs
    oracle_report, browser_report = valid_report_bundle
    browser_catalog_path = tmp_path / "browser-catalog.json"
    oracle_path = tmp_path / "oracle.json"
    browser_report_path = tmp_path / "browser-report.json"
    _write_json(path=browser_catalog_path, value=tiny_browser_catalog)
    _write_json(path=oracle_path, value=oracle_report)
    _write_json(path=browser_report_path, value=browser_report)
    before = (
        browser_catalog_path.read_bytes(),
        oracle_path.read_bytes(),
        browser_report_path.read_bytes(),
    )

    summary = validate_browser_solver_report_files(
        catalog_path=TINY_CATALOG_PATH,
        browser_catalog_path=browser_catalog_path,
        oracle_path=oracle_path,
        browser_report_path=browser_report_path,
    )

    assert summary["completed_parity_count"] == 1
    assert (
        browser_catalog_path.read_bytes(),
        oracle_path.read_bytes(),
        browser_report_path.read_bytes(),
    ) == before


def test_main_returns_nonzero_for_completed_objective_mismatch(
    tmp_path: Path,
    report_inputs: tuple[
        dict[str, object],
        tuple[dict[str, object], dict[str, object]],
    ],
    capsys: pytest.CaptureFixture[str],
) -> None:
    tiny_browser_catalog, valid_report_bundle = report_inputs
    oracle_report, browser_report = json.loads(json.dumps(valid_report_bundle))
    oracle_report["cases"][0]["preference_score"] += 1
    browser_report["cases"][0]["parity"] = False
    browser_catalog_path = tmp_path / "browser-catalog.json"
    oracle_path = tmp_path / "oracle.json"
    browser_report_path = tmp_path / "browser-report.json"
    _write_json(path=browser_catalog_path, value=tiny_browser_catalog)
    _write_json(path=oracle_path, value=oracle_report)
    _write_json(path=browser_report_path, value=browser_report)

    exit_code = main(
        [
            str(TINY_CATALOG_PATH),
            str(browser_catalog_path),
            str(oracle_path),
            str(browser_report_path),
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["completed_parity_failure_count"] == 1


def test_file_validator_rejects_source_bytes_hash_mismatch(
    tmp_path: Path,
    report_inputs: tuple[
        dict[str, object],
        tuple[dict[str, object], dict[str, object]],
    ],
) -> None:
    tiny_browser_catalog, valid_report_bundle = report_inputs
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_bytes(TINY_CATALOG_PATH.read_bytes() + b"\n")
    oracle_report, browser_report = valid_report_bundle
    browser_catalog_path = tmp_path / "browser-catalog.json"
    oracle_path = tmp_path / "oracle.json"
    browser_report_path = tmp_path / "browser-report.json"
    _write_json(path=browser_catalog_path, value=tiny_browser_catalog)
    _write_json(path=oracle_path, value=oracle_report)
    _write_json(path=browser_report_path, value=browser_report)

    with pytest.raises(ValueError, match="source Catalog bytes"):
        validate_browser_solver_report_files(
            catalog_path=catalog_path,
            browser_catalog_path=browser_catalog_path,
            oracle_path=oracle_path,
            browser_report_path=browser_report_path,
        )
