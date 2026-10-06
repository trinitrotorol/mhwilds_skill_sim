from __future__ import annotations

from dataclasses import replace
from itertools import product

import pytest

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.inventory import (
    InventoryCatalogMismatchError,
    apply_inventory_to_catalog,
    decode_inventory_search_snapshot,
    validate_candidate_inventory,
)
from mhwilds_skill_sim.solver.inventory_search import search_inventory_ranked_builds
from mhwilds_skill_sim.solver.preferences import SkillPreference
from mhwilds_skill_sim.solver.requirements import SkillRequirement
from mhwilds_skill_sim.validation.build import validate_build

REVISION = "0" * 64
ARMOR_SLOT = DecorationSlot(kind=DecorationKind.ARMOR, level=1)


def catalog() -> Catalog:
    skill = SkillDefinition(
        skill_id="attack",
        kind=SkillKind.ARMOR,
        ranks=tuple(
            SkillRankDefinition(level=i, required_pieces=None) for i in range(1, 6)
        ),
    )
    equipment = tuple(
        EquipmentDefinition(
            equipment_id=f"equipment:{part.value}",
            part=part,
            skills=(),
            slots=(ARMOR_SLOT, ARMOR_SLOT) if part is EquipmentPart.HEAD else (),
        )
        for part in EquipmentPart
    )
    return Catalog(
        schema_version=1,
        skills=(skill,),
        equipment=equipment,
        decorations=(
            DecorationDefinition(
                decoration_id="jewel",
                required_slot=ARMOR_SLOT,
                skills=(SkillContribution(skill_id="attack", level=1),),
            ),
        ),
    )


def snapshot(**changes):
    payload = {
        "schema_version": 1,
        "catalog_revision": REVISION,
        "decorations": [],
        "fixed_charms": [{"equipment_id": "equipment:charm", "quantity": 1}],
        "appraisal_charms": [],
    }
    payload.update(changes)
    return decode_inventory_search_snapshot(payload)


def search(source, inventory, **changes):
    arguments = dict(
        catalog=source,
        catalog_revision=REVISION,
        snapshot=inventory,
        requirements=(),
        preferences=(),
        max_results=20,
    )
    arguments.update(changes)
    return search_inventory_ranked_builds(**arguments)


@pytest.mark.parametrize("quantity", [0, 1, 2])
def test_exact_owned_decoration_boundary(quantity):
    inventory = snapshot(decorations=[{"decoration_id": "jewel", "quantity": quantity}])
    source = catalog()
    result = search(source, inventory, requirements=(SkillRequirement("attack", 2),))
    assert len(result.candidates) == (1 if quantity == 2 else 0)
    assert result.exhausted
    for candidate in result.candidates:
        validate_candidate_inventory(candidate=candidate, snapshot=inventory)
        validation = validate_build(
            equipment=candidate.equipment,
            decorations=source.decorations,
            placements=candidate.placements,
        )
        assert not validation.equipment_selection_issues
        assert not validation.decoration_placement_issues


def test_unlisted_decorations_and_unowned_charms_are_never_injected():
    source = catalog()
    assert not search(
        source,
        snapshot(),
        requirements=(SkillRequirement("attack", 1),),
    ).candidates
    assert not search(source, snapshot(fixed_charms=[])).candidates


