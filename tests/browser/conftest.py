from __future__ import annotations

import hashlib
from dataclasses import replace
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
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.skill import (
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.solver.cp_sat_search import (
    search_catalog_ranked_build_candidates_with_cp_sat,
)
from mhwilds_skill_sim.solver.preferences import (
    calculate_skill_preference_score,
)


ROOT = Path(__file__).resolve().parents[2]
TINY_CATALOG_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"


@pytest.fixture(scope="session")
def tiny_catalog_path() -> Path:
    return TINY_CATALOG_PATH


@pytest.fixture(scope="session")
def tiny_catalog() -> Catalog:
    return load_catalog(path=TINY_CATALOG_PATH)


@pytest.fixture(scope="session")
def tiny_sha256() -> str:
    return hashlib.sha256(TINY_CATALOG_PATH.read_bytes()).hexdigest()


def _extra_bonus_skills() -> tuple[SkillDefinition, SkillDefinition]:
    return (
        SkillDefinition(
            skill_id="skill:fixture-series-extra",
            kind=SkillKind.SERIES,
            ranks=(SkillRankDefinition(level=1, required_pieces=1),),
        ),
        SkillDefinition(
            skill_id="skill:fixture-group-extra",
            kind=SkillKind.GROUP,
            ranks=(SkillRankDefinition(level=1, required_pieces=1),),
        ),
    )


@pytest.fixture(scope="session")
def artian_variant_catalog(tiny_catalog: Catalog) -> Catalog:
    extra_series, extra_group = _extra_bonus_skills()
    return replace(
        tiny_catalog,
        skills=(*tiny_catalog.skills, extra_series, extra_group),
    )


@pytest.fixture(scope="session")
def primary_additional_membership_catalog(tiny_catalog: Catalog) -> Catalog:
    extra_series, extra_group = _extra_bonus_skills()
    equipment = list(tiny_catalog.equipment)
    equipment[1] = replace(
        equipment[1],
        additional_series_skill_ids=(extra_series.skill_id,),
        additional_group_skill_ids=(extra_group.skill_id,),
    )
    return replace(
        tiny_catalog,
        equipment=tuple(equipment),
        skills=(*tiny_catalog.skills, extra_series, extra_group),
    )


@pytest.fixture(scope="session")
def tiny_browser_catalog(
    tiny_catalog: Catalog,
    tiny_sha256: str,
) -> dict[str, object]:
    return build_browser_search_catalog(
        catalog=tiny_catalog,
        source_catalog_sha256=tiny_sha256,
    )


@pytest.fixture(scope="session")
def valid_report_bundle(
    tiny_catalog: Catalog,
    tiny_sha256: str,
    tiny_browser_catalog: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    request_payload = {
        "requirements": [],
        "preferences": [
            {"skill_id": "skill:attack-boost", "target_level": 1},
        ],
        "max_results": 1,
    }
    cases = ({"name": "normal-preferred", "request": request_payload},)
    oracle_body = build_browser_solver_oracle_report(
        catalog=tiny_catalog,
        cases=cases,
        timeout_seconds=5,
    )
    oracle_report = {
        "format_version": oracle_body["format_version"],
        "source_catalog_sha256": tiny_sha256,
        "timeout_seconds": oracle_body["timeout_seconds"],
        "omitted_cases": oracle_body["omitted_cases"],
        "cases": oracle_body["cases"],
    }

    request = decode_ranked_search_request_payload(payload=request_payload)
    result = search_catalog_ranked_build_candidates_with_cp_sat(
        catalog=tiny_catalog,
        requirements=request.requirements,
        preferences=request.preferences,
        max_results=1,
        timeout_seconds=5,
    )
    assert not result.timed_out
    candidate = result.candidates[0]
    prepared = _prepare_expanded_equipment(
        catalog=tiny_catalog,
        maximum_expanded_equipment=500_000,
    )
    selected_variant_ids = [
        next(
            variant_id
            for variant_id, definition in enumerate(prepared.expanded)
            if definition == selected
        )
        for selected in candidate.equipment
    ]
    preference_score = calculate_skill_preference_score(
        skill_levels=dict(candidate.skill_levels),
        preferences=request.preferences,
    )
    candidate_response = build_candidate_to_response(candidate=candidate)
    candidate_response["preference_score"] = preference_score
    browser_report = {
        "format_version": 1,
        "source_catalog_sha256": tiny_sha256,
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
                    "preference_score": preference_score,
                    "decoration_count": len(candidate.placements),
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
    assert tiny_browser_catalog["format_version"] == 1
    return oracle_report, browser_report
