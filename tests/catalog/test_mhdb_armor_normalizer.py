from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

import mhwilds_skill_sim.catalog as catalog_package
from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_equipment_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.mhdb_armor import (
    build_skill_armor_and_decoration_catalog_document,
    normalize_mhdb_armor_snapshot,
)
from mhwilds_skill_sim.domain.equipment import EquipmentPart
from mhwilds_skill_sim.domain.slot import DecorationKind


ROOT = Path(__file__).resolve().parents[2]
SKILL_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"
ARMOR_SET_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_armor_sets_raw.json"
ARMOR_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_armor_raw.json"
DECORATION_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_decorations_raw.json"
ABSENT = object()


def load_fixture(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_skill_fixture() -> list[dict[str, object]]:
    return load_fixture(SKILL_FIXTURE_PATH)


def load_armor_set_fixture() -> list[dict[str, object]]:
    return load_fixture(ARMOR_SET_FIXTURE_PATH)


def load_armor_fixture() -> list[dict[str, object]]:
    return load_fixture(ARMOR_FIXTURE_PATH)


def load_decoration_fixture() -> list[dict[str, object]]:
    return load_fixture(DECORATION_FIXTURE_PATH)


def raw_bonus_skill(game_id: object) -> dict[str, object]:
    return {
        "gameId": game_id,
        "name": "ignored bonus skill stub",
    }


def raw_armor_set(
    raw_id: object = 701,
    *,
    game_id: object = -3001,
    set_bonus: object = ABSENT,
    group_bonus: object = ABSENT,
) -> dict[str, object]:
    if set_bonus is ABSENT:
        set_bonus = raw_bonus_skill(1003)
    if group_bonus is ABSENT:
        group_bonus = raw_bonus_skill(1004)
    return {
        "id": raw_id,
        "gameId": game_id,
        "setBonusSkill": set_bonus,
        "groupBonusSkill": group_bonus,
        "name": "ignored armor set name",
        "pieces": [],
    }


def raw_armor_skill(
    game_id: object = 1001,
    *,
    level: object = 1,
) -> dict[str, object]:
    return {
        "skill": {
            "gameId": game_id,
            "name": "ignored armor skill stub",
        },
        "level": level,
        "description": "ignored armor skill-rank extra",
    }


def raw_armor(
    raw_id: object = 801,
    *,
    name: object = "テストヘルムα",
    kind: object = "head",
    armor_set_id: object = 701,
    slots: object = ABSENT,
    skills: object = ABSENT,
) -> dict[str, object]:
    if slots is ABSENT:
        slots = [2, 1]
    if skills is ABSENT:
        skills = [raw_armor_skill()]
    return {
        "id": raw_id,
        "name": name,
        "kind": kind,
        "armorSet": {
            "id": armor_set_id,
            "name": "ignored armor-set stub",
        },
        "slots": slots,
        "skills": skills,
        "defense": 10,
    }


def armor_root_generator() -> Iterator[dict[str, object]]:
    yield raw_armor()


def armor_set_root_generator() -> Iterator[dict[str, object]]:
    yield raw_armor_set()


def slot_generator() -> Iterator[int]:
    yield 1


def armor_skills_generator() -> Iterator[dict[str, object]]:
    yield raw_armor_skill()


def test_fixture_normalizes_to_exact_six_armor_pieces_in_input_order() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=load_armor_fixture(),
        armor_set_snapshot=load_armor_set_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized == [
        {
            "equipment_id": "mhdb:armor:-3001:head",
            "display_name": "テストヘルムα",
            "part": "head",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 1}],
            "slots": [
                {"kind": "armor", "level": 2},
                {"kind": "armor", "level": 1},
            ],
            "series_skill_id": "mhdb:skill:1003",
            "group_skill_id": "mhdb:skill:1004",
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:armor:-3001:chest",
            "display_name": "テストメイルα",
            "part": "chest",
            "skills": [],
            "slots": [{"kind": "armor", "level": 1}],
            "series_skill_id": "mhdb:skill:1003",
            "group_skill_id": "mhdb:skill:1004",
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:armor:-3001:arms",
            "display_name": "テストアームα",
            "part": "arms",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 2}],
            "slots": [],
            "series_skill_id": "mhdb:skill:1003",
            "group_skill_id": "mhdb:skill:1004",
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:armor:-3001:waist",
            "display_name": "テストコイルα",
            "part": "waist",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 1}],
            "slots": [
                {"kind": "armor", "level": 1},
                {"kind": "armor", "level": 1},
            ],
            "series_skill_id": "mhdb:skill:1003",
            "group_skill_id": "mhdb:skill:1004",
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:armor:-3001:legs",
            "display_name": "テストグリーヴα",
            "part": "legs",
            "skills": [],
            "slots": [{"kind": "armor", "level": 3}],
            "series_skill_id": "mhdb:skill:1003",
            "group_skill_id": "mhdb:skill:1004",
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:armor:3002:head",
            "display_name": "テストヘルムβ",
            "part": "head",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 1}],
            "slots": [{"kind": "armor", "level": 2}],
            "series_skill_id": None,
            "group_skill_id": "mhdb:skill:1004",
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
    ]