def test_top_k_matches_exhaustive_small_equipment_oracle_and_ties():
    source = catalog()
    variants = []
    for item in source.equipment:
        if item.part in (EquipmentPart.HEAD, EquipmentPart.CHEST, EquipmentPart.CHARM):
            variants.extend(
                replace(
                    item,
                    equipment_id=f"{item.equipment_id}:{level}",
                    slots=(),
                    skills=(SkillContribution("attack", level),) if level else (),
                )
                for level in range(2)
            )
        else:
            variants.append(item)
    source = replace(source, equipment=tuple(variants))
    inventory = snapshot(
        fixed_charms=[
            {"equipment_id": f"equipment:charm:{level}", "quantity": 1}
            for level in range(2)
        ]
    )
    expected = sorted(
        product(range(2), repeat=3), key=lambda row: (-min(sum(row), 2), row)
    )
    result = search(source, inventory, preferences=(SkillPreference("attack", 2),))
    actual = [
        tuple(
            int(item.equipment_id.rsplit(":", 1)[1])
            for item in build.equipment
            if item.part
            in (EquipmentPart.HEAD, EquipmentPart.CHEST, EquipmentPart.CHARM)
        )
        for build in result.candidates
    ]
    assert actual == expected
    assert result.exhausted and not result.timed_out
    assert (
        search(
            source,
            inventory,
            preferences=(SkillPreference("attack", 2),),
            max_results=3,
        ).candidates
        == result.candidates[:3]
    )


def test_owned_appraisal_rules_and_distinct_instances():
    source = replace(
        catalog(),
        appraisal_charm_skill_groups=(
            AppraisalCharmSkillGroupDefinition(
                group_id="group:a",
                skills=(SkillContribution("attack", 2),),
            ),
        ),
        appraisal_charm_patterns=(
            AppraisalCharmPatternDefinition(
                pattern_id="pattern:a",
                rarity=8,
                skill_group_ids=("group:a",),
                slots=(),
            ),
        ),
    )
    charm = dict(
        instance_id="owned:0",
        rarity=8,
        skills=[dict(skill_id="attack", level=2)],
        slots=[],
        quantity=1,
    )
    inventory = snapshot(
        fixed_charms=[],
        appraisal_charms=[
            charm,
            {**charm, "instance_id": "owned:1"},
        ],
    )
    result = search(source, inventory)
    assert [build.equipment[-1].equipment_id for build in result.candidates] == [
        "owned:0",
        "owned:1",
    ]
    assert not search(
        source,
        snapshot(),
        requirements=(SkillRequirement("attack", 2),),
    ).candidates  # no theoretical charm injected
    with pytest.raises(ValueError, match="rules"):
        search(source, snapshot(appraisal_charms=[{**charm, "rarity": 9}]))


def test_catalog_revision_unknown_ids_and_quantity_errors_fail_closed():
    source = catalog()
    with pytest.raises(InventoryCatalogMismatchError):
        apply_inventory_to_catalog(
            catalog=source,
            snapshot=snapshot(),
            catalog_revision="1" * 64,
        )
    with pytest.raises(ValueError, match="unknown decoration"):
        search(
            source, snapshot(decorations=[dict(decoration_id="unknown", quantity=1)])
        )
    for value in (-1, 0.5, True, 2**53):
        with pytest.raises(ValueError):
            snapshot(decorations=[dict(decoration_id="jewel", quantity=value)])


def test_zero_budget_reports_timeout_without_false_infeasibility():
    result = search(catalog(), snapshot(), timeout_seconds=1e-9)
    assert result.timed_out and not result.exhausted


def test_owned_charm_cannot_sum_duplicate_base_skills_from_two_groups():
    source = replace(
        catalog(),
        appraisal_charm_skill_groups=(
            AppraisalCharmSkillGroupDefinition(
                group_id="group:a",
                skills=(SkillContribution("attack", 1),),
            ),
        ),
        appraisal_charm_patterns=(
            AppraisalCharmPatternDefinition(
                pattern_id="pattern:a",
                rarity=8,
                skill_group_ids=("group:a", "group:a"),
                slots=(),
            ),
        ),
    )
    with pytest.raises(ValueError, match="rules"):
        search(
            source,
            snapshot(
                appraisal_charms=[
                    dict(
                        instance_id="owned:0",
                        rarity=8,
                        quantity=1,
                        slots=[],
                        skills=[dict(skill_id="attack", level=2)],
                    )
                ]
            ),
        )
