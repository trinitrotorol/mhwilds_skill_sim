"""Catalog model containers."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.skill import SkillDefinition


@dataclass(frozen=True, slots=True)
class Catalog:
    schema_version: int
    equipment: tuple[EquipmentDefinition, ...]
    decorations: tuple[DecorationDefinition, ...]
    skills: tuple[SkillDefinition, ...] = ()

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int:
            raise TypeError("schema_version must be int")

        if self.schema_version < 1:
            raise ValueError("schema_version must be at least 1")

        if type(self.equipment) is not tuple:
            raise TypeError("equipment must be tuple")

        seen_equipment_ids: set[str] = set()
        for equipment in self.equipment:
            if not isinstance(equipment, EquipmentDefinition):
                raise TypeError("equipment must contain only EquipmentDefinition")

            if equipment.equipment_id in seen_equipment_ids:
                raise ValueError("equipment must not contain duplicate equipment_id")

            seen_equipment_ids.add(equipment.equipment_id)

        if type(self.decorations) is not tuple:
            raise TypeError("decorations must be tuple")

        seen_decoration_ids: set[str] = set()
        for decoration in self.decorations:
            if not isinstance(decoration, DecorationDefinition):
                raise TypeError("decorations must contain only DecorationDefinition")

            if decoration.decoration_id in seen_decoration_ids:
                raise ValueError("decorations must not contain duplicate decoration_id")

            seen_decoration_ids.add(decoration.decoration_id)

        if type(self.skills) is not tuple:
            raise TypeError("skills must be tuple")

        seen_skill_ids: set[str] = set()
        for skill in self.skills:
            if not isinstance(skill, SkillDefinition):
                raise TypeError("skills must contain only SkillDefinition")

            if skill.skill_id in seen_skill_ids:
                raise ValueError("skills must not contain duplicate skill_id")

            seen_skill_ids.add(skill.skill_id)
