from __future__ import annotations

import ast
import inspect
import json
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path
from typing import cast

import pytest

import mhwilds_skill_sim.api.catalog_response as catalog_response_module
from mhwilds_skill_sim.api.catalog_response import build_catalog_metadata_response
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot


EXPECTED_WEAPON_KIND_VALUES = [
    "bow",
    "charge-blade",
    "dual-blades",
    "great-sword",
    "gunlance",
    "hammer",
    "heavy-bowgun",
    "hunting-horn",
    "insect-glaive",
    "lance",
    "light-bowgun",
    "long-sword",
    "switch-axe",
    "sword-shield",
]


def regular_skill(
    skill_id: str,
    *,
    kind: SkillKind = SkillKind.ARMOR,
    max_level: int = 1,
    display_name: str | None = None,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(level=level, required_pieces=None)
            for level in range(1, max_level + 1)
        ),
        display_name=display_name,
    )


def threshold_skill(
    skill_id: str,
    *,
    kind: SkillKind,
    required_pieces: tuple[int, ...],
    display_name: str | None = None,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(level=level, required_pieces=pieces)
            for level, pieces in enumerate(required_pieces, start=1)
        ),
        display_name=display_name,
    )


def equipment_definition(
    equipment_id: str,
    *,
    part: EquipmentPart = EquipmentPart.WEAPON,
    weapon_kind: WeaponKind | None = None,
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=(),
        slots=(),
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
        weapon_kind=weapon_kind,
    )


def decoration_definition(
    decoration_id: str,
    *,
    kind: DecorationKind,
    level: int,
    skills: tuple[SkillContribution, ...],
    display_name: str | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=DecorationSlot(kind=kind, level=level),
        skills=skills,
        display_name=display_name,
    )


def appraisal_group() -> AppraisalCharmSkillGroupDefinition:
    return AppraisalCharmSkillGroupDefinition(
        group_id="appraisal-group:A",
        skills=(
            SkillContribution("skill:critical-eye", 2),
            SkillContribution("skill:weapon-technique", 1),
        ),
    )


def appraisal_pattern() -> AppraisalCharmPatternDefinition:
    return AppraisalCharmPatternDefinition(
        pattern_id="appraisal-pattern:r8-a",
        rarity=8,
        skill_group_ids=("appraisal-group:A",),
        slots=(),
    )


def metadata_skills() -> tuple[SkillDefinition, ...]:
    return (
        regular_skill(
            "skill:critical-eye",
            max_level=2,
            display_name="Critical Eye",
        ),
        regular_skill(
            "skill:weapon-technique",
            kind=SkillKind.WEAPON,
            max_level=2,
        ),
        threshold_skill(
            "skill:rathalos-power",
            kind=SkillKind.SERIES,
            required_pieces=(2, 4),
            display_name="Rathalos Power",
        ),
        threshold_skill(
            "skill:scale-layering",
            kind=SkillKind.GROUP,
            required_pieces=(3, 5),
        ),
    )


def metadata_catalog() -> Catalog:
    return Catalog(
        schema_version=7,
        skills=metadata_skills(),
        equipment=(
            equipment_definition(
                "equipment:weapon:artian-great-sword",
                weapon_kind=WeaponKind.GREAT_SWORD,
                allows_series_skill_assignment=True,
                allows_group_skill_assignment=True,
            ),
            equipment_definition(
                "equipment:head:training",
                part=EquipmentPart.HEAD,
            ),
        ),
        decorations=(
            decoration_definition(
                "decoration:weapon-technique-3",
                kind=DecorationKind.WEAPON,
                level=3,
                skills=(SkillContribution("skill:weapon-technique", 1),),
                display_name="Technique Jewel III",
            ),
            decoration_definition(
                "decoration:critical-combination-2",
                kind=DecorationKind.ARMOR,
                level=2,
                skills=(
                    SkillContribution("skill:critical-eye", 2),
                    SkillContribution("skill:weapon-technique", 1),
                ),
            ),
        ),
        appraisal_charm_skill_groups=(appraisal_group(),),
        appraisal_charm_patterns=(appraisal_pattern(),),
    )