def test_fixture_output_has_exact_nested_key_order_and_no_upstream_fields() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=load_armor_fixture(),
        armor_set_snapshot=load_armor_set_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    for equipment in normalized:
        assert list(equipment) == [
            "equipment_id",
            "display_name",
            "part",
            "skills",
            "slots",
            "series_skill_id",
            "group_skill_id",
            "allows_series_skill_assignment",
            "allows_group_skill_assignment",
        ]
        for skill in equipment["skills"]:  # type: ignore[union-attr]
            assert list(skill) == ["skill_id", "level"]
        for slot in equipment["slots"]:  # type: ignore[union-attr]
            assert list(slot) == ["kind", "level"]
        for ignored in (
            "id",
            "gameId",
            "armorSet",
            "defense",
            "resistances",
            "rarity",
            "rank",
            "description",
            "crafting",
            "pieces",
        ):
            assert ignored not in equipment


def test_fixture_preserves_ids_names_parts_skills_slots_and_memberships() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=load_armor_fixture(),
        armor_set_snapshot=load_armor_set_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    assert [equipment["equipment_id"] for equipment in normalized] == [
        "mhdb:armor:-3001:head",
        "mhdb:armor:-3001:chest",
        "mhdb:armor:-3001:arms",
        "mhdb:armor:-3001:waist",
        "mhdb:armor:-3001:legs",
        "mhdb:armor:3002:head",
    ]
    assert [equipment["display_name"] for equipment in normalized] == [
        "テストヘルムα",
        "テストメイルα",
        "テストアームα",
        "テストコイルα",
        "テストグリーヴα",
        "テストヘルムβ",
    ]
    assert [equipment["part"] for equipment in normalized] == [
        "head",
        "chest",
        "arms",
        "waist",
        "legs",
        "head",
    ]
    assert [equipment["skills"] for equipment in normalized] == [
        [{"skill_id": "mhdb:skill:1001", "level": 1}],
        [],
        [{"skill_id": "mhdb:skill:1001", "level": 2}],
        [{"skill_id": "mhdb:skill:1001", "level": 1}],
        [],
        [{"skill_id": "mhdb:skill:1001", "level": 1}],
    ]
    assert [equipment["slots"] for equipment in normalized] == [
        [{"kind": "armor", "level": 2}, {"kind": "armor", "level": 1}],
        [{"kind": "armor", "level": 1}],
        [],
        [{"kind": "armor", "level": 1}, {"kind": "armor", "level": 1}],
        [{"kind": "armor", "level": 3}],
        [{"kind": "armor", "level": 2}],
    ]
    assert all(
        equipment["series_skill_id"] == "mhdb:skill:1003"
        for equipment in normalized[:5]
    )
    assert normalized[5]["series_skill_id"] is None
    assert all(
        equipment["group_skill_id"] == "mhdb:skill:1004" for equipment in normalized
    )
    assert all(
        equipment["allows_series_skill_assignment"] is False
        and equipment["allows_group_skill_assignment"] is False
        for equipment in normalized
    )


def test_every_normalized_armor_piece_passes_existing_equipment_decoder() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=load_armor_fixture(),
        armor_set_snapshot=load_armor_set_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    decoded = [
        decode_equipment_definition(
            value=equipment,
            path=f"$.equipment[{index}]",
        )
        for index, equipment in enumerate(normalized)
    ]

    assert [equipment.part for equipment in decoded] == [
        EquipmentPart.HEAD,
        EquipmentPart.CHEST,
        EquipmentPart.ARMS,
        EquipmentPart.WAIST,
        EquipmentPart.LEGS,
        EquipmentPart.HEAD,
    ]
    assert all(
        slot.kind is DecorationKind.ARMOR
        for equipment in decoded
        for slot in equipment.slots
    )


