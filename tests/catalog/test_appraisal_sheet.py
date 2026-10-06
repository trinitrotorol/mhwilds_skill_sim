from __future__ import annotations

import json
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.appraisal_rule_import import (
    normalize_appraisal_charm_rule_snapshot,
)
from mhwilds_skill_sim.catalog.appraisal_sheet import (
    ENGLISH_SKILLS_URL,
    GROUPS_URL,
    PATTERNS_URL,
    extract_appraisal_rule_snapshot,
)
from mhwilds_skill_sim.catalog.decoder import decode_skill_definition
from scripts.sync_appraisal_sheet import fetch_source, sync_files

# Explicitly synthetic, minimal CSV layout; no live source data in unit tests.
GROUPS = (
    ",,,,,,\n,Group 1,,,Group 2,\n"
    ",Skill Name,Skill Level,,Skill Name,Skill Level\n"
    ",Sample Weapon,1,,Sample Armor,2\n"
)
PATTERNS = (
    "Rarity,Skill 1 Group,Skill 2 Group,Skill 3 Group,Possible Slot Combos\n"
    'RARE[7],1,2,-,"[1,0] [2,0] [3,0]"\n'
    'RARE[8],1,2,-,"[W1,0] [W1,1] [W1,1,1]"\n'
)


def english_skills() -> list[dict[str, object]]:
    return [
        {
            "gameId": 10,
            "name": "Sample Weapon",
            "kind": "weapon",
            "ranks": [{"level": 1}, {"level": 2}],
        },
        {
            "gameId": 20,
            "name": "Sample Armor",
            "kind": "armor",
            "ranks": [{"level": 1}, {"level": 2}],
        },
    ]


def canonical_skill_values() -> list[dict[str, object]]:
    return [
        {
            "skill_id": "mhdb:skill:10",
            "display_name": "武器試験",
            "kind": "weapon",
            "ranks": [
                {"level": 1, "required_pieces": None},
                {"level": 2, "required_pieces": None},
            ],
        },
        {
            "skill_id": "mhdb:skill:20",
            "display_name": "防具試験",
            "kind": "armor",
            "ranks": [
                {"level": 1, "required_pieces": None},
                {"level": 2, "required_pieces": None},
            ],
        },
    ]


def definitions():
    return tuple(decode_skill_definition(value=s) for s in canonical_skill_values())


def extract(groups: str = GROUPS, patterns: str = PATTERNS, english=None):
    return extract_appraisal_rule_snapshot(
        groups_csv=groups,
        patterns_csv=patterns,
        english_skills=english_skills() if english is None else english,
        skill_definitions=definitions(),
    )


def test_exact_cross_locale_game_ids_and_slot_semantics() -> None:
    rules = extract()
    assert rules["groups"] == {"1": {"武器試験": 1}, "2": {"防具試験": 2}}
    normalized = normalize_appraisal_charm_rule_snapshot(
        value=rules,
        skill_definitions=definitions(),
    )
    assert len(normalized["appraisal_charm_patterns"]) == 6
    groups = normalized["appraisal_charm_skill_groups"]
    assert groups[0]["skills"] == [{"skill_id": "mhdb:skill:10", "level": 1}]
    patterns = normalized["appraisal_charm_patterns"]
    assert patterns[2]["slots"] == [{"kind": "armor", "level": 3}]
    assert patterns[3]["slots"] == [{"kind": "weapon", "level": 1}]
    assert patterns[5]["slots"] == [
        {"kind": "weapon", "level": 1},
        {"kind": "armor", "level": 1},
        {"kind": "armor", "level": 1},
    ]


def test_repeated_group_ids_preserved_without_aggregating_choices() -> None:
    rules = extract(patterns=PATTERNS.replace("1,2,-", "1,1,2"))
    assert rules["rarity_patterns"]["8"][0]["skill_patterns"] == [["1", "1", "2"]]


