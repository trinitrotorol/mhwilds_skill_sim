"""Normalize and merge offline appraisal charm rule snapshots."""

from __future__ import annotations

from copy import deepcopy
from typing import NoReturn, cast

from mhwilds_skill_sim.catalog.decoder import (
    decode_appraisal_charm_pattern_definition,
    decode_appraisal_charm_skill_group_definition,
    decode_catalog,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind

_ROOT_KEYS = ("groups", "rarity_patterns")
_ROOT_KEY_SET = frozenset(_ROOT_KEYS)
_PATTERN_BLOCK_KEYS = ("slots", "skill_patterns")
_PATTERN_BLOCK_KEY_SET = frozenset(_PATTERN_BLOCK_KEYS)
_ARMOR_SLOT_LEVELS = {
    "①": 1,
    "②": 2,
    "③": 3,
    "④": 4,
}
_EMPTY_SLOT_SYMBOL = "ー"


def normalize_appraisal_charm_rule_snapshot(
    *,
    value: object,
    skill_definitions: tuple[SkillDefinition, ...],
    path: str = "$.appraisal_rules",
) -> dict[str, object]:
    skills_by_display_name = _build_skill_name_index(skill_definitions)
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("appraisal rule snapshot must be object"),
        )
    _validate_exact_keys(
        value=value,
        required_keys=_ROOT_KEYS,
        allowed_keys=_ROOT_KEY_SET,
        path=path,
    )

    normalized_groups, group_ids_by_raw_id = _normalize_groups(
        value=value["groups"],
        skills_by_display_name=skills_by_display_name,
        path=f"{path}.groups",
    )
    normalized_patterns = _normalize_rarity_patterns(
        value=value["rarity_patterns"],
        group_ids_by_raw_id=group_ids_by_raw_id,
        path=f"{path}.rarity_patterns",
    )
    return {
        "appraisal_charm_skill_groups": normalized_groups,
        "appraisal_charm_patterns": normalized_patterns,
    }


def build_catalog_document_with_appraisal_charm_rules(
    *,
    catalog_value: object,
    rule_value: object,
    catalog_path: str = "$.catalog",
    rule_path: str = "$.appraisal_rules",
) -> dict[str, object]:
    if type(catalog_value) is not dict:
        raise CatalogDecodeError(
            path=catalog_path,
            detail="expected catalog object",
        )
    decoded_catalog = decode_catalog(value=catalog_value, path=catalog_path)

    has_group_key = "appraisal_charm_skill_groups" in catalog_value
    has_pattern_key = "appraisal_charm_patterns" in catalog_value
    if has_group_key != has_pattern_key:
        _raise_catalog_merge_error(
            path=catalog_path,
            error=ValueError(
                "source Catalog must omit both appraisal rule keys or contain both"
            ),
        )
    if (
        decoded_catalog.appraisal_charm_skill_groups
        or decoded_catalog.appraisal_charm_patterns
    ):
        _raise_catalog_merge_error(
            path=catalog_path,
            error=ValueError("source Catalog appraisal rules must be empty"),
        )

    normalized_rules = normalize_appraisal_charm_rule_snapshot(
        value=rule_value,
        skill_definitions=decoded_catalog.skills,
        path=rule_path,
    )
    source = cast(dict[str, object], catalog_value)
    document = {
        "schema_version": deepcopy(source["schema_version"]),
        "skills": deepcopy(source.get("skills", [])),
        "appraisal_charm_skill_groups": normalized_rules[
            "appraisal_charm_skill_groups"
        ],
        "appraisal_charm_patterns": normalized_rules["appraisal_charm_patterns"],
        "equipment": deepcopy(source["equipment"]),
        "decorations": deepcopy(source["decorations"]),
    }
    decode_catalog(value=document, path=catalog_path)
    return document