def test_normalized_fixture_output_is_json_serializable() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=load_armor_fixture(),
        armor_set_snapshot=load_armor_set_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    encoded = json.dumps(normalized, ensure_ascii=False)

    assert "テストヘルムα" in encoded
    assert "\\u30c6" not in encoded


def test_combined_document_has_exact_shape_and_passes_catalog_decoder() -> None:
    document = build_skill_armor_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        armor_set_value=load_armor_set_fixture(),
        armor_value=load_armor_fixture(),
        decoration_value=load_decoration_fixture(),
    )

    assert list(document) == [
        "schema_version",
        "skills",
        "equipment",
        "decorations",
    ]
    assert document["schema_version"] == 1
    assert len(document["skills"]) == 4  # type: ignore[arg-type]
    assert len(document["equipment"]) == 6  # type: ignore[arg-type]
    assert len(document["decorations"]) == 3  # type: ignore[arg-type]
    assert "appraisal_charm_skill_groups" not in document
    assert "appraisal_charm_patterns" not in document

    decoded = decode_catalog(value=document)
    assert len(decoded.skills) == 4
    assert len(decoded.equipment) == 6
    assert len(decoded.decorations) == 3
    assert decoded.equipment[0].series_skill_id == "mhdb:skill:1003"
    assert decoded.equipment[0].group_skill_id == "mhdb:skill:1004"


def test_combined_document_can_be_written_and_loaded(tmp_path: Path) -> None:
    document = build_skill_armor_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        armor_set_value=load_armor_set_fixture(),
        armor_value=load_armor_fixture(),
        decoration_value=load_decoration_fixture(),
    )
    output_path = tmp_path / "catalog.json"
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = load_catalog(path=output_path)

    assert len(loaded.skills) == 4
    assert len(loaded.equipment) == 6
    assert len(loaded.decorations) == 3
    assert loaded.equipment[5].series_skill_id is None
    assert loaded.equipment[5].group_skill_id == "mhdb:skill:1004"


def test_normalization_does_not_mutate_any_input() -> None:
    skills = load_skill_fixture()
    armor_sets = load_armor_set_fixture()
    armor = load_armor_fixture()
    decorations = load_decoration_fixture()
    before = copy.deepcopy((skills, armor_sets, armor, decorations))

    normalize_mhdb_armor_snapshot(
        value=armor,
        armor_set_snapshot=armor_sets,
        skill_snapshot=skills,
    )
    build_skill_armor_and_decoration_catalog_document(
        skill_value=skills,
        armor_set_value=armor_sets,
        armor_value=armor,
        decoration_value=decorations,
    )

    assert (skills, armor_sets, armor, decorations) == before


def test_repeated_calls_return_independent_nested_containers() -> None:
    values = {
        "skill_value": load_skill_fixture(),
        "armor_set_value": load_armor_set_fixture(),
        "armor_value": load_armor_fixture(),
        "decoration_value": load_decoration_fixture(),
    }
    first = build_skill_armor_and_decoration_catalog_document(**values)
    second = build_skill_armor_and_decoration_catalog_document(**values)

    assert first == second
    assert first is not second
    assert first["skills"] is not second["skills"]
    assert first["equipment"] is not second["equipment"]
    assert first["equipment"][0] is not second["equipment"][0]  # type: ignore[index]
    assert first["equipment"][0]["skills"] is not second["equipment"][0]["skills"]  # type: ignore[index]
    assert first["equipment"][0]["slots"] is not second["equipment"][0]["slots"]  # type: ignore[index]
    assert first["decorations"] is not second["decorations"]

    first["equipment"][0]["display_name"] = "changed"  # type: ignore[index]
    first["equipment"][0]["slots"][0]["level"] = 999  # type: ignore[index]
    assert second == build_skill_armor_and_decoration_catalog_document(**values)


def test_empty_armor_and_empty_armor_set_snapshots_are_allowed() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=[],
        armor_set_snapshot=[],
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized == []


def test_empty_armor_sets_are_rejected_for_nonempty_armor_snapshot() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor()],
            armor_set_snapshot=[],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("skill_snapshot", [None, {}, (), "skills"])
