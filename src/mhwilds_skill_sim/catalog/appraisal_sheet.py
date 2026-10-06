"""Extract numeric appraisal facts from the attributed public community sheet.

No spreadsheet formulas, code, prose, styling or images are republished. English
names are transient joins to MHDB game IDs; persistent references use those IDs
through the existing canonical normalizer.
"""

from __future__ import annotations

import csv
import io
import re
from typing import cast

from mhwilds_skill_sim.catalog.appraisal_rule_import import (
    normalize_appraisal_charm_rule_snapshot,
)
from mhwilds_skill_sim.catalog.mhdb_skills import normalize_mhdb_skill_snapshot
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind

SHEET_ID = "1fpkamu1VzEpX8dZqecygW1GflKyvdY2975Y0d9SUt04"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
PATTERNS_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
)
GROUPS_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export"
    "?format=csv&gid=1054141820"
)
ENGLISH_SKILLS_URL = "https://wilds.mhdb.io/en/skills"
MAX_SOURCE_BYTES = 5 * 1024 * 1024


def _rows(text: str) -> list[list[str]]:
    if type(text) is not str or len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("CSV source must be text within the 5 MiB safety limit")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True))
    if not rows or len(rows) > 10_000 or any(len(row) > 100 for row in rows):
        raise ValueError("Unexpected spreadsheet dimensions")
    return [[cell.strip() for cell in row] for row in rows]


def _name_join(
    english_skills: object,
    skill_definitions: tuple[SkillDefinition, ...],
) -> dict[str, str]:
    normalized = normalize_mhdb_skill_snapshot(value=english_skills)
    canonical = {s.skill_id: s for s in skill_definitions}
    if len(canonical) != len(skill_definitions):
        raise ValueError("Canonical skill identifiers must be unique")
    names: dict[str, str] = {}
    seen_names: set[str] = set()
    for source in normalized:
        if source["kind"] not in ("weapon", "armor"):
            continue
        name = cast(str, source["display_name"])
        if name in seen_names:
            raise ValueError(f"Ambiguous English skill name: {name}")
        seen_names.add(name)
        target = canonical.get(cast(str, source["skill_id"]))
        if target is None:
            continue
        if target.kind not in (SkillKind.WEAPON, SkillKind.ARMOR):
            raise ValueError("Skill identity changes kind between locales")
        if target.kind.value != source["kind"]:
            raise ValueError("Skill identity changes kind between locales")
        if target.display_name is None:
            raise ValueError("Canonical appraisal skill has no display name")
        if len(target.ranks) != len(cast(list[object], source["ranks"])):
            raise ValueError("Skill maximum differs between locale snapshots")
        names[name] = target.display_name
    return names


def _groups(text: str, names: dict[str, str]) -> dict[str, dict[str, int]]:
    rows = _rows(text)
    headers = [
        (i, row)
        for i, row in enumerate(rows)
        if any(re.fullmatch(r"Group [1-9][0-9]*", cell) for cell in row)
    ]
    if len(headers) != 1:
        raise ValueError("Expected one group header row")
    header_index, header = headers[0]
    columns: dict[str, int] = {}
    for column, cell in enumerate(header):
        match = re.fullmatch(r"Group ([1-9][0-9]*)", cell)
        if match:
            group_id = match[1]
            if group_id in columns:
                raise ValueError("Duplicate source group")
            columns[group_id] = column
    if not columns or len(columns) > 100:
        raise ValueError("Missing or oversized groups")
    labels = rows[header_index + 1] if header_index + 1 < len(rows) else []
    groups: dict[str, dict[str, int]] = {}
    for group_id, column in columns.items():
        if labels[column : column + 2] != ["Skill Name", "Skill Level"]:
            raise ValueError(f"Unexpected skill columns in group {group_id}")
        group: dict[str, int] = {}
        for row in rows[header_index + 2 :]:
            skill_name = row[column] if column < len(row) else ""
            level_text = row[column + 1] if column + 1 < len(row) else ""
            if not skill_name and not level_text:
                continue
            if not skill_name or not re.fullmatch(r"[1-9][0-9]*", level_text):
                raise ValueError(f"Malformed skill row in group {group_id}")
            target_name = names.get(skill_name)
            if target_name is None:
                raise ValueError(f"Unknown exact English skill name: {skill_name}")
            if target_name in group:
                raise ValueError(f"Duplicate skill in group {group_id}")
            group[target_name] = int(level_text)
        if not group:
            raise ValueError(f"Empty group {group_id}")
        groups[group_id] = group
    return groups


