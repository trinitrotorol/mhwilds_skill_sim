"""Normalize offline MHDB armor-set and armor snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_equipment_definition,
    decode_skill_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.mhdb_decorations import (
    normalize_mhdb_decoration_snapshot,
)
from mhwilds_skill_sim.catalog.mhdb_skills import normalize_mhdb_skill_snapshot
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind

_RAW_ARMOR_SET_REQUIRED_KEYS = (
    "id",
    "gameId",
    "setBonusSkill",
    "groupBonusSkill",
)
_RAW_ARMOR_REQUIRED_KEYS = ("id", "name", "kind", "slots", "skills", "armorSet")
_SUPPORTED_ARMOR_KINDS = ("head", "chest", "arms", "waist", "legs")


@dataclass(frozen=True, slots=True)
class _ArmorSetReference:
    game_id: int
    series_skill_id: str | None
    group_skill_id: str | None


def normalize_mhdb_armor_snapshot(
    *,
    value: object,
    armor_set_snapshot: object,
    skill_snapshot: object,
    path: str = "$.armor",
    armor_set_path: str = "$.armor_sets",
    skill_path: str = "$.skills",
) -> list[dict[str, object]]:
    _, skills_by_id = _normalize_and_index_skills(
        skill_snapshot=skill_snapshot,
        skill_path=skill_path,
    )
    return _normalize_armor_snapshot(
        value=value,
        armor_set_snapshot=armor_set_snapshot,
        skills_by_id=skills_by_id,
        path=path,
        armor_set_path=armor_set_path,
    )


def build_skill_armor_and_decoration_catalog_document(
    *,
    skill_value: object,
    armor_set_value: object,
    armor_value: object,
    decoration_value: object,
    skill_path: str = "$.skills",
    armor_set_path: str = "$.armor_sets",
    armor_path: str = "$.armor",
    decoration_path: str = "$.decorations",
) -> dict[str, object]:
    normalized_skills, skills_by_id = _normalize_and_index_skills(
        skill_snapshot=skill_value,
        skill_path=skill_path,
    )
    normalized_armor = _normalize_armor_snapshot(
        value=armor_value,
        armor_set_snapshot=armor_set_value,
        skills_by_id=skills_by_id,
        path=armor_path,
        armor_set_path=armor_set_path,
    )
    normalized_decorations = normalize_mhdb_decoration_snapshot(
        value=decoration_value,
        skill_snapshot=skill_value,
        path=decoration_path,
        skill_path=skill_path,
    )
    document = {
        "schema_version": 1,
        "skills": normalized_skills,
        "equipment": normalized_armor,
        "decorations": normalized_decorations,
    }
    decode_catalog(value=document)
    return document


def _normalize_and_index_skills(
    *,
    skill_snapshot: object,
    skill_path: str,
) -> tuple[list[dict[str, object]], dict[str, SkillDefinition]]:
    normalized_skills = normalize_mhdb_skill_snapshot(
        value=skill_snapshot,
        path=skill_path,
    )
    skills_by_id: dict[str, SkillDefinition] = {}
    for index, normalized_skill in enumerate(normalized_skills):
        skill = decode_skill_definition(
            value=normalized_skill,
            path=f"{skill_path}[{index}]",
        )
        skills_by_id[skill.skill_id] = skill
    return normalized_skills, skills_by_id


def _normalize_armor_snapshot(
    *,
    value: object,
    armor_set_snapshot: object,
    skills_by_id: dict[str, SkillDefinition],
    path: str,
    armor_set_path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB armor snapshot must be list"),
        )

    armor_sets_by_raw_id = _index_armor_sets(
        value=armor_set_snapshot,
        skills_by_id=skills_by_id,
        path=armor_set_path,
        armor_snapshot_is_empty=not value,
    )

    normalized_armor: list[dict[str, object]] = []
    seen_raw_ids: set[int] = set()
    seen_equipment_ids: set[str] = set()
    for index, raw_armor in enumerate(value):
        armor_path = f"{path}[{index}]"
        normalized_equipment, raw_id, equipment_id = _normalize_raw_armor(
            value=raw_armor,
            armor_sets_by_raw_id=armor_sets_by_raw_id,
            skills_by_id=skills_by_id,
            path=armor_path,
        )

        if raw_id in seen_raw_ids:
            _raise_normalization_error(
                path=f"{armor_path}.id",
                error=ValueError("id must not be duplicated"),
            )
        seen_raw_ids.add(raw_id)

        if equipment_id in seen_equipment_ids:
            _raise_normalization_error(
                path=f"{armor_path}.kind",
                error=ValueError(
                    "armor-set gameId and kind must form a unique equipment_id"
                ),
            )
        seen_equipment_ids.add(equipment_id)

        decode_equipment_definition(
            value=normalized_equipment,
            path=armor_path,
        )
        normalized_armor.append(normalized_equipment)

    return normalized_armor


def _index_armor_sets(
    *,
    value: object,
    skills_by_id: dict[str, SkillDefinition],
    path: str,
    armor_snapshot_is_empty: bool,
) -> dict[int, _ArmorSetReference]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB armor-set snapshot must be list"),
        )
    if not value and not armor_snapshot_is_empty:
        _raise_normalization_error(
            path=path,
            error=ValueError(
                "armor-set snapshot must not be empty when armor snapshot is not empty"
            ),
        )

    armor_sets_by_raw_id: dict[int, _ArmorSetReference] = {}
    seen_game_ids: set[int] = set()
    for index, raw_armor_set in enumerate(value):
        armor_set_path = f"{path}[{index}]"
        if type(raw_armor_set) is not dict:
            _raise_normalization_error(
                path=armor_set_path,
                error=TypeError("MHDB armor set must be object"),
            )

        for key in _RAW_ARMOR_SET_REQUIRED_KEYS:
            if key not in raw_armor_set:
                _raise_normalization_error(
                    path=f"{armor_set_path}.{key}",
                    error=ValueError(f"missing required key: {key}"),
                )

        raw_id = _decode_positive_int(
            value=raw_armor_set["id"],
            path=f"{armor_set_path}.id",
            field_name="id",
        )
        game_id = _decode_exact_int(
            value=raw_armor_set["gameId"],
            path=f"{armor_set_path}.gameId",
            field_name="gameId",
        )

        if raw_id in armor_sets_by_raw_id:
            _raise_normalization_error(
                path=f"{armor_set_path}.id",
                error=ValueError("id must not be duplicated"),
            )
        if game_id in seen_game_ids:
            _raise_normalization_error(
                path=f"{armor_set_path}.gameId",
                error=ValueError("gameId must not be duplicated"),
            )

        series_skill_id = _resolve_bonus_skill(
            value=raw_armor_set["setBonusSkill"],
            skills_by_id=skills_by_id,
            expected_kind=SkillKind.SERIES,
            path=f"{armor_set_path}.setBonusSkill",
            field_name="setBonusSkill",
        )
        group_skill_id = _resolve_bonus_skill(
            value=raw_armor_set["groupBonusSkill"],
            skills_by_id=skills_by_id,
            expected_kind=SkillKind.GROUP,
            path=f"{armor_set_path}.groupBonusSkill",
            field_name="groupBonusSkill",
        )

        armor_sets_by_raw_id[raw_id] = _ArmorSetReference(
            game_id=game_id,
            series_skill_id=series_skill_id,
            group_skill_id=group_skill_id,
        )
        seen_game_ids.add(game_id)

    return armor_sets_by_raw_id


def _resolve_bonus_skill(
    *,
    value: object,
    skills_by_id: dict[str, SkillDefinition],
    expected_kind: SkillKind,
    path: str,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError(f"{field_name} must be object or None"),
        )
    if "gameId" not in value:
        _raise_normalization_error(
            path=f"{path}.gameId",
            error=ValueError("missing required key: gameId"),
        )

    game_id = _decode_exact_int(
        value=value["gameId"],
        path=f"{path}.gameId",
        field_name=f"{field_name}.gameId",
    )
    skill_id = f"mhdb:skill:{game_id}"
    skill = skills_by_id.get(skill_id)
    if skill is None:
        _raise_normalization_error(
            path=f"{path}.gameId",
            error=ValueError(
                f"{field_name}.gameId must reference an existing raw skill gameId"
            ),
        )
    if skill.kind is not expected_kind:
        _raise_normalization_error(
            path=f"{path}.gameId",
            error=ValueError(
                f"{field_name}.gameId must reference a {expected_kind.name.lower()} skill"
            ),
        )
    return skill.skill_id


def _normalize_raw_armor(
    *,
    value: object,
    armor_sets_by_raw_id: dict[int, _ArmorSetReference],
    skills_by_id: dict[str, SkillDefinition],
    path: str,
) -> tuple[dict[str, object], int, str]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB armor must be object"),
        )

    for key in _RAW_ARMOR_REQUIRED_KEYS:
        if key not in value:
            _raise_normalization_error(
                path=f"{path}.{key}",
                error=ValueError(f"missing required key: {key}"),
            )

    raw_id = _decode_positive_int(
        value=value["id"],
        path=f"{path}.id",
        field_name="id",
    )
    name = _decode_name(value=value["name"], path=f"{path}.name")
    kind = _decode_armor_kind(value=value["kind"], path=f"{path}.kind")
    armor_set = _resolve_armor_set(
        value=value["armorSet"],
        armor_sets_by_raw_id=armor_sets_by_raw_id,
        path=f"{path}.armorSet",
    )
    slots = _normalize_slots(value=value["slots"], path=f"{path}.slots")
    skills = _normalize_armor_skills(
        value=value["skills"],
        skills_by_id=skills_by_id,
        path=f"{path}.skills",
    )
    equipment_id = f"mhdb:armor:{armor_set.game_id}:{kind}"

    return (
        {
            "equipment_id": equipment_id,
            "display_name": name,
            "part": kind,
            "skills": skills,
            "slots": slots,
            "series_skill_id": armor_set.series_skill_id,
            "group_skill_id": armor_set.group_skill_id,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        raw_id,
        equipment_id,
    )


def _resolve_armor_set(
    *,
    value: object,
    armor_sets_by_raw_id: dict[int, _ArmorSetReference],
    path: str,
) -> _ArmorSetReference:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("armorSet must be object"),
        )
    if "id" not in value:
        _raise_normalization_error(
            path=f"{path}.id",
            error=ValueError("missing required key: id"),
        )

    raw_id = _decode_positive_int(
        value=value["id"],
        path=f"{path}.id",
        field_name="armorSet.id",
    )
    armor_set = armor_sets_by_raw_id.get(raw_id)
    if armor_set is None:
        _raise_normalization_error(
            path=f"{path}.id",
            error=ValueError("armorSet.id must reference an existing raw armor-set id"),
        )
    return armor_set


def _normalize_slots(*, value: object, path: str) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("slots must be list"),
        )
    if len(value) > 3:
        _raise_normalization_error(
            path=path,
            error=ValueError("slots must contain at most three entries"),
        )

    return [
        {
            "kind": "armor",
            "level": _decode_positive_int(
                value=raw_level,
                path=f"{path}[{index}]",
                field_name="slot level",
            ),
        }
        for index, raw_level in enumerate(value)
    ]


def _normalize_armor_skills(
    *,
    value: object,
    skills_by_id: dict[str, SkillDefinition],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("skills must be list"),
        )

    return [
        _normalize_armor_skill(
            value=raw_skill_rank,
            skills_by_id=skills_by_id,
            path=f"{path}[{index}]",
        )
        for index, raw_skill_rank in enumerate(value)
    ]


def _normalize_armor_skill(
    *,
    value: object,
    skills_by_id: dict[str, SkillDefinition],
    path: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB armor skill rank must be object"),
        )
    for key in ("skill", "level"):
        if key not in value:
            _raise_normalization_error(
                path=f"{path}.{key}",
                error=ValueError(f"missing required key: {key}"),
            )

    raw_skill = value["skill"]
    if type(raw_skill) is not dict:
        _raise_normalization_error(
            path=f"{path}.skill",
            error=TypeError("skill must be object"),
        )
    if "gameId" not in raw_skill:
        _raise_normalization_error(
            path=f"{path}.skill.gameId",
            error=ValueError("missing required key: gameId"),
        )

    game_id = _decode_exact_int(
        value=raw_skill["gameId"],
        path=f"{path}.skill.gameId",
        field_name="skill.gameId",
    )
    skill = skills_by_id.get(f"mhdb:skill:{game_id}")
    if skill is None:
        _raise_normalization_error(
            path=f"{path}.skill.gameId",
            error=ValueError(
                "skill.gameId must reference an existing raw skill gameId"
            ),
        )

    level = _decode_positive_int(
        value=value["level"],
        path=f"{path}.level",
        field_name="level",
    )
    if level > skill.ranks[-1].level:
        _raise_normalization_error(
            path=f"{path}.level",
            error=ValueError("level must not exceed the referenced skill maximum rank"),
        )
    if skill.kind is not SkillKind.ARMOR:
        _raise_normalization_error(
            path=path,
            error=ValueError("skills must reference only armor skills"),
        )

    return {
        "skill_id": skill.skill_id,
        "level": level,
    }


def _decode_name(*, value: object, path: str) -> str:
    if type(value) is not str:
        _raise_normalization_error(
            path=path,
            error=TypeError("name must be str"),
        )
    if value == "":
        _raise_normalization_error(
            path=path,
            error=ValueError("name must not be empty"),
        )
    if value.strip() == "":
        _raise_normalization_error(
            path=path,
            error=ValueError("name must not be blank"),
        )
    if value != value.strip():
        _raise_normalization_error(
            path=path,
            error=ValueError("name must not have leading or trailing whitespace"),
        )
    return value


def _decode_armor_kind(*, value: object, path: str) -> str:
    if type(value) is not str:
        _raise_normalization_error(
            path=path,
            error=TypeError("kind must be str"),
        )
    if value not in _SUPPORTED_ARMOR_KINDS:
        _raise_normalization_error(
            path=path,
            error=ValueError("kind must be one of: head, chest, arms, waist, legs"),
        )
    return value


def _decode_exact_int(*, value: object, path: str, field_name: str) -> int:
    if type(value) is not int:
        _raise_normalization_error(
            path=path,
            error=TypeError(f"{field_name} must be int"),
        )
    return value


def _decode_positive_int(*, value: object, path: str, field_name: str) -> int:
    decoded = _decode_exact_int(value=value, path=path, field_name=field_name)
    if decoded < 1:
        _raise_normalization_error(
            path=path,
            error=ValueError(f"{field_name} must be at least 1"),
        )
    return decoded


def _raise_normalization_error(*, path: str, error: Exception) -> NoReturn:
    raise CatalogDecodeError(path=path, detail=str(error)) from error
