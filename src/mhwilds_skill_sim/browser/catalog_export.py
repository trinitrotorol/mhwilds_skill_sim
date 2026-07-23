"""Deterministic compact Catalog export for the browser solver spike."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillKind
from mhwilds_skill_sim.solver.appraisal_charms import (
    generate_appraisal_charm_equipment_candidates,
)
from mhwilds_skill_sim.solver.equipment_variants import (
    expand_equipment_bonus_skill_variants,
)


BROWSER_SEARCH_CATALOG_FORMAT_VERSION = 1
DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT = 500_000
_SOURCE_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_EQUIPMENT_PART_ORDER = tuple(EquipmentPart)


class BrowserCatalogSizeError(ValueError):
    """Raised before materialization when the expanded Catalog is too large."""

    def __init__(self, *, estimated_count: int, maximum_count: int) -> None:
        self.estimated_count = estimated_count
        self.maximum_count = maximum_count
        super().__init__(
            "estimated expanded equipment count "
            f"{estimated_count} exceeds limit {maximum_count}"
        )


@dataclass(frozen=True, slots=True)
class _PreparedEquipment:
    generated_appraisal_charm_count: int
    expanded: tuple[EquipmentDefinition, ...]


def build_browser_search_catalog(
    *,
    catalog: Catalog,
    source_catalog_sha256: str,
    maximum_expanded_equipment: int = DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
) -> dict[str, object]:
    """Convert a normalized Catalog into the compact browser search format."""

    _validate_catalog(catalog=catalog)
    _validate_source_catalog_sha256(value=source_catalog_sha256)
    _validate_maximum_expanded_equipment(value=maximum_expanded_equipment)

    prepared = _prepare_expanded_equipment(
        catalog=catalog,
        maximum_expanded_equipment=maximum_expanded_equipment,
    )
    skill_indexes = {
        definition.skill_id: index for index, definition in enumerate(catalog.skills)
    }

    skills: list[dict[str, object]] = []
    for definition in catalog.skills:
        skills.append(
            {
                "skill_id": definition.skill_id,
                "display_name": definition.display_name,
                "kind": definition.kind.value,
                "max_level": definition.ranks[-1].level,
                "required_pieces": (
                    [
                        _required_pieces(
                            skill_id=definition.skill_id,
                            value=rank.required_pieces,
                        )
                        for rank in definition.ranks
                    ]
                    if definition.kind in (SkillKind.SERIES, SkillKind.GROUP)
                    else []
                ),
            }
        )

    equipment_by_part: dict[str, object] = {
        part.value: [] for part in _EQUIPMENT_PART_ORDER
    }
    for variant_id, definition in enumerate(prepared.expanded):
        variants = equipment_by_part[definition.part.value]
        assert isinstance(variants, list)
        variants.append(
            {
                "variant_id": variant_id,
                "equipment_id": definition.equipment_id,
                "display_name": definition.display_name,
                "part": definition.part.value,
                "weapon_kind": (
                    definition.weapon_kind.value
                    if definition.weapon_kind is not None
                    else None
                ),
                "series_skill_id": _optional_skill_index(
                    skill_id=definition.series_skill_id,
                    skill_indexes=skill_indexes,
                    location=f"equipment {definition.equipment_id!r} series_skill_id",
                ),
                "group_skill_id": _optional_skill_index(
                    skill_id=definition.group_skill_id,
                    skill_indexes=skill_indexes,
                    location=f"equipment {definition.equipment_id!r} group_skill_id",
                ),
                "series_skill_ids": [
                    _skill_index(
                        skill_id=skill_id,
                        skill_indexes=skill_indexes,
                        location=(
                            f"equipment {definition.equipment_id!r} series_skill_ids"
                        ),
                    )
                    for skill_id in definition.series_skill_ids
                ],
                "group_skill_ids": [
                    _skill_index(
                        skill_id=skill_id,
                        skill_indexes=skill_indexes,
                        location=(
                            f"equipment {definition.equipment_id!r} group_skill_ids"
                        ),
                    )
                    for skill_id in definition.group_skill_ids
                ],
                "skills": [
                    [
                        _skill_index(
                            skill_id=contribution.skill_id,
                            skill_indexes=skill_indexes,
                            location=(f"equipment {definition.equipment_id!r} skills"),
                        ),
                        contribution.level,
                    ]
                    for contribution in definition.skills
                ],
                "slots": [[slot.kind.value, slot.level] for slot in definition.slots],
            }
        )

    decorations: list[dict[str, object]] = []
    for definition in catalog.decorations:
        decorations.append(
            {
                "decoration_id": definition.decoration_id,
                "display_name": definition.display_name,
                "required_slot": [
                    definition.required_slot.kind.value,
                    definition.required_slot.level,
                ],
                "skills": [
                    [
                        _skill_index(
                            skill_id=contribution.skill_id,
                            skill_indexes=skill_indexes,
                            location=(
                                f"decoration {definition.decoration_id!r} skills"
                            ),
                        ),
                        contribution.level,
                    ]
                    for contribution in definition.skills
                ],
            }
        )

    return {
        "format_version": BROWSER_SEARCH_CATALOG_FORMAT_VERSION,
        "source_catalog": {
            "schema_version": catalog.schema_version,
            "sha256": source_catalog_sha256,
            "source_equipment_count": len(catalog.equipment),
            "generated_appraisal_charm_count": (
                prepared.generated_appraisal_charm_count
            ),
            "expanded_equipment_count": len(prepared.expanded),
            "decoration_count": len(catalog.decorations),
            "skill_count": len(catalog.skills),
        },
        "skills": skills,
        "equipment_by_part": equipment_by_part,
        "decorations": decorations,
    }


def write_browser_search_catalog(
    *,
    value: dict[str, object],
    output_path: Path,
) -> None:
    """Write a compact browser Catalog using stable UTF-8/LF bytes."""

    if type(value) is not dict:
        raise TypeError("value must be dict")
    if not isinstance(output_path, Path):
        raise TypeError("output_path must be Path")

    content = (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)


def _prepare_expanded_equipment(
    *,
    catalog: Catalog,
    maximum_expanded_equipment: int,
) -> _PreparedEquipment:
    generated_charms = generate_appraisal_charm_equipment_candidates(
        skill_groups=catalog.appraisal_charm_skill_groups,
        patterns=catalog.appraisal_charm_patterns,
        skill_definitions=catalog.skills,
    )
    equipment_with_generated_charms = catalog.equipment + generated_charms

    series_option_count = sum(
        definition.kind is SkillKind.SERIES for definition in catalog.skills
    )
    group_option_count = sum(
        definition.kind is SkillKind.GROUP for definition in catalog.skills
    )
    estimated_count = sum(
        _equipment_expansion_multiplier(
            definition=definition,
            series_option_count=series_option_count,
            group_option_count=group_option_count,
        )
        for definition in equipment_with_generated_charms
    )
    if estimated_count > maximum_expanded_equipment:
        raise BrowserCatalogSizeError(
            estimated_count=estimated_count,
            maximum_count=maximum_expanded_equipment,
        )

    expanded = expand_equipment_bonus_skill_variants(
        equipment=equipment_with_generated_charms,
        skill_definitions=catalog.skills,
    )
    if len(expanded) != estimated_count:
        raise RuntimeError(
            "expanded equipment count does not match the preflight estimate"
        )
    part_major_expanded = tuple(
        definition
        for part in _EQUIPMENT_PART_ORDER
        for definition in expanded
        if definition.part is part
    )

    return _PreparedEquipment(
        generated_appraisal_charm_count=len(generated_charms),
        expanded=part_major_expanded,
    )


def _equipment_expansion_multiplier(
    *,
    definition: EquipmentDefinition,
    series_option_count: int,
    group_option_count: int,
) -> int:
    series_multiplier = (
        series_option_count if definition.allows_series_skill_assignment else 1
    )
    group_multiplier = (
        group_option_count if definition.allows_group_skill_assignment else 1
    )
    return series_multiplier * group_multiplier


def _validate_catalog(*, catalog: object) -> None:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")


def _validate_source_catalog_sha256(*, value: object) -> None:
    if type(value) is not str:
        raise TypeError("source_catalog_sha256 must be str")
    if _SOURCE_SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "source_catalog_sha256 must be lowercase 64-character hexadecimal"
        )


def _validate_maximum_expanded_equipment(*, value: object) -> None:
    if type(value) is not int:
        raise TypeError("maximum_expanded_equipment must be int")
    if value < 0:
        raise ValueError("maximum_expanded_equipment must be at least zero")


def _required_pieces(*, skill_id: str, value: int | None) -> int:
    if value is None:
        raise ValueError(f"bonus skill {skill_id!r} rank requires pieces")
    return value


def _optional_skill_index(
    *,
    skill_id: str | None,
    skill_indexes: dict[str, int],
    location: str,
) -> int | None:
    if skill_id is None:
        return None
    return _skill_index(
        skill_id=skill_id,
        skill_indexes=skill_indexes,
        location=location,
    )


def _skill_index(
    *,
    skill_id: str,
    skill_indexes: dict[str, int],
    location: str,
) -> int:
    try:
        return skill_indexes[skill_id]
    except KeyError as error:
        raise ValueError(f"{location} references unknown skill {skill_id!r}") from error
