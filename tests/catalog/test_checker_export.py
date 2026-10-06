"""Shared checker projection must retain exact canonical IDs and rules."""

from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.checker_export import (
    build_checker_catalog,
    validate_generated_at,
)
from mhwilds_skill_sim.catalog.loader import load_catalog


def test_checker_projection_preserves_canonical_skills_charms_and_rules():
    catalog = load_catalog(path=Path("data/fixtures/tiny_catalog.json"))
    exported = build_checker_catalog(
        catalog=catalog, revision="a" * 64, generated_at="2026-10-06T00:00:00Z"
    )
    assert len(exported["decorations"]) == len(catalog.decorations)
    assert exported["revision"] == "a" * 64
    assert exported["appraisal_charm_patterns"][0]["skill_group_ids"] == list(
        catalog.appraisal_charm_patterns[0].skill_group_ids
    )
    assert exported["fixed_charms"]
    assert all(c["equipment_id"] for c in exported["fixed_charms"])
    assert exported["skills"][0]["skill_id"] == catalog.skills[0].skill_id


@pytest.mark.parametrize("revision", ["", "synthetic-latest", "a" * 63])
def test_checker_projection_rejects_fabricated_revision(revision):
    with pytest.raises(ValueError, match="SHA-256"):
        build_checker_catalog(
            catalog=load_catalog(path=Path("data/fixtures/tiny_catalog.json")),
            revision=revision,
            generated_at="2026-10-06T00:00:00Z",
        )


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-06T00:00:00+00:00",
        "2026-10-06T09:00:00+09:00",
        "2026-10-06T00:00:00.123456Z",
        "2026-10-06T00:00:00.1Z",
        "2026-10-06T00:00:00",
        "2026-02-30T00:00:00Z",
        "../../outside",
        "",
        None,
    ],
)
def test_checker_projection_rejects_timestamps_outside_shared_contract(value):
    with pytest.raises(ValueError, match="generated_at"):
        build_checker_catalog(
            catalog=load_catalog(path=Path("data/fixtures/tiny_catalog.json")),
            revision="a" * 64,
            generated_at=value,
        )


@pytest.mark.parametrize("value", ["2026-10-06T00:00:00Z", "2026-10-06T00:00:00.123Z"])
def test_shared_timestamp_accepts_seconds_or_milliseconds(value):
    assert validate_generated_at(value) == value