def test_skill_snapshot_shape_validation_is_delegated(skill_snapshot: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[],
            skill_snapshot=skill_snapshot,
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.skills"
    assert "list" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_skill_snapshot_list_subclass_validation_is_delegated() -> None:
    class SkillList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[],
            skill_snapshot=SkillList(load_skill_fixture()),
        )

    assert exc_info.value.path == "$.skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_unknown_armor_skill_game_id() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[raw_armor_skill(9999)])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].skill.gameId"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("kind", ["weapon", "set", "group"])
def test_rejects_non_armor_skill_kind(kind: str) -> None:
    skills = load_skill_fixture()
    skills[0]["kind"] = kind
    if kind in ("set", "group"):
        skills[0]["ranks"] = [
            {
                "level": 1,
                "setPiecesRequired": 2,
                "description": "ignored",
            }
        ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor()],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=skills,
        )

    assert exc_info.value.path == "$.armor[0].skills[0]"
    assert "armor" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_armor_skill_level_above_maximum_rank() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[raw_armor_skill(level=4)])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].level"
    assert "maximum" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "armor_set_snapshot",
    [None, {}, (), "armor sets", armor_set_root_generator()],
)
def test_rejects_non_list_armor_set_root(armor_set_snapshot: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=armor_set_snapshot,
            skill_snapshot=load_skill_fixture(),
            armor_set_path="$.raw.armorSets",
        )

    assert exc_info.value.path == "$.raw.armorSets"
    assert "list" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_set_root_list_subclass() -> None:
    class ArmorSetList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=ArmorSetList([raw_armor_set()]),
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("armor_set", [None, "set", [], ()])
def test_rejects_non_dict_armor_set_item(armor_set: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[0]"
    assert "object" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_set_item_dict_subclass() -> None:
    class ArmorSetDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[ArmorSetDict(raw_armor_set())],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "missing_key",
    ["id", "gameId", "setBonusSkill", "groupBonusSkill"],
)
def test_rejects_missing_armor_set_keys(missing_key: str) -> None:
    armor_set = raw_armor_set()
    del armor_set[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor_sets[0].{missing_key}"
    assert missing_key in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("701", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_armor_set_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[raw_armor_set(raw_id)],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[0].id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_duplicate_armor_set_id_at_duplicate_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[
                raw_armor_set(701, game_id=-3001),
                raw_armor_set(701, game_id=3002),
            ],
            skill_snapshot=load_skill_fixture(),
            armor_set_path="$.raw.armorSets",
        )

    assert exc_info.value.path == "$.raw.armorSets[1].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("game_id", [True, False, 1.5, "-3001", None])
def test_rejects_non_exact_int_armor_set_game_id(game_id: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[raw_armor_set(game_id=game_id)],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[0].gameId"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_duplicate_armor_set_game_id_at_duplicate_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[
                raw_armor_set(701, game_id=-3001),
                raw_armor_set(702, game_id=-3001),
            ],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[1].gameId"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_armor_set_game_id_has_no_positive_minimum() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=[raw_armor()],
        armor_set_snapshot=[raw_armor_set(game_id=0)],
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized[0]["equipment_id"] == "mhdb:armor:0:head"


@pytest.mark.parametrize("field_name", ["setBonusSkill", "groupBonusSkill"])
@pytest.mark.parametrize("bonus_value", [True, 1, "skill", [], ()])
def test_rejects_invalid_bonus_skill_object_type(
    field_name: str,
    bonus_value: object,
) -> None:
    armor_set = raw_armor_set()
    armor_set[field_name] = bonus_value

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor_sets[0].{field_name}"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("field_name", ["setBonusSkill", "groupBonusSkill"])
def test_rejects_bonus_skill_dict_subclass(field_name: str) -> None:
    class BonusSkillDict(dict[str, object]):
        pass

    armor_set = raw_armor_set()
    armor_set[field_name] = BonusSkillDict({"gameId": 1003})

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor_sets[0].{field_name}"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("field_name", ["setBonusSkill", "groupBonusSkill"])
def test_rejects_missing_bonus_skill_game_id(field_name: str) -> None:
    armor_set = raw_armor_set()
    armor_set[field_name] = {"name": "missing gameId"}

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor_sets[0].{field_name}.gameId"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("field_name", ["setBonusSkill", "groupBonusSkill"])
@pytest.mark.parametrize("game_id", [True, False, 1.5, "1003", None])
def test_rejects_invalid_bonus_skill_game_id(
    field_name: str,
    game_id: object,
) -> None:
    armor_set = raw_armor_set()
    armor_set[field_name] = raw_bonus_skill(game_id)

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor_sets[0].{field_name}.gameId"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("field_name", ["setBonusSkill", "groupBonusSkill"])
def test_rejects_unknown_bonus_skill(field_name: str) -> None:
    armor_set = raw_armor_set()
    armor_set[field_name] = raw_bonus_skill(9999)

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[armor_set],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor_sets[0].{field_name}.gameId"
    assert "existing" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_series_bonus_pointing_to_non_series_skill() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[raw_armor_set(set_bonus=raw_bonus_skill(1001))],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[0].setBonusSkill.gameId"
    assert "series" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_group_bonus_pointing_to_non_group_skill() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[],
            armor_set_snapshot=[raw_armor_set(group_bonus=raw_bonus_skill(1001))],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor_sets[0].groupBonusSkill.gameId"
    assert "group" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "armor_value",
    [None, {}, (), "armor", armor_root_generator()],
)
def test_rejects_non_list_armor_root(armor_value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=armor_value,
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
            path="$.raw.armor",
        )

    assert exc_info.value.path == "$.raw.armor"
    assert "list" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_root_list_subclass() -> None:
    class ArmorList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=ArmorList([raw_armor()]),
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("armor", [None, "armor", [], ()])
def test_rejects_non_dict_armor_item(armor: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[armor],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0]"
    assert "object" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_item_dict_subclass() -> None:
    class ArmorDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[ArmorDict(raw_armor())],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "missing_key",
    ["id", "name", "kind", "slots", "skills", "armorSet"],
)
def test_rejects_missing_armor_keys(missing_key: str) -> None:
    armor = raw_armor()
    del armor[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[armor],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor[0].{missing_key}"
    assert missing_key in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("801", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_raw_armor_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(raw_id)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_duplicate_raw_armor_id_at_duplicate_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[
                raw_armor(801, kind="head"),
                raw_armor(801, kind="chest"),
            ],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
            path="$.raw.armor",
        )

    assert exc_info.value.path == "$.raw.armor[1].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("name", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" テストヘルム", ValueError),
        ("テストヘルム ", ValueError),
    ],
)
def test_rejects_invalid_armor_name(
    name: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(name=name)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].name"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_armor_name_string_subclass() -> None:
    class Name(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(name=Name("Test Helm"))],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].name"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    ("kind", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("Head", ValueError),
        ("helm", ValueError),
        ("weapon", ValueError),
        ("", ValueError),
    ],
)
def test_rejects_invalid_armor_kind(
    kind: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(kind=kind)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].kind"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_armor_kind_string_subclass() -> None:
    class Kind(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(kind=Kind("head"))],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].kind"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("armor_set_stub", [None, True, 1, "set", [], ()])