@pytest.mark.parametrize(
    "groups",
    [
        GROUPS.replace("Group 2", "Group 1"),
        GROUPS.replace("Skill Level", "Bad Header", 1),
        GROUPS.replace("Sample Weapon", "Unconfirmed Alias"),
        GROUPS.replace("Sample Weapon,1", "Sample Weapon,0"),
        GROUPS.replace("Sample Weapon,1", "Sample Weapon,1.5"),
        GROUPS.replace("Sample Weapon,1", "Sample Weapon,"),
        GROUPS + ",Sample Weapon,1,,,,\n",
        GROUPS.replace(",Sample Weapon,1,,Sample Armor,2\n", ""),
    ],
)
def test_rejects_bad_group_data_without_guessing_names(groups: str) -> None:
    with pytest.raises(ValueError):
        extract(groups=groups)


@pytest.mark.parametrize(
    "patterns",
    [
        PATTERNS.replace("Rarity", "Wrong Header", 1),
        PATTERNS.replace("1,2,-", "1,99,-"),
        PATTERNS.replace("1,2,-", "1,-,2"),
        PATTERNS.replace("RARE[8]", "RARE[0]"),
        PATTERNS.replace("[W1,1]", "[W1,0,1]"),
        PATTERNS.replace("[2,0]", "[0,2]"),
        PATTERNS.replace("[W1,1]", "[W1,1,1,1]"),
        PATTERNS.replace("[2,0]", "[1,0]"),
        PATTERNS + PATTERNS.splitlines()[1] + "\n",
    ],
)
def test_rejects_malformed_patterns_instead_of_dropping_rows(patterns: str) -> None:
    with pytest.raises(ValueError):
        extract(patterns=patterns)


def test_rejects_ambiguous_english_names_or_locale_rank_drift() -> None:
    english = english_skills()
    english.append({**english[0], "gameId": 30})
    with pytest.raises(ValueError, match="Ambiguous"):
        extract(english=english)
    english = english_skills()
    english[0]["ranks"] = [{"level": 1}]
    with pytest.raises(ValueError, match="maximum differs"):
        extract(english=english)


def test_explicit_sources_and_hashes_without_live_network(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "skills": canonical_skill_values(),
                "equipment": [],
                "decorations": [],
            }
        ),
        encoding="utf-8",
    )
    patterns = tmp_path / "input-patterns.csv"
    groups = tmp_path / "input-groups.csv"
    english = tmp_path / "input-english.json"
    patterns.write_text(PATTERNS, encoding="utf-8")
    groups.write_text(GROUPS, encoding="utf-8")
    english.write_text(json.dumps(english_skills()), encoding="utf-8")
    output = tmp_path / "rules.json"
    metadata = sync_files(
        catalog_path=catalog,
        raw_directory=tmp_path / "raw",
        rule_output_path=output,
        patterns_csv=patterns,
        groups_csv=groups,
        english_skills_json=english,
    )
    assert json.loads(output.read_text()) == extract()
    assert [s["url"] for s in metadata["sources"]] == [
        PATTERNS_URL,
        GROUPS_URL,
        ENGLISH_SKILLS_URL,
    ]
    assert all(len(s["sha256"]) == 64 for s in metadata["sources"])
    assert "No explicit" in metadata["license"]
    before = output.read_bytes()
    groups.write_text("malformed", encoding="utf-8")
    with pytest.raises(ValueError):
        sync_files(
            catalog_path=catalog,
            raw_directory=tmp_path / "raw",
            rule_output_path=output,
            patterns_csv=patterns,
            groups_csv=groups,
            english_skills_json=english,
        )
    assert output.read_bytes() == before


def test_fetch_rejects_untrusted_urls_without_network() -> None:
    with pytest.raises(ValueError, match="documented"):
        fetch_source("https://evil.example/")
    with pytest.raises(ValueError, match="timeout"):
        fetch_source(PATTERNS_URL, timeout_seconds=float("nan"))