def _slots(text: str) -> list[str]:
    tokens = re.findall(r"\[[^\[\]]+\]", text)
    if not tokens or " ".join(tokens) != text:
        raise ValueError("Malformed slot combination list")
    result: list[str] = []
    for token in tokens:
        values = token[1:-1].split(",")
        weapon = values[0].startswith("W")
        if weapon:
            if not re.fullmatch(r"W[1-9][0-9]*", values[0]):
                raise ValueError("Malformed weapon slot")
            prefix = f"[{int(values.pop(0)[1:])}]"
            positions = 2
        else:
            prefix = ""
            positions = 3
        if len(values) > positions or not values:
            raise ValueError("Invalid slot count")
        armor = ""
        empty_seen = False
        for value in values:
            if value == "0":
                empty_seen = True
                armor += "ー"
            elif value in ("1", "2", "3", "4") and not empty_seen:
                armor += "①②③④"[int(value) - 1]
            else:
                raise ValueError("Invalid armor slot level or order")
        notation = prefix + armor.ljust(positions, "ー")
        if notation in result:
            raise ValueError("Duplicate slot combination")
        result.append(notation)
    return result


def _patterns(text: str, group_ids: set[str]) -> dict[str, list[dict[str, object]]]:
    rows = _rows(text)
    expected = [
        "Rarity",
        "Skill 1 Group",
        "Skill 2 Group",
        "Skill 3 Group",
        "Possible Slot Combos",
    ]
    if rows[0][:5] != expected:
        raise ValueError("Unexpected pattern header")
    patterns: dict[str, list[dict[str, object]]] = {}
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for row in rows[1:]:
        if not row or not any(row[:5]):
            continue
        match = re.fullmatch(r"RARE\[([1-9][0-9]*)\]", row[0])
        if not match or len(row) < 5:
            raise ValueError("Unexpected non-pattern content in pattern columns")
        rarity = match[1]
        groups: list[str] = []
        empty_seen = False
        for cell in row[1:4]:
            if cell == "-":
                empty_seen = True
            elif cell in group_ids and not empty_seen:
                groups.append(cell)
            else:
                raise ValueError("Unknown group or interior empty skill position")
        if not groups:
            raise ValueError("Empty skill pattern")
        slots = _slots(row[4])
        key = (rarity, tuple(groups), tuple(slots))
        if key in seen:
            raise ValueError("Duplicate source pattern")
        seen.add(key)
        patterns.setdefault(rarity, []).append(
            {
                "slots": slots,
                "skill_patterns": [groups],
            }
        )
    if not patterns:
        raise ValueError("No appraisal patterns found")
    return patterns


def extract_appraisal_rule_snapshot(
    *,
    groups_csv: str,
    patterns_csv: str,
    english_skills: object,
    skill_definitions: tuple[SkillDefinition, ...],
) -> dict[str, object]:
    """Return the established raw rule format after full canonical validation."""
    groups = _groups(groups_csv, _name_join(english_skills, skill_definitions))
    snapshot: dict[str, object] = {
        "groups": groups,
        "rarity_patterns": _patterns(patterns_csv, set(groups)),
    }
    normalize_appraisal_charm_rule_snapshot(
        value=snapshot,
        skill_definitions=skill_definitions,
    )
    return snapshot
