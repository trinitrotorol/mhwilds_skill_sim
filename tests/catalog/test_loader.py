from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog import Catalog, load_catalog
from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_decoration_definition,
    decode_decoration_slot,
    decode_equipment_definition,
    decode_skill_contribution,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution, SkillKind
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"


def catalog_value(
    *,
    schema_version: int = 1,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "equipment": [
            {
                "equipment_id": "fixture:weapon:training-blade",
                "part": "weapon",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "slots": [{"kind": "weapon", "level": 1}],
            },
        ],
        "decorations": [
            {
                "decoration_id": "fixture:decoration:weapon-power-1",
                "required_slot": {"kind": "weapon", "level": 1},
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            },
        ],
    }


def write_catalog_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_load_catalog_reads_tiny_catalog_from_path() -> None:
    catalog = load_catalog(path=FIXTURE_PATH)

    assert isinstance(catalog, Catalog)
    assert catalog.schema_version == 1
    assert len(catalog.equipment) == 9
    assert len(catalog.decorations) == 5
    assert len(catalog.skills) == 6


def test_load_catalog_reads_tiny_catalog_from_str() -> None:
    catalog = load_catalog(path=str(FIXTURE_PATH))

    assert isinstance(catalog, Catalog)
    assert catalog.schema_version == 1
    assert len(catalog.equipment) == 9
    assert len(catalog.decorations) == 5
    assert len(catalog.skills) == 6


def test_load_catalog_preserves_tiny_catalog_order() -> None:
    catalog = load_catalog(path=FIXTURE_PATH)

    assert [equipment.equipment_id for equipment in catalog.equipment] == [
        "fixture:weapon:training-blade",
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
        "fixture:chest:power-mail",
        "fixture:arms:socket-braces",
        "fixture:waist:precision-coil",
        "fixture:legs:tenderizer-greaves",
        "fixture:charm:power",
        "fixture:charm:precision",
    ]
    assert [decoration.decoration_id for decoration in catalog.decorations] == [
        "fixture:decoration:weapon-power-1",
        "fixture:decoration:weapon-precision-2",
        "fixture:decoration:armor-power-1",
        "fixture:decoration:armor-tenderizer-2",
        "fixture:decoration:armor-combination-2",
    ]


def test_load_catalog_reads_all_skill_kinds_in_expected_order() -> None:
    catalog = load_catalog(path=FIXTURE_PATH)

    assert [skill.skill_id for skill in catalog.skills] == [
        "skill:attack-boost",
        "skill:critical-eye",
        "skill:weakness-exploit",
        "skill:fixture-weapon-technique",
        "skill:fixture-series-bonus",
        "skill:fixture-group-bonus",
    ]
    assert {skill.kind for skill in catalog.skills} == {
        SkillKind.ARMOR,
        SkillKind.WEAPON,
        SkillKind.SERIES,
        SkillKind.GROUP,
    }


def test_load_catalog_reads_series_and_group_rank_thresholds() -> None:
    catalog = load_catalog(path=FIXTURE_PATH)
    skills_by_id = {skill.skill_id: skill for skill in catalog.skills}

    assert [
        rank.required_pieces
        for rank in skills_by_id["skill:fixture-series-bonus"].ranks
    ] == [2, 4]
    assert [
        rank.required_pieces for rank in skills_by_id["skill:fixture-group-bonus"].ranks
    ] == [3]


def test_load_catalog_is_keyword_only() -> None:
    signature = inspect.signature(load_catalog)

    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        load_catalog(FIXTURE_PATH)  # type: ignore[call-arg]


def test_catalog_package_exports_load_catalog_and_catalog() -> None:
    from mhwilds_skill_sim.catalog import Catalog as ExportedCatalog
    from mhwilds_skill_sim.catalog import load_catalog as exported_load_catalog

    assert ExportedCatalog is Catalog
    assert exported_load_catalog is load_catalog


def test_loader_module_exports_load_catalog_directly() -> None:
    from mhwilds_skill_sim.catalog.loader import load_catalog as direct_load_catalog

    assert direct_load_catalog is load_catalog