def _build_skill_name_index(
    skill_definitions: object,
) -> dict[str, SkillDefinition]:
    if type(skill_definitions) is not tuple:
        raise TypeError("skill_definitions must be tuple")

    skills_by_display_name: dict[str, SkillDefinition] = {}
    seen_skill_ids: set[str] = set()
    for index, skill in enumerate(skill_definitions):
        if not isinstance(skill, SkillDefinition):
            raise TypeError(f"skill_definitions[{index}] must be SkillDefinition")
        if skill.skill_id in seen_skill_ids:
            raise ValueError(
                "skill_definitions must not contain duplicate skill_id: "
                f"{skill.skill_id}"
            )
        seen_skill_ids.add(skill.skill_id)

        if skill.kind not in (SkillKind.ARMOR, SkillKind.WEAPON):
            continue
        if skill.display_name is None:
            continue
        if skill.display_name in skills_by_display_name:
            raise ValueError(
                f"skill_definitions has ambiguous display name: {skill.display_name}"
            )
        skills_by_display_name[skill.display_name] = skill

    return skills_by_display_name


def _normalize_groups(
    *,
    value: object,
    skills_by_display_name: dict[str, SkillDefinition],
    path: str,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("groups must be object"),
        )
    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("groups must not be empty"),
        )

    raw_groups = cast(dict[object, object], value)
    validated_group_ids: list[str] = []
    for raw_group_id in raw_groups:
        group_path = _key_path(path, raw_group_id)
        try:
            validated_group_ids.append(
                _validate_identifier(raw_group_id, field_name="group ID")
            )
        except (TypeError, ValueError) as exc:
            _raise_normalization_error(path=group_path, error=exc)

    normalized_groups: list[dict[str, object]] = []
    group_ids_by_raw_id: dict[str, str] = {}
    for raw_group_id in sorted(validated_group_ids):
        group_path = _key_path(path, raw_group_id)
        raw_group = raw_groups[raw_group_id]
        normalized_group_id = f"imported:appraisal-group:{raw_group_id}"
        normalized_group = _normalize_group(
            value=raw_group,
            normalized_group_id=normalized_group_id,
            skills_by_display_name=skills_by_display_name,
            path=group_path,
        )
        decode_appraisal_charm_skill_group_definition(
            value=normalized_group,
            path=group_path,
        )
        normalized_groups.append(normalized_group)
        group_ids_by_raw_id[raw_group_id] = normalized_group_id

    return normalized_groups, group_ids_by_raw_id


def _normalize_group(
    *,
    value: object,
    normalized_group_id: str,
    skills_by_display_name: dict[str, SkillDefinition],
    path: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("group must be object"),
        )
    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("group must not be empty"),
        )

    normalized_skills: list[dict[str, object]] = []
    seen_skill_ids: set[str] = set()
    for raw_display_name, raw_level in value.items():
        skill_path = _key_path(path, raw_display_name)
        try:
            display_name = _validate_identifier(
                raw_display_name,
                field_name="skill display name",
            )
        except (TypeError, ValueError) as exc:
            _raise_normalization_error(path=skill_path, error=exc)

        skill = skills_by_display_name.get(display_name)
        if skill is None:
            _raise_normalization_error(
                path=skill_path,
                error=ValueError(
                    f"unknown eligible skill display name: {display_name}"
                ),
            )
        level = _decode_positive_int(
            value=raw_level,
            path=skill_path,
            field_name="skill level",
        )
        if level > skill.ranks[-1].level:
            _raise_normalization_error(
                path=skill_path,
                error=ValueError(
                    "skill level must not exceed the referenced skill maximum rank"
                ),
            )
        if skill.skill_id in seen_skill_ids:
            _raise_normalization_error(
                path=skill_path,
                error=ValueError("group skills must not resolve to duplicate skill_id"),
            )
        seen_skill_ids.add(skill.skill_id)
        normalized_skills.append(
            {
                "skill_id": skill.skill_id,
                "level": level,
            }
        )

    return {
        "group_id": normalized_group_id,
        "skills": normalized_skills,
    }


