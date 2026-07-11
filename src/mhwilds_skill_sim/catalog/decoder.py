"""Catalog value decoders."""

from __future__ import annotations

from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot

_SKILL_CONTRIBUTION_KEYS = frozenset(("skill_id", "level"))
_SKILL_CONTRIBUTION_KEY_ORDER = ("skill_id", "level")
_APPRAISAL_CHARM_SKILL_GROUP_KEYS = frozenset(("group_id", "skills"))
_APPRAISAL_CHARM_SKILL_GROUP_KEY_ORDER = ("group_id", "skills")
_APPRAISAL_CHARM_PATTERN_KEYS = frozenset(
    ("pattern_id", "rarity", "skill_group_ids", "slots")
)
_APPRAISAL_CHARM_PATTERN_KEY_ORDER = (
    "pattern_id",
    "rarity",
    "skill_group_ids",
    "slots",
)
_SKILL_RANK_DEFINITION_KEYS = frozenset(("level", "required_pieces"))
_SKILL_RANK_DEFINITION_KEY_ORDER = ("level", "required_pieces")
_SKILL_DEFINITION_KEYS = frozenset(("skill_id", "kind", "ranks", "display_name"))
_SKILL_DEFINITION_KEY_ORDER = ("skill_id", "kind", "ranks")
_DECORATION_SLOT_KEYS = frozenset(("kind", "level"))
_DECORATION_SLOT_KEY_ORDER = ("kind", "level")
_DECORATION_DEFINITION_KEYS = frozenset(
    ("decoration_id", "required_slot", "skills", "display_name"),
)
_DECORATION_DEFINITION_KEY_ORDER = ("decoration_id", "required_slot", "skills")
_EQUIPMENT_DEFINITION_KEYS = frozenset(
    (
        "equipment_id",
        "part",
        "skills",
        "slots",
        "series_skill_id",
        "group_skill_id",
        "allows_series_skill_assignment",
        "allows_group_skill_assignment",
        "display_name",
    )
)
_EQUIPMENT_DEFINITION_KEY_ORDER = ("equipment_id", "part", "skills", "slots")
_EQUIPMENT_PART_VALUES = ("weapon", "head", "chest", "arms", "waist", "legs", "charm")
_CATALOG_KEYS = frozenset(
    (
        "schema_version",
        "equipment",
        "decorations",
        "skills",
        "appraisal_charm_skill_groups",
        "appraisal_charm_patterns",
    )
)
_CATALOG_KEY_ORDER = ("schema_version", "equipment", "decorations")


