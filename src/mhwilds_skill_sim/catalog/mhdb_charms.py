"""Normalize offline MHDB fixed charm snapshots."""

from __future__ import annotations

from typing import NoReturn, cast

from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_equipment_definition,
    decode_skill_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.mhdb_skills import normalize_mhdb_skill_snapshot
from mhwilds_skill_sim.catalog.mhdb_weapons import (
    build_skill_weapon_armor_and_decoration_catalog_document,
)
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind

_RAW_CHARM_REQUIRED_KEYS = ("id", "gameId", "ranks")
_RAW_RANK_REQUIRED_KEYS = ("id", "name", "level", "skills")
_RAW_SKILL_RANK_REQUIRED_KEYS = ("skill", "level")


def normalize_mhdb_charm_snapshot(
    *,
    value: object,
    skill_snapshot: object,
    path: str = "$.charms",
    skill_path: str = "$.skills",
) -> list[dict[str, object]]:
    _, skills_by_raw_id = _normalize_and_index_skills(
        skill_snapshot=skill_snapshot,
        skill_path=skill_path,
    )
    return _normalize_charms(
        value=value,
        skills_by_raw_id=skills_by_raw_id,
        path=path,
    )


def build_skill_weapon_armor_charm_and_decoration_catalog_document(
    *,
    skill_value: object,
    weapon_value: object,
    armor_set_value: object,
    armor_value: object,
    charm_value: object,
    decoration_value: object,
    skill_path: str = "$.skills",
    weapon_path: str = "$.weapons",
    armor_set_path: str = "$.armor_sets",
    armor_path: str = "$.armor",
    charm_path: str = "$.charms",
    decoration_path: str = "$.decorations",
) -> dict[str, object]:
    base_document = build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=skill_value,
        weapon_value=weapon_value,
        armor_set_value=armor_set_value,
        armor_value=armor_value,
        decoration_value=decoration_value,
        skill_path=skill_path,
        weapon_path=weapon_path,
        armor_set_path=armor_set_path,
        armor_path=armor_path,
        decoration_path=decoration_path,
    )
    normalized_charms = normalize_mhdb_charm_snapshot(
        value=charm_value,
        skill_snapshot=skill_value,
        path=charm_path,
        skill_path=skill_path,
    )
    base_equipment = cast(list[dict[str, object]], base_document["equipment"])
    document = {
        "schema_version": 1,
        "skills": base_document["skills"],
        "equipment": base_equipment + normalized_charms,
        "decorations": base_document["decorations"],
    }
    decode_catalog(value=document)
    return document


def _normalize_and_index_skills(
    *,
    skill_snapshot: object,
    skill_path: str,
) -> tuple[list[dict[str, object]], dict[int, SkillDefinition]]:
    normalized_skills = normalize_mhdb_skill_snapshot(
        value=skill_snapshot,
        path=skill_path,
    )

    raw_skills = cast(list[dict[str, object]], skill_snapshot)
    skills_by_raw_id: dict[int, SkillDefinition] = {}
    for index, (raw_skill, normalized_skill) in enumerate(
        zip(raw_skills, normalized_skills)
    ):
        raw_id_path = f"{skill_path}[{index}].id"
        if "id" not in raw_skill:
            _raise_normalization_error(
                path=raw_id_path,
                error=ValueError("missing required key: id"),
            )

        raw_id = _decode_positive_int(
            value=raw_skill["id"],
            path=raw_id_path,
            field_name="id",
        )
        if raw_id in skills_by_raw_id:
            _raise_normalization_error(
                path=raw_id_path,
                error=ValueError("id must not be duplicated"),
            )

        skills_by_raw_id[raw_id] = decode_skill_definition(
            value=normalized_skill,
            path=f"{skill_path}[{index}]",
        )

    return normalized_skills, skills_by_raw_id


def _normalize_charms(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB charm snapshot must be list"),
        )

    normalized_charms: list[dict[str, object]] = []
    seen_raw_ids: set[int] = set()
    seen_game_ids: set[int] = set()
    seen_equipment_ids: set[str] = set()
    for index, raw_charm in enumerate(value):
        charm_path = f"{path}[{index}]"
        raw_id, game_id, is_random, ranks = _decode_raw_charm(
            value=raw_charm,
            path=charm_path,
        )

        if raw_id in seen_raw_ids:
            _raise_normalization_error(
                path=f"{charm_path}.id",
                error=ValueError("id must not be duplicated"),
            )
        seen_raw_ids.add(raw_id)

        if game_id in seen_game_ids:
            _raise_normalization_error(
                path=f"{charm_path}.gameId",
                error=ValueError("gameId must not be duplicated"),
            )
        seen_game_ids.add(game_id)

        if is_random:
            continue

        fixed_ranks = _normalize_fixed_ranks(
            value=ranks,
            parent_game_id=game_id,
            skills_by_raw_id=skills_by_raw_id,
            path=f"{charm_path}.ranks",
        )
        for raw_index, normalized_charm in fixed_ranks:
            equipment_id = cast(str, normalized_charm["equipment_id"])
            if equipment_id in seen_equipment_ids:
                _raise_normalization_error(
                    path=f"{charm_path}.ranks[{raw_index}].level",
                    error=ValueError("generated equipment_id must not be duplicated"),
                )
            seen_equipment_ids.add(equipment_id)
            normalized_charms.append(normalized_charm)

    return normalized_charms


