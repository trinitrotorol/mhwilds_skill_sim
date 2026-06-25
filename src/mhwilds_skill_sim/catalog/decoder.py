"""Catalog value decoders."""

from __future__ import annotations

from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot

_SKILL_CONTRIBUTION_KEYS = frozenset(("skill_id", "level"))
_SKILL_CONTRIBUTION_KEY_ORDER = ("skill_id", "level")
_DECORATION_SLOT_KEYS = frozenset(("kind", "level"))
_DECORATION_SLOT_KEY_ORDER = ("kind", "level")


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


def _decode_decoration_kind(value: object) -> DecorationKind:
    if type(value) is not str:
        raise TypeError("kind must be str")

    if value == DecorationKind.WEAPON.value:
        return DecorationKind.WEAPON

    if value == DecorationKind.ARMOR.value:
        return DecorationKind.ARMOR

    raise ValueError("kind must be one of: weapon, armor")


def _sort_keys(keys: list[object]) -> list[object]:
    return sorted(keys, key=lambda key: (_format_key(key), type(key).__module__))


def _format_key(key: object) -> str:
    if type(key) is str:
        return key

    if type(key) in (int, float, bool, bytes, tuple, frozenset, type(None)):
        return repr(key)

    return f"<{type(key).__module__}.{type(key).__qualname__}>"