def test_rejects_invalid_armor_set_stub(armor_set_stub: object) -> None:
    armor = raw_armor()
    armor["armorSet"] = armor_set_stub

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[armor],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].armorSet"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_set_stub_dict_subclass() -> None:
    class ArmorSetStubDict(dict[str, object]):
        pass

    armor = raw_armor()
    armor["armorSet"] = ArmorSetStubDict({"id": 701})

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[armor],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].armorSet"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_armor_set_stub_id() -> None:
    armor = raw_armor()
    armor["armorSet"] = {"name": "missing id"}

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[armor],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].armorSet.id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("701", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_armor_set_stub_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(armor_set_id=raw_id)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].armorSet.id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_unresolved_armor_set_stub_id() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(armor_set_id=999)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].armorSet.id"
    assert "existing" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_duplicate_stable_equipment_id_at_later_kind_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(801), raw_armor(802)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
            path="$.raw.armor",
        )

    assert exc_info.value.path == "$.raw.armor[1].kind"
    assert "unique" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "slots",
    [(1,), {1}, {"level": 1}, slot_generator(), None, "slots"],
)
def test_rejects_non_list_armor_slots(slots: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(slots=slots)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].slots"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_slots_list_subclass() -> None:
    class SlotList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(slots=SlotList([1]))],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].slots"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_more_than_three_armor_slots() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(slots=[1, 2, 3, 4])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].slots"
    assert "three" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("slot", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_armor_slot_level(
    slot: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(slots=[1, slot])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].slots[1]"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_armor_slot_level_has_no_artificial_upper_bound() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=[raw_armor(slots=[999])],
        armor_set_snapshot=[raw_armor_set()],
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized[0]["slots"] == [{"kind": "armor", "level": 999}]


@pytest.mark.parametrize(
    "skills",
    [
        (raw_armor_skill(),),
        {"skill": {"gameId": 1001}},
        armor_skills_generator(),
        None,
        "skills",
    ],
)
def test_rejects_non_list_armor_skills(skills: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=skills)],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=SkillList([raw_armor_skill()]))],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_empty_armor_skills_are_accepted() -> None:
    normalized = normalize_mhdb_armor_snapshot(
        value=[raw_armor(skills=[])],
        armor_set_snapshot=[raw_armor_set()],
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized[0]["skills"] == []


@pytest.mark.parametrize("skill_rank", [None, "rank", [], ()])
def test_rejects_non_dict_armor_skill_rank(skill_rank: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[skill_rank])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_skill_rank_dict_subclass() -> None:
    class SkillRankDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[SkillRankDict(raw_armor_skill())])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("missing_key", ["skill", "level"])
