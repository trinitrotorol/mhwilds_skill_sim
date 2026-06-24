"""Decoration slot domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecorationKind(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"


@dataclass(frozen=True, slots=True)
class DecorationSlot:
    kind: DecorationKind
    level: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DecorationKind):
            raise TypeError("kind must be DecorationKind")

        if type(self.level) is not int:
            raise TypeError("level must be int")

        if self.level < 1:
            raise ValueError("level must be at least 1")


def can_place_decoration(
    *,
    required_slot: DecorationSlot,
    available_slot: DecorationSlot,
) -> bool:
    if not isinstance(required_slot, DecorationSlot):
        raise TypeError("required_slot must be DecorationSlot")

    if not isinstance(available_slot, DecorationSlot):
        raise TypeError("available_slot must be DecorationSlot")

    return (
        required_slot.kind == available_slot.kind
        and required_slot.level <= available_slot.level
    )
