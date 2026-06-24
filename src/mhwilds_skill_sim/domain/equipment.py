"""Equipment domain value objects."""

from enum import StrEnum


class EquipmentPart(StrEnum):
    WEAPON = "weapon"
    HEAD = "head"
    CHEST = "chest"
    ARMS = "arms"
    WAIST = "waist"
    LEGS = "legs"
    CHARM = "charm"