def test_rejects_missing_armor_skill_rank_keys(missing_key: str) -> None:
    skill_rank = raw_armor_skill()
    del skill_rank[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[skill_rank])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == f"$.armor[0].skills[0].{missing_key}"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("skill_stub", [None, True, 1, "skill", [], ()])
def test_rejects_invalid_armor_skill_stub(skill_stub: object) -> None:
    skill_rank = raw_armor_skill()
    skill_rank["skill"] = skill_stub

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[skill_rank])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].skill"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_armor_skill_stub_dict_subclass() -> None:
    class SkillStubDict(dict[str, object]):
        pass

    skill_rank = raw_armor_skill()
    skill_rank["skill"] = SkillStubDict({"gameId": 1001})

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[skill_rank])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].skill"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_armor_skill_game_id() -> None:
    skill_rank = raw_armor_skill()
    skill_rank["skill"] = {"name": "missing gameId"}

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[skill_rank])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].skill.gameId"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("game_id", [True, False, 1.5, "1001", None])
def test_rejects_invalid_armor_skill_game_id(game_id: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[raw_armor_skill(game_id)])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].skill.gameId"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    ("level", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_armor_skill_level(
    level: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[raw_armor_skill(level=level)])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].level"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_duplicate_resolved_skills_use_existing_equipment_invariant() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[
                raw_armor(
                    skills=[
                        raw_armor_skill(1001, level=1),
                        raw_armor_skill(1001, level=2),
                    ]
                )
            ],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
            path="$.raw.armor",
        )

    assert exc_info.value.path == "$.raw.armor[0]"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_custom_paths_are_preserved() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(slots=[1, 0])],
            armor_set_snapshot=[raw_armor_set()],
            skill_snapshot=load_skill_fixture(),
            path="$.raw.armor",
            armor_set_path="$.raw.armorSets",
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.armor[0].slots[1]"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_normalizer_functions_require_keyword_arguments() -> None:
    normalize_signature = inspect.signature(normalize_mhdb_armor_snapshot)
    build_signature = inspect.signature(
        build_skill_armor_and_decoration_catalog_document
    )

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in normalize_signature.parameters.values()
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in build_signature.parameters.values()
    )
    assert normalize_signature.parameters["path"].default == "$.armor"
    assert normalize_signature.parameters["armor_set_path"].default == "$.armor_sets"
    assert normalize_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["armor_set_path"].default == "$.armor_sets"
    assert build_signature.parameters["armor_path"].default == "$.armor"
    assert build_signature.parameters["decoration_path"].default == "$.decorations"

    with pytest.raises(TypeError):
        normalize_mhdb_armor_snapshot([], [], [])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        build_skill_armor_and_decoration_catalog_document(  # type: ignore[call-arg]
            [], [], [], []
        )


def test_mhdb_armor_normalizers_are_not_exported_from_catalog_package() -> None:
    assert not hasattr(catalog_package, "normalize_mhdb_armor_snapshot")
    assert not hasattr(
        catalog_package,
        "build_skill_armor_and_decoration_catalog_document",
    )
