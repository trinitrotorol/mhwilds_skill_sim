"""Normalize offline MHDB weapon snapshots."""

from __future__ import annotations

from typing import NoReturn

from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_equipment_definition,
    decode_skill_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.mhdb_armor import normalize_mhdb_armor_snapshot
from mhwilds_skill_sim.catalog.mhdb_decorations import (
    normalize_mhdb_decoration_snapshot,
)
from mhwilds_skill_sim.catalog.mhdb_skills import normalize_mhdb_skill_snapshot
from mhwilds_skill_sim.domain.equipment import WeaponKind
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind

_RAW_WEAPON_REQUIRED_KEYS = (
    "id",
    "gameId",
    "kind",
    "name",
    "slots",
    "skills",
    "series",
)
_SUPPORTED_WEAPON_KINDS = tuple(kind.value for kind in WeaponKind)


def normalize_mhdb_weapon_snapshot(
    *,
    value: object,
    skill_snapshot: object,
    path: str = "$.weapons",
    skill_path: str = "$.skills",
) -> list[dict[str, object]]:
    _, skills_by_raw_id = _normalize_and_index_skills(
        skill_snapshot=skill_snapshot,
        skill_path=skill_path,
    )
    return _normalize_weapons(
        value=value,
        skills_by_raw_id=skills_by_raw_id,
        path=path,
    )


def build_skill_weapon_armor_and_decoration_catalog_document(
    *,
    skill_value: object,
    weapon_value: object,
    armor_set_value: object,
    armor_value: object,
    decoration_value: object,
    skill_path: str = "$.skills",
    weapon_path: str = "$.weapons",
    armor_set_path: str = "$.armor_sets",
    armor_path: str = "$.armor",
    decoration_path: str = "$.decorations",
) -> dict[str, object]:
    normalized_skills, skills_by_raw_id = _normalize_and_index_skills(
        skill_snapshot=skill_value,
        skill_path=skill_path,
    )
    normalized_weapons = _normalize_weapons(
        value=weapon_value,
        skills_by_raw_id=skills_by_raw_id,
        path=weapon_path,
    )
    normalized_armor = normalize_mhdb_armor_snapshot(
        value=armor_value,
        armor_set_snapshot=armor_set_value,
        skill_snapshot=skill_value,
        path=armor_path,
        armor_set_path=armor_set_path,
        skill_path=skill_path,
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
        "equipment": normalized_weapons + normalized_armor,
        "decorations": normalized_decorations,
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

    skills_by_raw_id: dict[int, SkillDefinition] = {}
    for index, (raw_skill, normalized_skill) in enumerate(
        zip(skill_snapshot, normalized_skills)
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


def _normalize_weapons(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB weapon snapshot must be list"),
        )

    normalized_weapons: list[dict[str, object]] = []
    seen_raw_ids: set[int] = set()
    seen_identities: set[tuple[WeaponKind, int]] = set()
    for index, raw_weapon in enumerate(value):
        weapon_path = f"{path}[{index}]"
        normalized_weapon, raw_id, identity = _normalize_raw_weapon(
            value=raw_weapon,
            skills_by_raw_id=skills_by_raw_id,
            path=weapon_path,
        )

        if raw_id in seen_raw_ids:
            _raise_normalization_error(
                path=f"{weapon_path}.id",
                error=ValueError("id must not be duplicated"),
            )
        seen_raw_ids.add(raw_id)

        if identity in seen_identities:
            _raise_normalization_error(
                path=f"{weapon_path}.gameId",
                error=ValueError("kind and gameId pair must not be duplicated"),
            )
        seen_identities.add(identity)

        decode_equipment_definition(
            value=normalized_weapon,
            path=weapon_path,
        )
        normalized_weapons.append(normalized_weapon)

    return normalized_weapons


def _normalize_raw_weapon(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> tuple[dict[str, object], int, tuple[WeaponKind, int]]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB weapon must be object"),
        )

    for key in _RAW_WEAPON_REQUIRED_KEYS:
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
    kind = _decode_weapon_kind(value=value["kind"], path=f"{path}.kind")
    name = _decode_name(value=value["name"], path=f"{path}.name")
    slots = _normalize_slots(value=value["slots"], path=f"{path}.slots")
    skills = _normalize_weapon_skills(
        value=value["skills"],
        skills_by_raw_id=skills_by_raw_id,
        path=f"{path}.skills",
    )
    allows_assignment = _decode_series(
        value=value["series"],
        path=f"{path}.series",
    )
    equipment_id = f"mhdb:weapon:{kind.value}:{game_id}"

    return (
        {
            "equipment_id": equipment_id,
            "display_name": name,
            "part": "weapon",
            "weapon_kind": kind.value,
            "skills": skills,
            "slots": slots,
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": allows_assignment,
            "allows_group_skill_assignment": allows_assignment,
        },
        raw_id,
        (kind, game_id),
    )


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
            "kind": "weapon",
            "level": _decode_positive_int(
                value=raw_level,
                path=f"{path}[{index}]",
                field_name="slot level",
            ),
        }
        for index, raw_level in enumerate(value)
    ]


def _normalize_weapon_skills(
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

    return [
        _normalize_weapon_skill(
            value=raw_skill_rank,
            skills_by_raw_id=skills_by_raw_id,
            path=f"{path}[{index}]",
        )
        for index, raw_skill_rank in enumerate(value)
    ]


def _normalize_weapon_skill(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB weapon skill rank must be object"),
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
    if skill.kind is not SkillKind.WEAPON:
        _raise_normalization_error(
            path=path,
            error=ValueError("skills must reference only weapon skills"),
        )

    return {
        "skill_id": skill.skill_id,
        "level": level,
    }


def _decode_series(*, value: object, path: str) -> bool:
    if value is None:
        return True
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("series must be object or None"),
        )

    for key in ("id", "gameId"):
        if key not in value:
            _raise_normalization_error(
                path=f"{path}.{key}",
                error=ValueError(f"missing required key: {key}"),
            )

    _decode_positive_int(
        value=value["id"],
        path=f"{path}.id",
        field_name="series.id",
    )
    _decode_exact_int(
        value=value["gameId"],
        path=f"{path}.gameId",
        field_name="series.gameId",
    )
    return False


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


def _decode_weapon_kind(*, value: object, path: str) -> WeaponKind:
    if type(value) is not str:
        _raise_normalization_error(
            path=path,
            error=TypeError("kind must be str"),
        )
    if value not in _SUPPORTED_WEAPON_KINDS:
        _raise_normalization_error(
            path=path,
            error=ValueError(
                "kind must be one of: " + ", ".join(_SUPPORTED_WEAPON_KINDS)
            ),
        )
    return WeaponKind(value)


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