def _decode_raw_charm(
    *,
    value: object,
    path: str,
) -> tuple[int, int, bool, list[object]]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB charm must be object"),
        )

    for key in _RAW_CHARM_REQUIRED_KEYS:
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
    game_id = _decode_exact_int(
        value=value["gameId"],
        path=f"{path}.gameId",
        field_name="gameId",
    )
    is_random = _decode_random_flag(value=value, path=path)
    ranks = value["ranks"]
    if type(ranks) is not list:
        _raise_normalization_error(
            path=f"{path}.ranks",
            error=TypeError("ranks must be list"),
        )

    return raw_id, game_id, is_random, ranks


def _decode_random_flag(*, value: dict[object, object], path: str) -> bool:
    has_random = "random" in value
    has_randomized = "randomized" in value
    if not has_random and not has_randomized:
        _raise_normalization_error(
            path=f"{path}.random",
            error=ValueError(
                "missing required key: random (legacy randomized is also accepted)"
            ),
        )
    if has_random and has_randomized:
        _raise_normalization_error(
            path=f"{path}.randomized",
            error=ValueError("random and randomized must not be specified together"),
        )

    key = "random" if has_random else "randomized"
    is_random = value[key]
    if type(is_random) is not bool:
        _raise_normalization_error(
            path=f"{path}.{key}",
            error=TypeError(f"{key} must be bool"),
        )
    return is_random


def _normalize_fixed_ranks(
    *,
    value: list[object],
    parent_game_id: int,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> list[tuple[int, dict[str, object]]]:
    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("ranks must not be empty for a fixed charm"),
        )

    decoded_ranks: list[tuple[int, int, int, str, list[dict[str, object]]]] = []
    seen_raw_ids: set[int] = set()
    seen_levels: set[int] = set()
    for raw_index, raw_rank in enumerate(value):
        rank_path = f"{path}[{raw_index}]"
        raw_id, level, name, skills = _normalize_fixed_rank(
            value=raw_rank,
            skills_by_raw_id=skills_by_raw_id,
            path=rank_path,
        )

        if raw_id in seen_raw_ids:
            _raise_normalization_error(
                path=f"{rank_path}.id",
                error=ValueError("id must not be duplicated within a charm"),
            )
        seen_raw_ids.add(raw_id)

        if level in seen_levels:
            _raise_normalization_error(
                path=f"{rank_path}.level",
                error=ValueError("level must not be duplicated within a charm"),
            )
        seen_levels.add(level)
        decoded_ranks.append((raw_index, raw_id, level, name, skills))

    sorted_ranks = sorted(decoded_ranks, key=lambda rank: rank[2])
    for expected_level, (raw_index, _, level, _, _) in enumerate(
        sorted_ranks,
        start=1,
    ):
        if level != expected_level:
            _raise_normalization_error(
                path=f"{path}[{raw_index}].level",
                error=ValueError("rank levels must be exactly 1, 2, ..., N"),
            )

    normalized_ranks: list[tuple[int, dict[str, object]]] = []
    for raw_index, _, level, name, skills in sorted_ranks:
        normalized_charm = {
            "equipment_id": f"mhdb:charm:{parent_game_id}:rank-{level}",
            "display_name": name,
            "part": "charm",
            "weapon_kind": None,
            "skills": skills,
            "slots": [],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        }
        decode_equipment_definition(
            value=normalized_charm,
            path=f"{path}[{raw_index}]",
        )
        normalized_ranks.append((raw_index, normalized_charm))

    return normalized_ranks


def _normalize_fixed_rank(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> tuple[int, int, str, list[dict[str, object]]]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB fixed charm rank must be object"),
        )

    for key in _RAW_RANK_REQUIRED_KEYS:
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
    level = _decode_positive_int(
        value=value["level"],
        path=f"{path}.level",
        field_name="level",
    )
    skills = _normalize_fixed_rank_skills(
        value=value["skills"],
        skills_by_raw_id=skills_by_raw_id,
        path=f"{path}.skills",
    )
    return raw_id, level, name, skills


def _normalize_fixed_rank_skills(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("skills must be list"),
        )
    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("skills must not be empty"),
        )

    return [
        _normalize_fixed_rank_skill(
            value=raw_skill_rank,
            skills_by_raw_id=skills_by_raw_id,
            path=f"{path}[{index}]",
        )
        for index, raw_skill_rank in enumerate(value)
    ]


def _normalize_fixed_rank_skill(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB charm skill rank must be object"),
        )
    for key in _RAW_SKILL_RANK_REQUIRED_KEYS:
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
    if "id" not in raw_skill:
        _raise_normalization_error(
            path=f"{path}.skill.id",
            error=ValueError("missing required key: id"),
        )

    raw_skill_id = _decode_positive_int(
        value=raw_skill["id"],
        path=f"{path}.skill.id",
        field_name="skill.id",
    )
    skill = skills_by_raw_id.get(raw_skill_id)
    if skill is None:
        _raise_normalization_error(
            path=f"{path}.skill.id",
            error=ValueError("skill.id must reference an existing raw skill id"),
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
    if skill.kind not in (SkillKind.ARMOR, SkillKind.WEAPON):
        _raise_normalization_error(
            path=path,
            error=ValueError("skills must reference only armor or weapon skills"),
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
