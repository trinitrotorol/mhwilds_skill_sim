"""Domain value objects and rules."""

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
    aggregate_skill_levels,
)
from mhwilds_skill_sim.domain.slot import (
    DecorationKind,
    DecorationSlot,
    can_place_decoration,
)

__all__ = [
    "DecorationDefinition",
    "DecorationKind",
    "DecorationSlot",
    "EquipmentDefinition",
    "EquipmentPart",
    "SkillContribution",
    "SkillDefinition",
    "SkillKind",
    "SkillRankDefinition",
    "aggregate_skill_levels",
    "can_place_decoration",
]