def decode_skill_contribution(
    *,
    value: object,
    path: str = "$",
) -> SkillContribution:
    if type(value) is not dict:
        raise CatalogDecodeError(path=path, detail="expected skill contribution object")

    missing_keys = [key for key in _SKILL_CONTRIBUTION_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _SKILL_CONTRIBUTION_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    try:
        return SkillContribution(
            skill_id=value["skill_id"],
            level=value["level"],
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def decode_appraisal_charm_skill_group_definition(
    *,
    value: object,
    path: str = "$",
) -> AppraisalCharmSkillGroupDefinition:
    if type(value) is not dict:
        raise CatalogDecodeError(
            path=path,
            detail="expected appraisal charm skill group definition object",
        )

    missing_keys = [
        key for key in _APPRAISAL_CHARM_SKILL_GROUP_KEY_ORDER if key not in value
    ]
    extra_keys = [key for key in value if key not in _APPRAISAL_CHARM_SKILL_GROUP_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    if type(value["skills"]) is not list:
        raise CatalogDecodeError(
            path=f"{path}.skills",
            detail="skills must be list",
        )

    if not value["skills"]:
        raise CatalogDecodeError(
            path=f"{path}.skills",
            detail="skills must not be empty",
        )

    skills = tuple(
        decode_skill_contribution(
            value=skill,
            path=f"{path}.skills[{index}]",
        )
        for index, skill in enumerate(value["skills"])
    )

    try:
        return AppraisalCharmSkillGroupDefinition(
            group_id=value["group_id"],
            skills=skills,
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def decode_skill_rank_definition(
    *,
    value: object,
    path: str = "$",
) -> SkillRankDefinition:
    if type(value) is not dict:
        raise CatalogDecodeError(path=path, detail="expected skill rank object")

    missing_keys = [key for key in _SKILL_RANK_DEFINITION_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _SKILL_RANK_DEFINITION_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    try:
        return SkillRankDefinition(
            level=value["level"],
            required_pieces=value["required_pieces"],
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def decode_skill_definition(
    *,
    value: object,
    path: str = "$",
) -> SkillDefinition:
    if type(value) is not dict:
        raise CatalogDecodeError(path=path, detail="expected skill definition object")

    missing_keys = [key for key in _SKILL_DEFINITION_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _SKILL_DEFINITION_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    if type(value["ranks"]) is not list:
        raise CatalogDecodeError(path=f"{path}.ranks", detail="ranks must be list")

    if not value["ranks"]:
        raise CatalogDecodeError(path=f"{path}.ranks", detail="ranks must not be empty")

    ranks = tuple(
        decode_skill_rank_definition(value=rank, path=f"{path}.ranks[{index}]")
        for index, rank in enumerate(value["ranks"])
    )

    try:
        return SkillDefinition(
            skill_id=value["skill_id"],
            kind=_decode_skill_kind(value["kind"]),
            ranks=ranks,
            display_name=value.get("display_name"),
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def _decode_skill_kind(value: object) -> SkillKind:
    if type(value) is not str:
        raise TypeError("kind must be str")

    if value == SkillKind.ARMOR.value:
        return SkillKind.ARMOR
    if value == SkillKind.WEAPON.value:
        return SkillKind.WEAPON
    if value == SkillKind.SERIES.value:
        return SkillKind.SERIES
    if value == SkillKind.GROUP.value:
        return SkillKind.GROUP

    raise ValueError("kind must be one of: armor, weapon, set, group")


def decode_decoration_slot(
    *,
    value: object,
    path: str = "$",
) -> DecorationSlot:
    if type(value) is not dict:
        raise CatalogDecodeError(path=path, detail="expected decoration slot object")

    missing_keys = [key for key in _DECORATION_SLOT_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _DECORATION_SLOT_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    try:
        return DecorationSlot(
            kind=_decode_decoration_kind(value["kind"]),
            level=value["level"],
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def decode_appraisal_charm_pattern_definition(
    *,
    value: object,
    path: str = "$",
) -> AppraisalCharmPatternDefinition:
    if type(value) is not dict:
        raise CatalogDecodeError(
            path=path,
            detail="expected appraisal charm pattern definition object",
        )

    missing_keys = [
        key for key in _APPRAISAL_CHARM_PATTERN_KEY_ORDER if key not in value
    ]
    extra_keys = [key for key in value if key not in _APPRAISAL_CHARM_PATTERN_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    if type(value["skill_group_ids"]) is not list:
        raise CatalogDecodeError(
            path=f"{path}.skill_group_ids",
            detail="skill_group_ids must be list",
        )

    if type(value["slots"]) is not list:
        raise CatalogDecodeError(
            path=f"{path}.slots",
            detail="slots must be list",
        )

    skill_group_ids = tuple(value["skill_group_ids"])
    slots = tuple(
        decode_decoration_slot(
            value=slot,
            path=f"{path}.slots[{index}]",
        )
        for index, slot in enumerate(value["slots"])
    )

    try:
        return AppraisalCharmPatternDefinition(
            pattern_id=value["pattern_id"],
            rarity=value["rarity"],
            skill_group_ids=skill_group_ids,
            slots=slots,
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def _decode_decoration_kind(value: object) -> DecorationKind:
    if type(value) is not str:
        raise TypeError("kind must be str")

    if value == DecorationKind.WEAPON.value:
        return DecorationKind.WEAPON

    if value == DecorationKind.ARMOR.value:
        return DecorationKind.ARMOR

    raise ValueError("kind must be one of: weapon, armor")


def decode_decoration_definition(
    *,
    value: object,
    path: str = "$",
) -> DecorationDefinition:
    if type(value) is not dict:
        raise CatalogDecodeError(
            path=path, detail="expected decoration definition object"
        )

    missing_keys = [key for key in _DECORATION_DEFINITION_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _DECORATION_DEFINITION_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    required_slot = decode_decoration_slot(
        value=value["required_slot"],
        path=f"{path}.required_slot",
    )
    skills = _decode_decoration_skills(value=value["skills"], path=f"{path}.skills")

    try:
        return DecorationDefinition(
            decoration_id=value["decoration_id"],
            required_slot=required_slot,
            skills=skills,
            display_name=value.get("display_name"),
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def _decode_decoration_skills(
    *,
    value: object,
    path: str,
) -> tuple[SkillContribution, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(path=path, detail="skills must be list")

    if not value:
        raise CatalogDecodeError(path=path, detail="skills must not be empty")

    return tuple(
        decode_skill_contribution(value=skill, path=f"{path}[{index}]")
        for index, skill in enumerate(value)
    )


def decode_equipment_definition(
    *,
    value: object,
    path: str = "$",
) -> EquipmentDefinition:
    if type(value) is not dict:
        raise CatalogDecodeError(
            path=path, detail="expected equipment definition object"
        )

    missing_keys = [key for key in _EQUIPMENT_DEFINITION_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _EQUIPMENT_DEFINITION_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    try:
        part = _decode_equipment_part(value["part"])
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=f"{path}.part", detail=str(exc)) from exc

    skills = _decode_equipment_skills(value=value["skills"], path=f"{path}.skills")
    slots = _decode_equipment_slots(value=value["slots"], path=f"{path}.slots")

    try:
        return EquipmentDefinition(
            equipment_id=value["equipment_id"],
            part=part,
            skills=skills,
            slots=slots,
            series_skill_id=value.get("series_skill_id"),
            group_skill_id=value.get("group_skill_id"),
            allows_series_skill_assignment=value.get(
                "allows_series_skill_assignment",
                False,
            ),
            allows_group_skill_assignment=value.get(
                "allows_group_skill_assignment",
                False,
            ),
            display_name=value.get("display_name"),
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def _decode_equipment_part(value: object) -> EquipmentPart:
    if type(value) is not str:
        raise TypeError("part must be str")

    if value == EquipmentPart.WEAPON.value:
        return EquipmentPart.WEAPON
    if value == EquipmentPart.HEAD.value:
        return EquipmentPart.HEAD
    if value == EquipmentPart.CHEST.value:
        return EquipmentPart.CHEST
    if value == EquipmentPart.ARMS.value:
        return EquipmentPart.ARMS
    if value == EquipmentPart.WAIST.value:
        return EquipmentPart.WAIST
    if value == EquipmentPart.LEGS.value:
        return EquipmentPart.LEGS
    if value == EquipmentPart.CHARM.value:
        return EquipmentPart.CHARM

    raise ValueError("part must be one of: " + ", ".join(_EQUIPMENT_PART_VALUES))


def _decode_equipment_skills(
    *,
    value: object,
    path: str,
) -> tuple[SkillContribution, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(path=path, detail="skills must be list")

    return tuple(
        decode_skill_contribution(value=skill, path=f"{path}[{index}]")
        for index, skill in enumerate(value)
    )


def _decode_equipment_slots(
    *,
    value: object,
    path: str,
) -> tuple[DecorationSlot, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(path=path, detail="slots must be list")

    return tuple(
        decode_decoration_slot(value=slot, path=f"{path}[{index}]")
        for index, slot in enumerate(value)
    )


def decode_catalog(
    *,
    value: object,
    path: str = "$",
) -> Catalog:
    if type(value) is not dict:
        raise CatalogDecodeError(path=path, detail="expected catalog object")

    missing_keys = [key for key in _CATALOG_KEY_ORDER if key not in value]
    extra_keys = [key for key in value if key not in _CATALOG_KEYS]

    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append(f"missing keys: {', '.join(missing_keys)}")
        if extra_keys:
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in _sort_keys(extra_keys)),
            )
        raise CatalogDecodeError(path=path, detail="; ".join(detail_parts))

    try:
        schema_version = _decode_schema_version(value["schema_version"])
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(
            path=f"{path}.schema_version",
            detail=str(exc),
        ) from exc

    equipment = _decode_catalog_equipment(
        value=value["equipment"],
        path=f"{path}.equipment",
    )
    decorations = _decode_catalog_decorations(
        value=value["decorations"],
        path=f"{path}.decorations",
    )
    skills = (
        _decode_catalog_skills(
            value=value["skills"],
            path=f"{path}.skills",
        )
        if "skills" in value
        else ()
    )
    appraisal_charm_skill_groups = (
        _decode_catalog_appraisal_charm_skill_groups(
            value=value["appraisal_charm_skill_groups"],
            path=f"{path}.appraisal_charm_skill_groups",
        )
        if "appraisal_charm_skill_groups" in value
        else ()
    )
    appraisal_charm_patterns = (
        _decode_catalog_appraisal_charm_patterns(
            value=value["appraisal_charm_patterns"],
            path=f"{path}.appraisal_charm_patterns",
        )
        if "appraisal_charm_patterns" in value
        else ()
    )

    try:
        return Catalog(
            schema_version=schema_version,
            equipment=equipment,
            decorations=decorations,
            skills=skills,
            appraisal_charm_skill_groups=appraisal_charm_skill_groups,
            appraisal_charm_patterns=appraisal_charm_patterns,
        )
    except (TypeError, ValueError) as exc:
        raise CatalogDecodeError(path=path, detail=str(exc)) from exc


def _decode_schema_version(value: object) -> int:
    if type(value) is not int:
        raise TypeError("schema_version must be int")

    if value < 1:
        raise ValueError("schema_version must be at least 1")

    return value


def _decode_catalog_equipment(
    *,
    value: object,
    path: str,
) -> tuple[EquipmentDefinition, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(path=path, detail="equipment must be list")

    return tuple(
        decode_equipment_definition(value=equipment, path=f"{path}[{index}]")
        for index, equipment in enumerate(value)
    )


def _decode_catalog_decorations(
    *,
    value: object,
    path: str,
) -> tuple[DecorationDefinition, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(path=path, detail="decorations must be list")

    return tuple(
        decode_decoration_definition(value=decoration, path=f"{path}[{index}]")
        for index, decoration in enumerate(value)
    )


def _decode_catalog_skills(
    *,
    value: object,
    path: str,
) -> tuple[SkillDefinition, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(path=path, detail="skills must be list")

    return tuple(
        decode_skill_definition(value=skill, path=f"{path}[{index}]")
        for index, skill in enumerate(value)
    )


def _decode_catalog_appraisal_charm_skill_groups(
    *,
    value: object,
    path: str,
) -> tuple[AppraisalCharmSkillGroupDefinition, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(
            path=path,
            detail="appraisal_charm_skill_groups must be list",
        )

    return tuple(
        decode_appraisal_charm_skill_group_definition(
            value=group,
            path=f"{path}[{index}]",
        )
        for index, group in enumerate(value)
    )


def _decode_catalog_appraisal_charm_patterns(
    *,
    value: object,
    path: str,
) -> tuple[AppraisalCharmPatternDefinition, ...]:
    if type(value) is not list:
        raise CatalogDecodeError(
            path=path,
            detail="appraisal_charm_patterns must be list",
        )

    return tuple(
        decode_appraisal_charm_pattern_definition(
            value=pattern,
            path=f"{path}[{index}]",
        )
        for index, pattern in enumerate(value)
    )


def _sort_keys(keys: list[object]) -> list[object]:
    return sorted(keys, key=lambda key: (_format_key(key), type(key).__module__))


def _format_key(key: object) -> str:
    if type(key) is str:
        return key

    if type(key) in (int, float, bool, bytes, tuple, frozenset, type(None)):
        return repr(key)

    return f"<{type(key).__module__}.{type(key).__qualname__}>"