def _normalize_rarity_patterns(
    *,
    value: object,
    group_ids_by_raw_id: dict[str, str],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("rarity_patterns must be object"),
        )

    raw_rarities = cast(dict[object, object], value)
    decoded_rarities: list[tuple[int, str]] = []
    for raw_rarity in raw_rarities:
        rarity_path = _key_path(path, raw_rarity)
        try:
            rarity = _decode_rarity_key(raw_rarity)
        except (TypeError, ValueError) as exc:
            _raise_normalization_error(path=rarity_path, error=exc)
        decoded_rarities.append((rarity, cast(str, raw_rarity)))

    normalized_patterns: list[dict[str, object]] = []
    seen_pattern_ids: set[str] = set()
    for rarity, raw_rarity in sorted(decoded_rarities):
        rarity_path = _key_path(path, raw_rarity)
        blocks = raw_rarities[raw_rarity]
        if type(blocks) is not list:
            _raise_normalization_error(
                path=rarity_path,
                error=TypeError("rarity pattern blocks must be list"),
            )
        for block_index, block in enumerate(blocks, start=1):
            block_path = f"{rarity_path}[{block_index - 1}]"
            for pattern in _normalize_pattern_block(
                value=block,
                rarity=rarity,
                block_index=block_index,
                group_ids_by_raw_id=group_ids_by_raw_id,
                path=block_path,
            ):
                pattern_id = cast(str, pattern["pattern_id"])
                if pattern_id in seen_pattern_ids:
                    _raise_normalization_error(
                        path=block_path,
                        error=ValueError("generated pattern_id must not be duplicated"),
                    )
                seen_pattern_ids.add(pattern_id)
                decode_appraisal_charm_pattern_definition(
                    value=pattern,
                    path=block_path,
                )
                normalized_patterns.append(pattern)

    return normalized_patterns


def _normalize_pattern_block(
    *,
    value: object,
    rarity: int,
    block_index: int,
    group_ids_by_raw_id: dict[str, str],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("rarity pattern block must be object"),
        )
    _validate_exact_keys(
        value=value,
        required_keys=_PATTERN_BLOCK_KEYS,
        allowed_keys=_PATTERN_BLOCK_KEY_SET,
        path=path,
    )
    parsed_slots = _normalize_slot_strings(
        value=value["slots"],
        path=f"{path}.slots",
    )
    skill_patterns = _normalize_skill_patterns(
        value=value["skill_patterns"],
        group_ids_by_raw_id=group_ids_by_raw_id,
        path=f"{path}.skill_patterns",
    )

    normalized_patterns: list[dict[str, object]] = []
    for skill_pattern_index, group_ids in enumerate(skill_patterns, start=1):
        for slot_index, slots in enumerate(parsed_slots, start=1):
            normalized_patterns.append(
                {
                    "pattern_id": (
                        f"imported:appraisal-pattern:rarity-{rarity}:"
                        f"block-{block_index}:skills-{skill_pattern_index}:"
                        f"slots-{slot_index}"
                    ),
                    "rarity": rarity,
                    "skill_group_ids": list(group_ids),
                    "slots": [dict(slot) for slot in slots],
                }
            )
    return normalized_patterns


def _normalize_slot_strings(
    *,
    value: object,
    path: str,
) -> list[list[dict[str, object]]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("slots must be list"),
        )
    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("slots must not be empty"),
        )

    parsed_slots: list[list[dict[str, object]]] = []
    for index, raw_slot in enumerate(value):
        slot_path = f"{path}[{index}]"
        if type(raw_slot) is not str:
            _raise_normalization_error(
                path=slot_path,
                error=TypeError("slot notation must be str"),
            )
        try:
            parsed_slots.append(_parse_slot_notation(raw_slot))
        except ValueError as exc:
            _raise_normalization_error(path=slot_path, error=exc)
    return parsed_slots


def _normalize_skill_patterns(
    *,
    value: object,
    group_ids_by_raw_id: dict[str, str],
    path: str,
) -> list[list[str]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("skill_patterns must be list"),
        )
    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("skill_patterns must not be empty"),
        )

    normalized_patterns: list[list[str]] = []
    for pattern_index, raw_pattern in enumerate(value):
        pattern_path = f"{path}[{pattern_index}]"
        if type(raw_pattern) is not list:
            _raise_normalization_error(
                path=pattern_path,
                error=TypeError("skill pattern must be list"),
            )
        if not 1 <= len(raw_pattern) <= 3:
            _raise_normalization_error(
                path=pattern_path,
                error=ValueError(
                    "skill pattern must contain between one and three group IDs"
                ),
            )

        normalized_group_ids: list[str] = []
        for group_index, raw_group_id in enumerate(raw_pattern):
            group_path = f"{pattern_path}[{group_index}]"
            try:
                group_id = _validate_identifier(
                    raw_group_id,
                    field_name="group ID",
                )
            except (TypeError, ValueError) as exc:
                _raise_normalization_error(path=group_path, error=exc)
            normalized_group_id = group_ids_by_raw_id.get(group_id)
            if normalized_group_id is None:
                _raise_normalization_error(
                    path=group_path,
                    error=ValueError(f"unknown group ID: {group_id}"),
                )
            normalized_group_ids.append(normalized_group_id)
        normalized_patterns.append(normalized_group_ids)

    return normalized_patterns


