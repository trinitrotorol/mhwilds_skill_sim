"""Checker projection from the canonical normalized game catalog."""

from __future__ import annotations

import re
from datetime import datetime

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart


def validate_generated_at(value: str) -> str:
    """Keep generated timestamps compatible with the shared checker contract."""
    if (
        not isinstance(value, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z", value)
        is None
    ):
        raise ValueError("generated_at must be a UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("generated_at must be a valid UTC timestamp") from error
    return value


def appraisal_rules(catalog: Catalog) -> dict[str, object]:
    """Preserve canonical group choices and ordered pattern slots."""
    return {
        "appraisal_charm_skill_groups": [
            {
                "group_id": group.group_id,
                "skills": [
                    {"skill_id": skill.skill_id, "level": skill.level}
                    for skill in group.skills
                ],
            }
            for group in catalog.appraisal_charm_skill_groups
        ],
        "appraisal_charm_patterns": [
            {
                "pattern_id": pattern.pattern_id,
                "rarity": pattern.rarity,
                "skill_group_ids": list(pattern.skill_group_ids),
                "slots": [
                    {"kind": slot.kind.value, "level": slot.level}
                    for slot in pattern.slots
                ],
            }
            for pattern in catalog.appraisal_charm_patterns
        ],
    }


def build_checker_catalog(
    *, catalog: Catalog, revision: str, generated_at: str
) -> dict[str, object]:
    """Export IDs unchanged. Never infer names, rarity, or missing game rules."""
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise ValueError("revision must be a normalized source SHA-256")
    validate_generated_at(generated_at)
    return {
        "schema_version": 1,
        "revision": revision,
        "generated_at": generated_at,
        "skills": [
            {
                "skill_id": skill.skill_id,
                "display_name": skill.display_name,
                "kind": skill.kind.value,
                "ranks": [
                    {"level": rank.level, "required_pieces": rank.required_pieces}
                    for rank in skill.ranks
                ],
            }
            for skill in catalog.skills
        ],
        "decorations": [
            {
                "decoration_id": decoration.decoration_id,
                "display_name": decoration.display_name,
                "required_slot": {
                    "kind": decoration.required_slot.kind.value,
                    "level": decoration.required_slot.level,
                },
                "skills": [
                    {"skill_id": skill.skill_id, "level": skill.level}
                    for skill in decoration.skills
                ],
            }
            for decoration in catalog.decorations
        ],
        "fixed_charms": [
            {
                "equipment_id": charm.equipment_id,
                "display_name": charm.display_name,
                "skills": [
                    {"skill_id": skill.skill_id, "level": skill.level}
                    for skill in charm.skills
                ],
                "slots": [
                    {"kind": slot.kind.value, "level": slot.level}
                    for slot in charm.slots
                ],
            }
            for charm in catalog.equipment
            if charm.part is EquipmentPart.CHARM
        ],
        **appraisal_rules(catalog),
    }
