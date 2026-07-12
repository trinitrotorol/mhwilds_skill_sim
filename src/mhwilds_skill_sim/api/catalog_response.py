"""API response serializer for Catalog metadata."""

from __future__ import annotations

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart, WeaponKind


def build_catalog_metadata_response(
    *,
    catalog: Catalog,
) -> dict[str, object]:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")

    available_weapon_kinds = {
        equipment.weapon_kind
        for equipment in catalog.equipment
        if equipment.part is EquipmentPart.WEAPON and equipment.weapon_kind is not None
    }

    return {
        "schema_version": catalog.schema_version,
        "skills": [
            {
                "skill_id": skill.skill_id,
                "display_name": skill.display_name,
                "kind": skill.kind.value,
                "max_level": skill.ranks[-1].level,
                "ranks": [
                    {
                        "level": rank.level,
                        "required_pieces": rank.required_pieces,
                    }
                    for rank in skill.ranks
                ],
            }
            for skill in catalog.skills
        ],
        "weapon_kinds": [
            weapon_kind.value
            for weapon_kind in WeaponKind
            if weapon_kind in available_weapon_kinds
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
                    {
                        "skill_id": skill.skill_id,
                        "level": skill.level,
                    }
                    for skill in decoration.skills
                ],
            }
            for decoration in catalog.decorations
        ],
        "features": {
            "artian_series_skill_assignment": any(
                equipment.allows_series_skill_assignment
                for equipment in catalog.equipment
            ),
            "artian_group_skill_assignment": any(
                equipment.allows_group_skill_assignment
                for equipment in catalog.equipment
            ),
            "theoretical_appraisal_charms": bool(
                catalog.appraisal_charm_skill_groups
                and catalog.appraisal_charm_patterns
            ),
        },
        "counts": {
            "skills": len(catalog.skills),
            "equipment": len(catalog.equipment),
            "decorations": len(catalog.decorations),
            "appraisal_charm_skill_groups": len(catalog.appraisal_charm_skill_groups),
            "appraisal_charm_patterns": len(catalog.appraisal_charm_patterns),
        },
    }