def _parse_slot_notation(value: str) -> list[dict[str, object]]:
    slots: list[dict[str, object]] = []
    if value.startswith("["):
        closing_bracket = value.find("]")
        if closing_bracket < 0:
            raise ValueError(
                f"invalid slot notation {value!r}: missing closing bracket"
            )
        weapon_level_text = value[1:closing_bracket]
        if not _is_canonical_positive_decimal(weapon_level_text):
            raise ValueError(
                f"invalid slot notation {value!r}: weapon level must be a "
                "canonical positive decimal integer"
            )
        armor_symbols = value[closing_bracket + 1 :]
        if len(armor_symbols) != 2:
            raise ValueError(
                f"invalid slot notation {value!r}: weapon form must have two "
                "armor positions"
            )
        slots.append({"kind": "weapon", "level": int(weapon_level_text)})
    else:
        armor_symbols = value
        if len(armor_symbols) != 3:
            raise ValueError(
                f"invalid slot notation {value!r}: armor form must have three positions"
            )

    empty_seen = False
    for symbol in armor_symbols:
        if symbol == _EMPTY_SLOT_SYMBOL:
            empty_seen = True
            continue
        level = _ARMOR_SLOT_LEVELS.get(symbol)
        if level is None:
            raise ValueError(
                f"invalid slot notation {value!r}: unknown armor slot symbol"
            )
        if empty_seen:
            raise ValueError(
                f"invalid slot notation {value!r}: armor slots must not contain "
                "an interior gap"
            )
        slots.append({"kind": "armor", "level": level})
    return slots


def _decode_rarity_key(value: object) -> int:
    if type(value) is not str:
        raise TypeError("rarity key must be str")
    if not _is_canonical_positive_decimal(value):
        raise ValueError("rarity key must be canonical positive decimal text")
    return int(value)


def _is_canonical_positive_decimal(value: str) -> bool:
    return (
        value != ""
        and value[0] != "0"
        and all("0" <= character <= "9" for character in value)
    )


def _validate_identifier(value: object, *, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")
    if value == "":
        raise ValueError(f"{field_name} must not be empty")
    if value.strip() == "":
        raise ValueError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have leading or trailing whitespace")
    return value


def _decode_positive_int(*, value: object, path: str, field_name: str) -> int:
    if type(value) is not int:
        _raise_normalization_error(
            path=path,
            error=TypeError(f"{field_name} must be int"),
        )
    if value < 1:
        _raise_normalization_error(
            path=path,
            error=ValueError(f"{field_name} must be at least 1"),
        )
    return value


def _validate_exact_keys(
    *,
    value: dict[object, object],
    required_keys: tuple[str, ...],
    allowed_keys: frozenset[str],
    path: str,
) -> None:
    missing_keys = [key for key in required_keys if key not in value]
    extra_keys = [key for key in value if key not in allowed_keys]
    if not missing_keys and not extra_keys:
        return

    details: list[str] = []
    if missing_keys:
        details.append("missing keys: " + ", ".join(missing_keys))
    if extra_keys:
        ordered_extra_keys = sorted(
            extra_keys,
            key=lambda key: (type(key).__name__, repr(key)),
        )
        details.append(
            "unexpected keys: "
            + ", ".join(_format_key(key) for key in ordered_extra_keys)
        )
    _raise_normalization_error(
        path=path,
        error=ValueError("; ".join(details)),
    )


def _key_path(path: str, key: object) -> str:
    return f"{path}.{key}" if type(key) is str else f"{path}[{key!r}]"


def _format_key(value: object) -> str:
    return value if type(value) is str else repr(value)


def _raise_normalization_error(*, path: str, error: Exception) -> NoReturn:
    raise CatalogDecodeError(path=path, detail=str(error)) from error


def _raise_catalog_merge_error(*, path: str, error: Exception) -> NoReturn:
    raise CatalogDecodeError(path=path, detail=str(error)) from error
