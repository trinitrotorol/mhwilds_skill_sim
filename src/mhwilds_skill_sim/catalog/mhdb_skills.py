"""Normalize offline MHDB skill snapshots."""

from __future__ import annotations

from typing import NoReturn

from mhwilds_skill_sim.catalog.decoder import decode_skill_definition
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError

_RAW_SKILL_REQUIRED_KEYS = ("gameId", "name", "kind", "ranks")
_SUPPORTED_KINDS = ("armor", "weapon", "set", "group")


def normalize_mhdb_skill_snapshot(
    *,
    value: object,
    path: str = "$",
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB skill snapshot must be list"),
        )

    normalized_skills: list[dict[str, object]] = []
    seen_game_ids: set[int] = set()
    for index, raw_skill in enumerate(value):
        skill_path = f"{path}[{index}]"
        normalized_skill, game_id = _normalize_raw_skill(
            value=raw_skill,
            path=skill_path,
        )

        if game_id in seen_game_ids:
            _raise_normalization_error(
                path=f"{skill_path}.gameId",
                error=ValueError("gameId must not be duplicated"),
            )
        seen_game_ids.add(game_id)

        decode_skill_definition(value=normalized_skill, path=skill_path)
        normalized_skills.append(normalized_skill)

    return normalized_skills


def build_skill_only_catalog_document(
    *,
    value: object,
    path: str = "$",
) -> dict[str, object]:
    normalized_skills = normalize_mhdb_skill_snapshot(value=value, path=path)
    return {
        "schema_version": 1,
        "skills": normalized_skills,
        "equipment": [],
        "decorations": [],
    }


def _normalize_raw_skill(
    *,
    value: object,
    path: str,
) -> tuple[dict[str, object], int]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB skill must be object"),
        )

    for key in _RAW_SKILL_REQUIRED_KEYS:
        if key not in value:
            _raise_normalization_error(
                path=f"{path}.{key}",
                error=ValueError(f"missing required key: {key}"),
            )

    game_id = _decode_game_id(value=value["gameId"], path=f"{path}.gameId")
    name = _decode_name(value=value["name"], path=f"{path}.name")
    kind = _decode_kind(value=value["kind"], path=f"{path}.kind")
    ranks = _normalize_ranks(
        value=value["ranks"],
        kind=kind,
        path=f"{path}.ranks",
    )

    return (
        {
            "skill_id": f"mhdb:skill:{game_id}",
            "display_name": name,
            "kind": kind,
            "ranks": ranks,
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

    if value not in _SUPPORTED_KINDS:
        _raise_normalization_error(
            path=path,
            error=ValueError("kind must be one of: armor, weapon, set, group"),
        )

    return value


def _normalize_ranks(
    *,
    value: object,
    kind: str,
    path: str,
) -> list[dict[str, object]]:
    if type(value) is not list:
        _raise_normalization_error(
            path=path,
            error=TypeError("ranks must be list"),
        )

    if not value:
        _raise_normalization_error(
            path=path,
            error=ValueError("ranks must not be empty"),
        )

    decoded_ranks = tuple(
        _normalize_raw_rank(
            value=raw_rank,
            kind=kind,
            path=f"{path}[{raw_index}]",
            raw_index=raw_index,
        )
        for raw_index, raw_rank in enumerate(value)
    )
    sorted_ranks = tuple(sorted(decoded_ranks, key=lambda rank: rank[1]))

    for expected_level, (raw_index, level, _) in enumerate(sorted_ranks, start=1):
        if level != expected_level:
            _raise_normalization_error(
                path=f"{path}[{raw_index}].level",
                error=ValueError("rank levels must be exactly 1, 2, ..., N"),
            )

    if kind in ("set", "group"):
        previous_required_pieces: int | None = None
        for raw_index, _, required_pieces in sorted_ranks:
            if (
                previous_required_pieces is not None
                and required_pieces <= previous_required_pieces
            ):
                _raise_normalization_error(
                    path=f"{path}[{raw_index}].setPiecesRequired",
                    error=ValueError(
                        "setPiecesRequired must strictly increase by rank level"
                    ),
                )
            previous_required_pieces = required_pieces

    return [
        {
            "level": level,
            "required_pieces": required_pieces,
        }
        for _, level, required_pieces in sorted_ranks
    ]


def _normalize_raw_rank(
    *,
    value: object,
    kind: str,
    path: str,
    raw_index: int,
) -> tuple[int, int, int | None]:
    if type(value) is not dict:
        _raise_normalization_error(
            path=path,
            error=TypeError("MHDB skill rank must be object"),
        )

    if "level" not in value:
        _raise_normalization_error(
            path=f"{path}.level",
            error=ValueError("missing required key: level"),
        )

    level = value["level"]
    if type(level) is not int:
        _raise_normalization_error(
            path=f"{path}.level",
            error=TypeError("level must be int"),
        )
    if level < 1:
        _raise_normalization_error(
            path=f"{path}.level",
            error=ValueError("level must be at least 1"),
        )

    if kind in ("armor", "weapon"):
        required_pieces = value.get("setPiecesRequired")
        if required_pieces is not None:
            _raise_normalization_error(
                path=f"{path}.setPiecesRequired",
                error=ValueError(
                    "setPiecesRequired must be null for armor and weapon skills"
                ),
            )
        return (raw_index, level, None)

    if "setPiecesRequired" not in value:
        _raise_normalization_error(
            path=f"{path}.setPiecesRequired",
            error=ValueError("missing required key: setPiecesRequired"),
        )

    required_pieces = value["setPiecesRequired"]
    if type(required_pieces) is not int:
        _raise_normalization_error(
            path=f"{path}.setPiecesRequired",
            error=TypeError("setPiecesRequired must be int"),
        )
    if required_pieces < 1:
        _raise_normalization_error(
            path=f"{path}.setPiecesRequired",
            error=ValueError("setPiecesRequired must be at least 1"),
        )

    return (raw_index, level, required_pieces)


def _raise_normalization_error(*, path: str, error: Exception) -> NoReturn:
    raise CatalogDecodeError(path=path, detail=str(error)) from error