def response_contains_non_json_domain_value(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            response_contains_non_json_domain_value(key)
            or response_contains_non_json_domain_value(item)
            for key, item in value.items()
        )

    if isinstance(value, list):
        return any(response_contains_non_json_domain_value(item) for item in value)

    return isinstance(value, (tuple, Enum)) or is_dataclass(value)


def test_empty_catalog_response_has_exact_shape_and_key_order() -> None:
    response = build_catalog_metadata_response(
        catalog=Catalog(schema_version=1, equipment=(), decorations=()),
    )

    assert list(response) == [
        "schema_version",
        "skills",
        "weapon_kinds",
        "decorations",
        "features",
        "counts",
    ]
    assert response == {
        "schema_version": 1,
        "skills": [],
        "weapon_kinds": [],
        "decorations": [],
        "features": {
            "artian_series_skill_assignment": False,
            "artian_group_skill_assignment": False,
            "theoretical_appraisal_charms": False,
        },
        "counts": {
            "skills": 0,
            "equipment": 0,
            "decorations": 0,
            "appraisal_charm_skill_groups": 0,
            "appraisal_charm_patterns": 0,
        },
    }


def test_catalog_subclass_is_accepted() -> None:
    class CatalogSubclass(Catalog):
        pass

    catalog = CatalogSubclass(schema_version=3, equipment=(), decorations=())

    response = build_catalog_metadata_response(catalog=catalog)

    assert response["schema_version"] == 3