def test_load_catalog_reads_utf8_json_without_normalizing_ids(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    write_catalog_json(
        path,
        {
            "schema_version": 1,
            "equipment": [
                {
                    "equipment_id": "fixture:weapon:訓練太刀",
                    "part": "weapon",
                    "skills": [{"skill_id": "skill:攻撃", "level": 1}],
                    "slots": [],
                },
            ],
            "decorations": [
                {
                    "decoration_id": "fixture:decoration:攻撃珠",
                    "required_slot": {"kind": "weapon", "level": 1},
                    "skills": [{"skill_id": "skill:攻撃", "level": 1}],
                },
            ],
        },
    )

    catalog = load_catalog(path=path)

    assert catalog.equipment[0].equipment_id == "fixture:weapon:訓練太刀"
    assert catalog.equipment[0].skills[0].skill_id == "skill:攻撃"
    assert catalog.decorations[0].decoration_id == "fixture:decoration:攻撃珠"


@pytest.mark.parametrize("path", [None, 1, True])
def test_load_catalog_rejects_invalid_path_types(path: object) -> None:
    with pytest.raises(TypeError, match="path"):
        load_catalog(path=path)  # type: ignore[arg-type]


def test_load_catalog_converts_file_read_errors(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(CatalogDecodeError) as exc_info:
        load_catalog(path=path)

    assert exc_info.value.path == str(path)
    assert "read" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, OSError)


def test_load_catalog_converts_json_parse_errors(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(CatalogDecodeError) as exc_info:
        load_catalog(path=path)

    assert exc_info.value.path == str(path)
    assert "JSON" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    ("value", "expected_path", "expected_cause"),
    [
        ({}, "$", None),
        (
            {"schema_version": 0, "equipment": [], "decorations": []},
            "$.schema_version",
            ValueError,
        ),
    ],
)
def test_load_catalog_propagates_decode_catalog_errors(
    tmp_path: Path,
    value: object,
    expected_path: str,
    expected_cause: type[Exception] | None,
) -> None:
    path = tmp_path / "invalid-catalog.json"
    write_catalog_json(path, value)

    with pytest.raises(CatalogDecodeError) as exc_info:
        load_catalog(path=path)

    assert exc_info.value.path == expected_path
    if expected_cause is None:
        assert exc_info.value.__cause__ is None
    else:
        assert isinstance(exc_info.value.__cause__, expected_cause)


def test_existing_decode_catalog_still_works() -> None:
    catalog = decode_catalog(value=catalog_value())

    assert isinstance(catalog, Catalog)
    assert catalog.schema_version == 1


def test_existing_skill_contribution_decoder_still_works() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
    )

    assert contribution == SkillContribution("skill:attack-boost", 1)


def test_existing_decoration_slot_decoder_still_works() -> None:
    slot = decode_decoration_slot(value={"kind": "weapon", "level": 1})

    assert slot == DecorationSlot(DecorationKind.WEAPON, 1)


def test_existing_decoration_definition_decoder_still_works() -> None:
    decoration = decode_decoration_definition(
        value={
            "decoration_id": "fixture:decoration:weapon-power-1",
            "required_slot": {"kind": "weapon", "level": 1},
            "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
        },
    )

    assert decoration == DecorationDefinition(
        decoration_id="fixture:decoration:weapon-power-1",
        required_slot=DecorationSlot(DecorationKind.WEAPON, 1),
        skills=(SkillContribution("skill:attack-boost", 1),),
    )


def test_existing_equipment_definition_decoder_still_works() -> None:
    equipment = decode_equipment_definition(
        value={
            "equipment_id": "fixture:weapon:training-blade",
            "part": "weapon",
            "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            "slots": [{"kind": "weapon", "level": 1}],
        },
    )

    assert equipment == EquipmentDefinition(
        equipment_id="fixture:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(SkillContribution("skill:attack-boost", 1),),
        slots=(DecorationSlot(DecorationKind.WEAPON, 1),),
    )


def test_catalog_decode_error_still_imports_directly() -> None:
    error = CatalogDecodeError(path="$", detail="invalid object")

    assert str(error) == "$: invalid object"
