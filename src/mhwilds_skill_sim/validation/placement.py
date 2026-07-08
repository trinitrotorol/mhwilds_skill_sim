"""Decoration placement value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecorationPlacement:
    equipment_id: str
    slot_index: int
    decoration_id: str

    def __post_init__(self) -> None:
        if type(self.equipment_id) is not str:
            raise TypeError("equipment_id must be str")

        if self.equipment_id == "":
            raise ValueError("equipment_id must not be empty")

        if self.equipment_id.strip() == "":
            raise ValueError("equipment_id must not be blank")

        if self.equipment_id != self.equipment_id.strip():
            raise ValueError(
                "equipment_id must not have leading or trailing whitespace",
            )

        if type(self.slot_index) is not int:
            raise TypeError("slot_index must be int")

        if self.slot_index < 0:
            raise ValueError("slot_index must be at least 0")

        if type(self.decoration_id) is not str:
            raise TypeError("decoration_id must be str")

        if self.decoration_id == "":
            raise ValueError("decoration_id must not be empty")

        if self.decoration_id.strip() == "":
            raise ValueError("decoration_id must not be blank")

        if self.decoration_id != self.decoration_id.strip():
            raise ValueError(
                "decoration_id must not have leading or trailing whitespace",
            )