@pytest.mark.parametrize(
    "invalid_catalog",
    [None, object(), "catalog", {}, (), 1, True],
)
def test_invalid_catalog_values_are_rejected(invalid_catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        build_catalog_metadata_response(
            catalog=invalid_catalog,  # type: ignore[arg-type]
        )


def test_catalog_argument_is_keyword_only() -> None:
    signature = inspect.signature(build_catalog_metadata_response)

    assert list(signature.parameters) == ["catalog"]
    assert signature.parameters["catalog"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        build_catalog_metadata_response(metadata_catalog())  # type: ignore[call-arg]


def test_nested_metadata_uses_exact_key_order() -> None:
    response = build_catalog_metadata_response(catalog=metadata_catalog())
    skills = cast(list[dict[str, object]], response["skills"])
    ranks = cast(list[dict[str, object]], skills[0]["ranks"])
    decorations = cast(list[dict[str, object]], response["decorations"])
    required_slot = cast(dict[str, object], decorations[0]["required_slot"])
    decoration_skills = cast(
        list[dict[str, object]],
        decorations[0]["skills"],
    )
    features = cast(dict[str, object], response["features"])
    counts = cast(dict[str, object], response["counts"])

    assert list(skills[0]) == [
        "skill_id",
        "display_name",
        "kind",
        "max_level",
        "ranks",
    ]
    assert list(ranks[0]) == ["level", "required_pieces"]
    assert list(decorations[0]) == [
        "decoration_id",
        "display_name",
        "required_slot",
        "skills",
    ]
    assert list(required_slot) == ["kind", "level"]
    assert list(decoration_skills[0]) == ["skill_id", "level"]
    assert list(features) == [
        "artian_series_skill_assignment",
        "artian_group_skill_assignment",
        "theoretical_appraisal_charms",
    ]
    assert list(counts) == [
        "skills",
        "equipment",
        "decorations",
        "appraisal_charm_skill_groups",
        "appraisal_charm_patterns",
    ]


def test_all_skill_kinds_and_rank_metadata_preserve_input_order() -> None:
    response = build_catalog_metadata_response(catalog=metadata_catalog())

    assert response["skills"] == [
        {
            "skill_id": "skill:critical-eye",
            "display_name": "Critical Eye",
            "kind": "armor",
            "max_level": 2,
            "ranks": [
                {"level": 1, "required_pieces": None},
                {"level": 2, "required_pieces": None},
            ],
        },
        {
            "skill_id": "skill:weapon-technique",
            "display_name": None,
            "kind": "weapon",
            "max_level": 2,
            "ranks": [
                {"level": 1, "required_pieces": None},
                {"level": 2, "required_pieces": None},
            ],
        },
        {
            "skill_id": "skill:rathalos-power",
            "display_name": "Rathalos Power",
            "kind": "set",
            "max_level": 2,
            "ranks": [
                {"level": 1, "required_pieces": 2},
                {"level": 2, "required_pieces": 4},
            ],
        },
        {
            "skill_id": "skill:scale-layering",
            "display_name": None,
            "kind": "group",
            "max_level": 2,
            "ranks": [
                {"level": 1, "required_pieces": 3},
                {"level": 2, "required_pieces": 5},
            ],
        },
    ]


def test_all_fourteen_weapon_kinds_follow_declaration_order() -> None:
    input_kinds = tuple(reversed(tuple(WeaponKind)))
    catalog = Catalog(
        schema_version=1,
        equipment=tuple(
            equipment_definition(
                f"equipment:weapon:{index}:{kind.value}",
                weapon_kind=kind,
            )
            for index, kind in enumerate(input_kinds)
        ),
        decorations=(),
    )

    response = build_catalog_metadata_response(catalog=catalog)

    assert len(tuple(WeaponKind)) == 14
    assert [kind.value for kind in WeaponKind] == EXPECTED_WEAPON_KIND_VALUES
    assert response["weapon_kinds"] == EXPECTED_WEAPON_KIND_VALUES


def test_weapon_kinds_remove_duplicates_and_ignore_equipment_input_order() -> None:
    catalog = Catalog(
        schema_version=1,
        equipment=(
            equipment_definition(
                "equipment:weapon:long-sword:first",
                weapon_kind=WeaponKind.LONG_SWORD,
            ),
            equipment_definition(
                "equipment:weapon:bow",
                weapon_kind=WeaponKind.BOW,
            ),
            equipment_definition(
                "equipment:weapon:long-sword:second",
                weapon_kind=WeaponKind.LONG_SWORD,
            ),
        ),
        decorations=(),
    )

    response = build_catalog_metadata_response(catalog=catalog)

    assert response["weapon_kinds"] == ["bow", "long-sword"]


def test_weapon_kinds_ignore_non_weapons_and_legacy_weapons() -> None:
    catalog = Catalog(
        schema_version=1,
        equipment=(
            equipment_definition(
                "equipment:head:bow",
                part=EquipmentPart.HEAD,
            ),
            equipment_definition("equipment:weapon:legacy-great-sword"),
        ),
        decorations=(),
    )

    response = build_catalog_metadata_response(catalog=catalog)

    assert response["weapon_kinds"] == []


def test_decoration_metadata_preserves_definition_and_skill_order() -> None:
    response = build_catalog_metadata_response(catalog=metadata_catalog())

    assert response["decorations"] == [
        {
            "decoration_id": "decoration:weapon-technique-3",
            "display_name": "Technique Jewel III",
            "required_slot": {"kind": "weapon", "level": 3},
            "skills": [
                {"skill_id": "skill:weapon-technique", "level": 1},
            ],
        },
        {
            "decoration_id": "decoration:critical-combination-2",
            "display_name": None,
            "required_slot": {"kind": "armor", "level": 2},
            "skills": [
                {"skill_id": "skill:critical-eye", "level": 2},
                {"skill_id": "skill:weapon-technique", "level": 1},
            ],
        },
    ]


@pytest.mark.parametrize(
    ("series_assignment", "group_assignment"),
    [(True, False), (False, True), (True, True)],
)
def test_artian_assignment_features_are_computed_independently(
    series_assignment: bool,
    group_assignment: bool,
) -> None:
    skills: list[SkillDefinition] = []
    if series_assignment:
        skills.append(
            threshold_skill(
                "skill:series",
                kind=SkillKind.SERIES,
                required_pieces=(2,),
            )
        )
    if group_assignment:
        skills.append(
            threshold_skill(
                "skill:group",
                kind=SkillKind.GROUP,
                required_pieces=(3,),
            )
        )
    catalog = Catalog(
        schema_version=1,
        equipment=(
            equipment_definition(
                "equipment:weapon:artian",
                allows_series_skill_assignment=series_assignment,
                allows_group_skill_assignment=group_assignment,
            ),
        ),
        decorations=(),
        skills=tuple(skills),
    )

    response = build_catalog_metadata_response(catalog=catalog)

    assert response["features"] == {
        "artian_series_skill_assignment": series_assignment,
        "artian_group_skill_assignment": group_assignment,
        "theoretical_appraisal_charms": False,
    }


@pytest.mark.parametrize(
    ("include_group", "include_pattern", "expected"),
    [
        (False, False, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_theoretical_appraisal_charms_require_groups_and_patterns(
    include_group: bool,
    include_pattern: bool,
    expected: bool,
) -> None:
    # A pattern without its referenced group is not a valid Catalog state.
    catalog = Catalog(
        schema_version=1,
        equipment=(),
        decorations=(),
        skills=(
            regular_skill("skill:critical-eye", max_level=2),
            regular_skill(
                "skill:weapon-technique",
                kind=SkillKind.WEAPON,
            ),
        )
        if include_group
        else (),
        appraisal_charm_skill_groups=(appraisal_group(),) if include_group else (),
        appraisal_charm_patterns=(appraisal_pattern(),) if include_pattern else (),
    )

    response = build_catalog_metadata_response(catalog=catalog)
    features = cast(dict[str, object], response["features"])

    assert features["theoretical_appraisal_charms"] is expected


def test_counts_only_include_stored_catalog_definitions() -> None:
    catalog = metadata_catalog()

    response = build_catalog_metadata_response(catalog=catalog)

    assert response["counts"] == {
        "skills": 4,
        "equipment": 2,
        "decorations": 2,
        "appraisal_charm_skill_groups": 1,
        "appraisal_charm_patterns": 1,
    }
    assert response["features"] == {
        "artian_series_skill_assignment": True,
        "artian_group_skill_assignment": True,
        "theoretical_appraisal_charms": True,
    }


def test_response_is_json_serializable_without_domain_values() -> None:
    response = build_catalog_metadata_response(catalog=metadata_catalog())

    encoded = json.dumps(response)

    assert json.loads(encoded) == response
    assert not response_contains_non_json_domain_value(response)


def test_serializer_does_not_mutate_catalog() -> None:
    catalog = metadata_catalog()
    unchanged_catalog = metadata_catalog()

    build_catalog_metadata_response(catalog=catalog)

    assert catalog == unchanged_catalog


def test_repeated_calls_return_equal_independent_containers() -> None:
    catalog = metadata_catalog()
    first = build_catalog_metadata_response(catalog=catalog)
    second = build_catalog_metadata_response(catalog=catalog)

    first_skills = cast(list[dict[str, object]], first["skills"])
    second_skills = cast(list[dict[str, object]], second["skills"])
    first_ranks = cast(list[dict[str, object]], first_skills[0]["ranks"])
    second_ranks = cast(list[dict[str, object]], second_skills[0]["ranks"])
    first_decorations = cast(list[dict[str, object]], first["decorations"])
    second_decorations = cast(list[dict[str, object]], second["decorations"])
    first_required_slot = cast(
        dict[str, object],
        first_decorations[0]["required_slot"],
    )
    second_required_slot = cast(
        dict[str, object],
        second_decorations[0]["required_slot"],
    )
    first_decoration_skills = cast(
        list[dict[str, object]],
        first_decorations[0]["skills"],
    )
    second_decoration_skills = cast(
        list[dict[str, object]],
        second_decorations[0]["skills"],
    )
    first_weapon_kinds = cast(list[str], first["weapon_kinds"])
    first_features = cast(dict[str, object], first["features"])
    first_counts = cast(dict[str, object], first["counts"])

    assert first == second
    assert first is not second
    assert first_skills is not second_skills
    assert first_skills[0] is not second_skills[0]
    assert first_ranks is not second_ranks
    assert first_ranks[0] is not second_ranks[0]
    assert first["weapon_kinds"] is not second["weapon_kinds"]
    assert first_decorations is not second_decorations
    assert first_decorations[0] is not second_decorations[0]
    assert first_required_slot is not second_required_slot
    assert first_decoration_skills is not second_decoration_skills
    assert first_decoration_skills[0] is not second_decoration_skills[0]
    assert first["features"] is not second["features"]
    assert first["counts"] is not second["counts"]

    first["schema_version"] = 999
    first_ranks[0]["level"] = 999
    first_weapon_kinds.clear()
    first_required_slot["level"] = 999
    first_decoration_skills[0]["level"] = 999
    first_features["artian_series_skill_assignment"] = False
    first_counts["skills"] = 999

    assert second == build_catalog_metadata_response(catalog=catalog)
    assert catalog == metadata_catalog()


def test_nested_containers_within_one_response_are_independent() -> None:
    response = build_catalog_metadata_response(catalog=metadata_catalog())
    skills = cast(list[dict[str, object]], response["skills"])
    first_ranks = cast(list[dict[str, object]], skills[0]["ranks"])
    second_ranks = cast(list[dict[str, object]], skills[1]["ranks"])
    decorations = cast(list[dict[str, object]], response["decorations"])
    first_slot = cast(dict[str, object], decorations[0]["required_slot"])
    second_slot = cast(dict[str, object], decorations[1]["required_slot"])
    first_skills = cast(list[dict[str, object]], decorations[0]["skills"])
    second_skills = cast(list[dict[str, object]], decorations[1]["skills"])

    assert skills[0] is not skills[1]
    assert first_ranks is not second_ranks
    assert first_ranks[0] is not first_ranks[1]
    assert decorations[0] is not decorations[1]
    assert first_slot is not second_slot
    assert first_skills is not second_skills
    assert first_skills[0] is not second_skills[0]

    first_ranks[0]["level"] = 999
    first_slot["level"] = 999
    first_skills[0]["level"] = 999

    assert second_ranks[0]["level"] == 1
    assert second_slot["level"] == 2
    assert second_skills[0]["level"] == 2


def test_serializer_is_not_exported_from_api_package() -> None:
    import mhwilds_skill_sim.api as api

    assert not hasattr(api, "build_catalog_metadata_response")


def test_source_imports_only_domain_data_and_has_no_io_or_server_dependency() -> None:
    source_path = Path(catalog_response_module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    imported_names: dict[str, set[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported_modules.add(module)
            imported_names.setdefault(module, set()).update(
                alias.name for alias in node.names
            )

    assert imported_names["mhwilds_skill_sim.catalog.model"] == {"Catalog"}
    assert imported_names["mhwilds_skill_sim.domain.equipment"] == {
        "EquipmentPart",
        "WeaponKind",
    }
    assert imported_modules == {
        "__future__",
        "mhwilds_skill_sim.catalog.model",
        "mhwilds_skill_sim.domain.equipment",
    }

    forbidden_import_roots = {
        "fastapi",
        "pydantic",
        "starlette",
        "uvicorn",
        "io",
        "os",
        "pathlib",
        "json",
        "pickle",
        "subprocess",
        "socket",
        "urllib",
        "requests",
        "httpx",
        "mhwilds_skill_sim.api",
        "mhwilds_skill_sim.server",
    }
    assert not any(
        module == forbidden or module.startswith(f"{forbidden}.")
        for module in imported_modules
        for forbidden in forbidden_import_roots
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "print", "input"}
        for node in ast.walk(tree)
    )
