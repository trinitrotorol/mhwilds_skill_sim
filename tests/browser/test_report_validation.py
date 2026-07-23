from __future__ import annotations

import copy
import inspect

import pytest

from mhwilds_skill_sim.api.ranked_search_request import (
    decode_ranked_search_request_payload,
)
from mhwilds_skill_sim.api.search_response import build_candidate_to_response
from mhwilds_skill_sim.browser.catalog_export import (
    _prepare_expanded_equipment,
    build_browser_search_catalog,
)
from mhwilds_skill_sim.browser.report_validation import (
    validate_browser_solver_report,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.preferences import (
    calculate_skill_preference_score,
)
from mhwilds_skill_sim.validation.build import aggregate_valid_build_skill_levels


def _reports(
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    return copy.deepcopy(valid_report_bundle)


def _canonical_variant_ids(*, catalog: Catalog) -> list[int]:
    prepared = _prepare_expanded_equipment(
        catalog=catalog,
        maximum_expanded_equipment=500_000,
    )
    return [
        next(
            variant_id
            for variant_id, definition in enumerate(prepared.expanded)
            if definition.part is part
        )
        for part in EquipmentPart
    ]


def _build_report_bundle_for_variants(
    *,
    catalog: Catalog,
    source_sha256: str,
    selected_variant_ids: list[int],
) -> tuple[dict[str, object], dict[str, object]]:
    prepared = _prepare_expanded_equipment(
        catalog=catalog,
        maximum_expanded_equipment=500_000,
    )
    selected_equipment = tuple(
        prepared.expanded[variant_id] for variant_id in selected_variant_ids
    )
    skill_levels = aggregate_valid_build_skill_levels(
        equipment=selected_equipment,
        decorations=catalog.decorations,
        placements=(),
        skill_definitions=catalog.skills,
    )
    candidate = BuildCandidate(
        equipment=selected_equipment,
        placements=(),
        skill_levels=tuple(skill_levels.items()),
    )
    request_payload = {
        "requirements": [],
        "preferences": [],
        "max_results": 1,
    }
    request = decode_ranked_search_request_payload(payload=request_payload)
    preference_score = calculate_skill_preference_score(
        skill_levels=skill_levels,
        preferences=request.preferences,
    )
    candidate_response = build_candidate_to_response(candidate=candidate)
    candidate_response["preference_score"] = preference_score
    case_name = "selected-variant-validation"
    oracle_report = {
        "format_version": 1,
        "source_catalog_sha256": source_sha256,
        "timeout_seconds": 5.0,
        "omitted_cases": [],
        "cases": [
            {
                "name": case_name,
                "request": request_payload,
                "elapsed_seconds": 0.001,
                "status": "optimal",
                "candidate_exists": True,
                "preference_score": preference_score,
                "decoration_count": 0,
                "equipment_signature": [],
            }
        ],
    }
    browser_report = {
        "format_version": 1,
        "source_catalog_sha256": source_sha256,
        "runtime": "node",
        "timeout_ms": 10_000,
        "repeats": 1,
        "cases": [
            {
                "name": case_name,
                "request": request_payload,
                "result": {
                    "status": "optimal",
                    "candidate": candidate_response,
                    "selected_variant_ids": selected_variant_ids,
                    "preference_score": preference_score,
                    "decoration_count": 0,
                    "elapsed_ms": 1.0,
                    "visited_nodes": 1,
                    "pruned_nodes": 0,
                    "complete_equipment_selections": 1,
                },
                "timings_ms": {"min": 1.0, "median": 1.0, "max": 1.0},
                "deterministic": True,
                "parity": True,
            }
        ],
    }
    return oracle_report, browser_report


def test_validator_signature_is_keyword_only() -> None:
    signature = inspect.signature(validate_browser_solver_report)
    assert tuple(signature.parameters) == (
        "catalog",
        "browser_catalog",
        "oracle_report",
        "browser_report",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_valid_optimal_report_reuses_python_validation_and_has_parity(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    browser_report["environment"] = {"viewport": [1440, 900]}
    inputs_before = copy.deepcopy((tiny_browser_catalog, oracle_report, browser_report))

    summary = validate_browser_solver_report(
        catalog=tiny_catalog,
        browser_catalog=tiny_browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )

    assert summary == {
        "case_count": 1,
        "valid_candidate_count": 1,
        "completed_parity_count": 1,
        "completed_parity_failure_count": 0,
        "timed_out_count": 0,
        "cancelled_count": 0,
    }
    assert (tiny_browser_catalog, oracle_report, browser_report) == inputs_before


def test_objective_mismatch_is_counted_without_accepting_parity(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    oracle_case = oracle_report["cases"][0]  # type: ignore[index]
    oracle_case["preference_score"] += 1
    browser_report["cases"][0]["parity"] = False  # type: ignore[index]

    summary = validate_browser_solver_report(
        catalog=tiny_catalog,
        browser_catalog=tiny_browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )

    assert summary["completed_parity_count"] == 0
    assert summary["completed_parity_failure_count"] == 1


def test_invalid_variant_id_is_rejected(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    result = browser_report["cases"][0]["result"]  # type: ignore[index]
    result["selected_variant_ids"][0] = 100_000

    with pytest.raises(ValueError, match="unknown"):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=tiny_browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_missing_part_is_rejected_before_candidate_acceptance(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    result = browser_report["cases"][0]["result"]  # type: ignore[index]
    result["selected_variant_ids"].pop()

    with pytest.raises(ValueError, match="exactly seven"):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=tiny_browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_invalid_decoration_placement_is_rejected_by_existing_validation(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    result = browser_report["cases"][0]["result"]  # type: ignore[index]
    candidate = result["candidate"]
    head = candidate["equipment"][1]
    candidate["placements"].append(
        {
            "equipment_id": head["equipment_id"],
            "slot_index": 0,
            "decoration_id": "fixture:decoration:weapon-power-1",
        }
    )

    with pytest.raises(ValueError, match="valid build"):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=tiny_browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_wrong_reported_skill_levels_are_rejected(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    candidate = browser_report["cases"][0]["result"]["candidate"]  # type: ignore[index]
    candidate["skill_levels"][0]["level"] += 1

    with pytest.raises(ValueError, match="skill_levels"):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=tiny_browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


@pytest.mark.parametrize("field_name", ["preference_score", "decoration_count"])
def test_wrong_result_objective_is_rejected(
    field_name: str,
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    result = browser_report["cases"][0]["result"]  # type: ignore[index]
    result[field_name] += 1

    with pytest.raises(ValueError, match=field_name):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=tiny_browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_source_hash_mismatch_is_rejected(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    browser_report["source_catalog_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source Catalog hash"):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=tiny_browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_timed_out_partial_candidate_is_valid_but_not_compared(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    result = browser_report["cases"][0]["result"]  # type: ignore[index]
    result["status"] = "timed-out"
    browser_report["cases"][0]["parity"] = None  # type: ignore[index]

    summary = validate_browser_solver_report(
        catalog=tiny_catalog,
        browser_catalog=tiny_browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )

    assert summary["valid_candidate_count"] == 1
    assert summary["completed_parity_count"] == 0
    assert summary["timed_out_count"] == 1


def test_matching_infeasible_no_candidate_report_is_completed_parity(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    oracle_report, browser_report = _reports(valid_report_bundle)
    oracle_case = oracle_report["cases"][0]  # type: ignore[index]
    oracle_case.update(
        {
            "status": "infeasible",
            "candidate_exists": False,
            "preference_score": None,
            "decoration_count": None,
            "equipment_signature": [],
        }
    )
    result = browser_report["cases"][0]["result"]  # type: ignore[index]
    result.update(
        {
            "status": "infeasible",
            "candidate": None,
            "selected_variant_ids": [],
            "preference_score": None,
            "decoration_count": None,
        }
    )

    summary = validate_browser_solver_report(
        catalog=tiny_catalog,
        browser_catalog=tiny_browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )

    assert summary["valid_candidate_count"] == 0
    assert summary["completed_parity_count"] == 1


def test_tampered_variant_membership_in_browser_catalog_is_rejected(
    tiny_catalog: Catalog,
    tiny_browser_catalog: dict[str, object],
    valid_report_bundle: tuple[dict[str, object], dict[str, object]],
) -> None:
    browser_catalog = copy.deepcopy(tiny_browser_catalog)
    weapon = browser_catalog["equipment_by_part"]["weapon"][0]  # type: ignore[index]
    weapon["series_skill_ids"] = []
    oracle_report, browser_report = _reports(valid_report_bundle)

    with pytest.raises(ValueError, match="deterministic export"):
        validate_browser_solver_report(
            catalog=tiny_catalog,
            browser_catalog=browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_generated_charm_variant_is_validated_as_selected_equipment(
    tiny_catalog: Catalog,
    tiny_sha256: str,
    tiny_browser_catalog: dict[str, object],
) -> None:
    prepared = _prepare_expanded_equipment(
        catalog=tiny_catalog,
        maximum_expanded_equipment=500_000,
    )
    selected_variant_ids = _canonical_variant_ids(catalog=tiny_catalog)
    selected_variant_ids[-1] = next(
        variant_id
        for variant_id, definition in enumerate(prepared.expanded)
        if definition.equipment_id.startswith("generated:appraisal-charm:")
    )
    oracle_report, browser_report = _build_report_bundle_for_variants(
        catalog=tiny_catalog,
        source_sha256=tiny_sha256,
        selected_variant_ids=selected_variant_ids,
    )

    summary = validate_browser_solver_report(
        catalog=tiny_catalog,
        browser_catalog=tiny_browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )

    selected_charm = browser_report["cases"][0]["result"]["candidate"]["equipment"][  # type: ignore[index]
        -1
    ]
    assert selected_charm["equipment_id"].startswith("generated:appraisal-charm:")
    assert summary["valid_candidate_count"] == 1
    assert summary["completed_parity_count"] == 1


def test_same_equipment_id_artian_variants_remain_distinguishable(
    artian_variant_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    browser_catalog = build_browser_search_catalog(
        catalog=artian_variant_catalog,
        source_catalog_sha256=tiny_sha256,
    )
    prepared = _prepare_expanded_equipment(
        catalog=artian_variant_catalog,
        maximum_expanded_equipment=500_000,
    )
    artian_variant_ids = [
        variant_id
        for variant_id, definition in enumerate(prepared.expanded)
        if definition.equipment_id == "fixture:weapon:training-blade"
    ]
    selected_variant_ids = _canonical_variant_ids(catalog=artian_variant_catalog)
    oracle_report, browser_report = _build_report_bundle_for_variants(
        catalog=artian_variant_catalog,
        source_sha256=tiny_sha256,
        selected_variant_ids=selected_variant_ids,
    )

    summary = validate_browser_solver_report(
        catalog=artian_variant_catalog,
        browser_catalog=browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )
    assert summary["valid_candidate_count"] == 1
    assert len(artian_variant_ids) == 4
    assert {
        prepared.expanded[variant_id].equipment_id for variant_id in artian_variant_ids
    } == {"fixture:weapon:training-blade"}

    selected_weapon_id = selected_variant_ids[0]
    alternate_weapon_id = next(
        variant_id
        for variant_id in artian_variant_ids
        if variant_id != selected_weapon_id
    )
    browser_report["cases"][0]["result"]["selected_variant_ids"][0] = (  # type: ignore[index]
        alternate_weapon_id
    )
    with pytest.raises(ValueError, match="does not match selected variants"):
        validate_browser_solver_report(
            catalog=artian_variant_catalog,
            browser_catalog=browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )


def test_primary_and_additional_membership_bonuses_are_recomputed(
    primary_additional_membership_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    browser_catalog = build_browser_search_catalog(
        catalog=primary_additional_membership_catalog,
        source_catalog_sha256=tiny_sha256,
    )
    selected_variant_ids = _canonical_variant_ids(
        catalog=primary_additional_membership_catalog
    )
    oracle_report, browser_report = _build_report_bundle_for_variants(
        catalog=primary_additional_membership_catalog,
        source_sha256=tiny_sha256,
        selected_variant_ids=selected_variant_ids,
    )

    summary = validate_browser_solver_report(
        catalog=primary_additional_membership_catalog,
        browser_catalog=browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )
    reported_levels = {
        item["skill_id"]: item["level"]
        for item in browser_report["cases"][0]["result"]["candidate"][  # type: ignore[index]
            "skill_levels"
        ]
    }
    assert reported_levels["skill:fixture-series-bonus"] == 2
    assert reported_levels["skill:fixture-group-bonus"] == 1
    assert reported_levels["skill:fixture-series-extra"] == 1
    assert reported_levels["skill:fixture-group-extra"] == 1
    assert summary["valid_candidate_count"] == 1

    browser_report["cases"][0]["result"]["candidate"]["skill_levels"] = [  # type: ignore[index]
        item
        for item in browser_report["cases"][0]["result"]["candidate"][  # type: ignore[index]
            "skill_levels"
        ]
        if item["skill_id"] != "skill:fixture-series-extra"
    ]
    with pytest.raises(ValueError, match="skill_levels are incorrect"):
        validate_browser_solver_report(
            catalog=primary_additional_membership_catalog,
            browser_catalog=browser_catalog,
            oracle_report=oracle_report,
            browser_report=browser_report,
        )
