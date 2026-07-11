"""Normalize offline MHDB decoration snapshots."""

from __future__ import annotations

from typing import NoReturn

from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_decoration_definition,
    decode_skill_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.mhdb_skills import normalize_mhdb_skill_snapshot
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind

_RAW_DECORATION_REQUIRED_KEYS = ("gameId", "name", "slot", "kind", "skills")
_SUPPORTED_DECORATION_KINDS = ("weapon", "armor")


def normalize_mhdb_decoration_snapshot(
    *,
    value: object,
    skill_snapshot: object,
    path: str = "$",
    skill_path: str = "$.skills",
) -> list[dict[str, object]]:
    _, skills_by_raw_id = _normalize_and_index_skills(
        skill_snapshot=skill_snapshot,
        skill_path=skill_path,
    )
    return _normalize_decorations(
        value=value,
        skills_by_raw_id=skills_by_raw_id,
        path=path,
    )


def build_skill_and_decoration_catalog_document(
    *,
    skill_value: object,
    decoration_value: object,
    skill_path: str = "$.skills",
    decoration_path: str = "$.decorations",
) -> dict[str, object]:
    normalized_skills, skills_by_raw_id = _normalize_and_index_skills(
        skill_snapshot=skill_value,
        skill_path=skill_path,
    )
    normalized_decorations = _normalize_decorations(
        value=decoration_value,
        skills_by_raw_id=skills_by_raw_id,
        path=decoration_path,
    )
    document = {
        "schema_version": 1,
        "skills": normalized_skills,
        "equipment": [],
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

        raw_id = raw_skill["id"]
        if type(raw_id) is not int:
            _raise_normalization_error(
                path=raw_id_path,
                error=TypeError("id must be int"),
            )
        if raw_id < 1:
            _raise_normalization_error(
                path=raw_id_path,
                error=ValueError("id must be at least 1"),
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


def _normalize_decorations(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB decoration snapshot must be list"),
        )

    normalized_decorations: list[dict[str, object]] = []
    seen_game_ids: set[int] = set()
    for index, raw_decoration in enumerate(value):
        decoration_path = f"{path}[{index}]"
        normalized_decoration, game_id = _normalize_raw_decoration(
            value=raw_decoration,
            skills_by_raw_id=skills_by_raw_id,
            path=decoration_path,
        )

        if game_id in seen_game_ids:
            _raise_normalization_error(
                path=f"{decoration_path}.gameId",
                error=ValueError("gameId must not be duplicated"),
            )
        seen_game_ids.add(game_id)

        decode_decoration_definition(
            value=normalized_decoration,
            path=decoration_path,
        )
        normalized_decorations.append(normalized_decoration)

    return normalized_decorations


def _normalize_raw_decoration(
    *,
    value: object,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> tuple[dict[str, object], int]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB decoration must be object"),
        )

    for key in _RAW_DECORATION_REQUIRED_KEYS:
        if key not in value:
            _raise_normalization_error(
                path=f"{path}.{key}",
                error=ValueError(f"missing required key: {key}"),
            )

    game_id = _decode_game_id(value=value["gameId"], path=f"{path}.gameId")
    name = _decode_name(value=value["name"], path=f"{path}.name")
    slot = _decode_positive_int(
        value=value["slot"],
        path=f"{path}.slot",
        field_name="slot",
    )
    kind = _decode_kind(value=value["kind"], path=f"{path}.kind")
    skills = _normalize_decoration_skills(
        value=value["skills"],
        decoration_kind=kind,
        skills_by_raw_id=skills_by_raw_id,
        path=f"{path}.skills",
    )

    return (
        {
            "decoration_id": f"mhdb:decoration:{game_id}",
            "display_name": name,
            "required_slot": {
                "kind": kind,
                "level": slot,
            },
            "skills": skills,
        },
        game_id,
    )


def _decode_game_id(*, value: object, path: str) -> int:
    if type(value) is not int:
        _raise_normalization_error(
            path=path,
            error=TypeError("gameId must be int"),
        )
    return value


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


def _decode_kind(*, value: object, path: str) -> str:
    if type(value) is not str:
        _raise_normalization_error(
            path=path,
            error=TypeError("kind must be str"),
        )
    if value not in _SUPPORTED_DECORATION_KINDS:
        _raise_normalization_error(
            path=path,
            error=ValueError("kind must be one of: weapon, armor"),
        )
    return value


def _normalize_decoration_skills(
    *,
    value: object,
    decoration_kind: str,
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
        _normalize_decoration_skill(
            value=raw_skill_rank,
            decoration_kind=decoration_kind,
            skills_by_raw_id=skills_by_raw_id,
            path=f"{path}[{index}]",
        )
        for index, raw_skill_rank in enumerate(value)
    ]


def _normalize_decoration_skill(
    *,
    value: object,
    decoration_kind: str,
    skills_by_raw_id: dict[int, SkillDefinition],
    path: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB decoration skill rank must be object"),
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
    referenced_skill = skills_by_raw_id.get(raw_skill_id)
    if referenced_skill is None:
        _raise_normalization_error(
            path=f"{path}.skill.id",
            error=ValueError("skill.id must reference an existing raw skill id"),
        )

    level = _decode_positive_int(
        value=value["level"],
        path=f"{path}.level",
        field_name="level",
    )
    if level > referenced_skill.ranks[-1].level:
        _raise_normalization_error(
            path=f"{path}.level",
            error=ValueError("level must not exceed the referenced skill maximum rank"),
        )

    expected_skill_kind = (
        SkillKind.WEAPON if decoration_kind == "weapon" else SkillKind.ARMOR
    )
    if referenced_skill.kind is not expected_skill_kind:
        _raise_normalization_error(
            path=path,
            error=ValueError(
                "skills kind must match decoration kind and be armor or weapon"
            ),
        )

    return {
        "skill_id": referenced_skill.skill_id,
        "level": level,
    }


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


def _raise_normalization_error(*, path: str, error: Exception) -> NoReturn:
    raise CatalogDecodeError(path=path, detail=str(error)) from error
