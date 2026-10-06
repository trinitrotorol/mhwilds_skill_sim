"""The committed multi-result inventory oracle is checked by both solver engines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.solver.inventory import decode_inventory_search_snapshot
from mhwilds_skill_sim.solver.inventory_search import search_inventory_ranked_builds
from mhwilds_skill_sim.solver.preferences import (
    SkillPreference,
    calculate_skill_preference_score,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement


ORACLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "apps/web/src/browser-solver/fixtures/inventory-oracle.json"
)
CASES = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_inventory_multi_result_oracle(case, tiny_catalog: Catalog, tiny_sha256: str):
    request = case["request"]
    preferences = tuple(SkillPreference(**item) for item in request["preferences"])
    result = search_inventory_ranked_builds(
        catalog=tiny_catalog,
        catalog_revision=tiny_sha256,
        snapshot=decode_inventory_search_snapshot(request["inventory"]),
        requirements=tuple(
            SkillRequirement(**item) for item in request["requirements"]
        ),
        preferences=preferences,
        max_results=request["max_results"],
    )
    assert not result.timed_out
    assert result.exhausted == case["exhausted"]
    assert [
        {
            "equipment_ids": [item.equipment_id for item in build.equipment],
            "preference_score": calculate_skill_preference_score(
                skill_levels=dict(build.skill_levels),
                preferences=preferences,
            ),
            "decoration_count": len(build.placements),
        }
        for build in result.candidates
    ] == case["expected"]
