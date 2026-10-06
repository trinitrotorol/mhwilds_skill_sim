"""Validated search-only inventory snapshots; never persistent player profiles."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution, SkillKind
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.build import BuildCandidate


class InventoryCatalogMismatchError(ValueError):
    """The immutable search catalog does not match the saved snapshot."""


@dataclass(frozen=True, slots=True)
class OwnedAppraisalCharm:
    instance_id: str
    rarity: int
    skills: tuple[SkillContribution, ...]
    slots: tuple[DecorationSlot, ...]
    quantity: int

    def __post_init__(self) -> None:
        if re.fullmatch(r"owned:\d+", _id(self.instance_id), flags=re.ASCII) is None:
            raise ValueError("appraisal ID must be anonymous owned:index")
        _integer(self.rarity, 1)
        _integer(self.quantity)
        if (
            type(self.skills) is not tuple
            or not 1 <= len(self.skills) <= 3
            or any(not isinstance(item, SkillContribution) for item in self.skills)
            or len({item.skill_id for item in self.skills}) != len(self.skills)
        ):
            raise ValueError("invalid appraisal skills")
        if (
            type(self.slots) is not tuple
            or len(self.slots) > 4
            or any(not isinstance(item, DecorationSlot) for item in self.slots)
        ):
            raise ValueError("invalid appraisal slots")


@dataclass(frozen=True, slots=True)
class InventorySearchSnapshot:
    catalog_revision: str
    decorations: tuple[tuple[str, int], ...]
    fixed_charms: tuple[tuple[str, int], ...]
    appraisal_charms: tuple[OwnedAppraisalCharm, ...]

    def __post_init__(self) -> None:
        if re.fullmatch("[a-f0-9]{64}", _id(self.catalog_revision)) is None:
            raise ValueError("catalog revision must be SHA256")
        for entries in (self.decorations, self.fixed_charms):
            if type(entries) is not tuple or len(entries) > 10000:
                raise ValueError("invalid inventory quantity entries")
            seen: set[str] = set()
            for item in entries:
                if type(item) is not tuple or len(item) != 2:
                    raise ValueError("invalid inventory quantity entry")
                item_id = _id(item[0])
                _integer(item[1])
                if item_id in seen:
                    raise ValueError("duplicate inventory identifier")
                seen.add(item_id)
        if (
            type(self.appraisal_charms) is not tuple
            or len(self.appraisal_charms) > 1000
            or any(
                not isinstance(item, OwnedAppraisalCharm)
                for item in self.appraisal_charms
            )
            or len({item.instance_id for item in self.appraisal_charms})
            != len(self.appraisal_charms)
        ):
            raise ValueError("invalid owned appraisal entries")


def _object(value: object, keys: tuple[str, ...]) -> dict:
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError("inventory fields do not match version 1 contract")
    return value


def _list(value: object, maximum: int = 10000) -> list:
    if type(value) is not list or len(value) > maximum:
        raise ValueError("inventory list exceeds size limit")
    return value


def _id(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 512 or value.strip() != value:
        raise ValueError("invalid inventory identifier")
    return value


def _integer(value: object, minimum: int = 0, maximum: int = 2**53 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("inventory number must be a safe integer in range")
    return value


def _quantities(value: object, key: str) -> tuple[tuple[str, int], ...]:
    result: list[tuple[str, int]] = []
    for entry in _list(value):
        item = _object(entry, (key, "quantity"))
        result.append((_id(item[key]), _integer(item["quantity"])))
    if len(dict(result)) != len(result):
        raise ValueError("duplicate inventory identifier")
    return tuple(result)


def decode_inventory_search_snapshot(value: object) -> InventorySearchSnapshot:
    """Structural validation without assuming any catalog references are valid."""
    record = _object(
        value,
        (
            "schema_version",
            "catalog_revision",
            "decorations",
            "fixed_charms",
            "appraisal_charms",
        ),
    )
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise ValueError("unsupported inventory snapshot version")
    revision = _id(record["catalog_revision"])
    if re.fullmatch("[a-f0-9]{64}", revision) is None:
        raise ValueError("catalog revision must be SHA256")
    charms: list[OwnedAppraisalCharm] = []
    for raw in _list(record["appraisal_charms"], 1000):
        item = _object(raw, ("instance_id", "rarity", "skills", "slots", "quantity"))
        instance_id = _id(item["instance_id"])
        if re.fullmatch(r"owned:\d+", instance_id, flags=re.ASCII) is None:
            raise ValueError("appraisal ID must be anonymous owned:index")
        skills: list[SkillContribution] = []
        for raw_skill in _list(item["skills"], 3):
            skill = _object(raw_skill, ("skill_id", "level"))
            skills.append(
                SkillContribution(
                    skill_id=_id(skill["skill_id"]),
                    level=_integer(skill["level"], 1),
                )
            )
        if not skills or len({skill.skill_id for skill in skills}) != len(skills):
            raise ValueError("duplicate appraisal skill")
        slots: list[DecorationSlot] = []
        for raw_slot in _list(item["slots"], 4):
            slot = _object(raw_slot, ("kind", "level"))
            slots.append(
                DecorationSlot(
                    kind=DecorationKind(slot["kind"]),
                    level=_integer(slot["level"], 1),
                )
            )
        charms.append(
            OwnedAppraisalCharm(
                instance_id=instance_id,
                rarity=_integer(item["rarity"], 1),
                skills=tuple(skills),
                slots=tuple(slots),
                quantity=_integer(item["quantity"]),
            )
        )
    if len({charm.instance_id for charm in charms}) != len(charms):
        raise ValueError("duplicate appraisal instance ID")
    return InventorySearchSnapshot(
        catalog_revision=revision,
        decorations=_quantities(record["decorations"], "decoration_id"),
        fixed_charms=_quantities(record["fixed_charms"], "equipment_id"),
        appraisal_charms=tuple(charms),
    )


def validate_snapshot_contract(value: object) -> None:
    """Validate against the pinned checker contract, failing closed if absent."""
    from jsonschema import Draft202012Validator

    configured_path = os.environ.get("MHWILDS_INVENTORY_CONTRACT_PATH")
    path = (
        Path(configured_path)
        if configured_path
        else Path(__file__).resolve().parents[3]
        / "subprojects"
        / "inventory-checker"
        / "contracts"
        / "search-inventory.v1.schema.json"
    )
    if not path.is_file():
        raise ValueError("pinned checker search inventory contract is unavailable")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ValueError("inventory does not match pinned checker schema")


def _matches_rules(charm: OwnedAppraisalCharm, catalog: Catalog) -> bool:
    definitions = {skill.skill_id: skill for skill in catalog.skills}
    if not charm.skills:
        return False
    for skill in charm.skills:
        definition = definitions.get(skill.skill_id)
        if (
            definition is None
            or definition.kind not in (SkillKind.WEAPON, SkillKind.ARMOR)
            or skill.level > definition.ranks[-1].level
        ):
            return False
    groups = {group.group_id: group for group in catalog.appraisal_charm_skill_groups}
    for pattern in catalog.appraisal_charm_patterns:
        if pattern.rarity != charm.rarity or pattern.slots != charm.slots:
            continue
        remaining = {skill.skill_id: skill.level for skill in charm.skills}
        selected_skill_ids: set[str] = set()

        def visit(depth: int) -> bool:
            if depth == len(pattern.skill_group_ids):
                return all(level == 0 for level in remaining.values())
            for skill in groups[pattern.skill_group_ids[depth]].skills:
                available = remaining.get(skill.skill_id, 0)
                if available < skill.level or skill.skill_id in selected_skill_ids:
                    continue
                remaining[skill.skill_id] = available - skill.level
                selected_skill_ids.add(skill.skill_id)
                matched = visit(depth + 1)
                selected_skill_ids.remove(skill.skill_id)
                remaining[skill.skill_id] = available
                if matched:
                    return True
            return False

        if visit(0):
            return True
    return False


def apply_inventory_to_catalog(
    *,
    catalog: Catalog,
    snapshot: InventorySearchSnapshot,
    catalog_revision: str,
) -> Catalog:
    if not isinstance(snapshot, InventorySearchSnapshot):
        raise TypeError("snapshot must be InventorySearchSnapshot")
    if snapshot.catalog_revision != catalog_revision:
        raise InventoryCatalogMismatchError("inventory catalog revision mismatch")
    known_decorations = {item.decoration_id for item in catalog.decorations}
    if any(item_id not in known_decorations for item_id, _ in snapshot.decorations):
        raise ValueError("inventory references unknown decoration")
    known_charms = {
        item.equipment_id
        for item in catalog.equipment
        if item.part is EquipmentPart.CHARM
        and not item.equipment_id.startswith("generated:")
    }
    if any(item_id not in known_charms for item_id, _ in snapshot.fixed_charms):
        raise ValueError("inventory references unknown fixed charm")
    quantities = dict(snapshot.fixed_charms)
    equipment = [
        item
        for item in catalog.equipment
        if item.part is not EquipmentPart.CHARM
        or quantities.get(item.equipment_id, 0) > 0
    ]
    for charm in snapshot.appraisal_charms:
        if not _matches_rules(charm, catalog):
            raise ValueError("owned appraisal charm does not match catalog rules")
        if charm.quantity > 0:
            equipment.append(
                EquipmentDefinition(
                    equipment_id=charm.instance_id,
                    part=EquipmentPart.CHARM,
                    skills=charm.skills,
                    slots=charm.slots,
                )
            )
    # Empty rules prohibit the ordinary solver from creating theoretical charms.
    return replace(
        catalog,
        equipment=tuple(equipment),
        appraisal_charm_skill_groups=(),
        appraisal_charm_patterns=(),
    )


def validate_candidate_inventory(
    *,
    candidate: BuildCandidate,
    snapshot: InventorySearchSnapshot,
) -> None:
    quantities = dict(snapshot.decorations)
    used = Counter(placement.decoration_id for placement in candidate.placements)
    if any(count > quantities.get(item_id, 0) for item_id, count in used.items()):
        raise ValueError("candidate exceeds owned decoration quantity")
    owned_charms = {
        item_id for item_id, quantity in snapshot.fixed_charms if quantity > 0
    } | {charm.instance_id for charm in snapshot.appraisal_charms if charm.quantity > 0}
    charm = next(
        item for item in candidate.equipment if item.part is EquipmentPart.CHARM
    )
    if charm.equipment_id not in owned_charms:
        raise ValueError("candidate uses unowned charm")
