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
from mhwilds_skill_sim.catalog.mhdb_weapons import (
    build_skill_weapon_armor_and_decoration_catalog_document,
    normalize_mhdb_weapon_snapshot,
)
from mhwilds_skill_sim.domain.equipment import EquipmentPart, WeaponKind
from mhwilds_skill_sim.domain.slot import DecorationKind


ROOT = Path(__file__).resolve().parents[2]
SKILL_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"
WEAPON_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_weapons_raw.json"
ARMOR_SET_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_armor_sets_raw.json"
ARMOR_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_armor_raw.json"
DECORATION_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_decorations_raw.json"
ABSENT = object()


def load_fixture(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_skill_fixture() -> list[dict[str, object]]:
    return load_fixture(SKILL_FIXTURE_PATH)


def load_weapon_fixture() -> list[dict[str, object]]:
    return load_fixture(WEAPON_FIXTURE_PATH)


def load_armor_set_fixture() -> list[dict[str, object]]:
    return load_fixture(ARMOR_SET_FIXTURE_PATH)


def load_armor_fixture() -> list[dict[str, object]]:
    return load_fixture(ARMOR_FIXTURE_PATH)


def load_decoration_fixture() -> list[dict[str, object]]:
    return load_fixture(DECORATION_FIXTURE_PATH)


def raw_skill_rank(
    level: int = 1,
    *,
    required_pieces: object = ABSENT,
) -> dict[str, object]:
    rank: dict[str, object] = {"level": level, "description": "ignored"}
    if required_pieces is not ABSENT:
        rank["setPiecesRequired"] = required_pieces
    return rank


def raw_skill(
    raw_id: object = 502,
    *,
    game_id: object = -1002,
    kind: str = "weapon",
    ranks: object = ABSENT,
) -> dict[str, object]:
    if ranks is ABSENT:
        ranks = [raw_skill_rank()]
    return {
        "id": raw_id,
        "gameId": game_id,
        "name": "Synthetic Skill",
        "kind": kind,
        "ranks": ranks,
        "description": "ignored skill extra",
    }


def raw_series(
    raw_id: object = 10001,
    *,
    game_id: object = 5001,
) -> dict[str, object]:
    return {
        "id": raw_id,
        "gameId": game_id,
        "name": "ignored crafting series stub",
    }


def raw_weapon_skill(
    raw_skill_id: object = 502,
    *,
    level: object = 1,
) -> dict[str, object]:
    return {
        "skill": {
            "id": raw_skill_id,
            "name": "ignored weapon skill stub",
        },
        "level": level,
        "description": "ignored weapon skill-rank extra",
    }


def raw_weapon(
    raw_id: object = 901,
    *,
    game_id: object = 4001,
    kind: object = "great-sword",
    name: object = "テスト大剣",
    slots: object = ABSENT,
    skills: object = ABSENT,
    series: object = ABSENT,
) -> dict[str, object]:
    if slots is ABSENT:
        slots = [2, 1]
    if skills is ABSENT:
        skills = [raw_weapon_skill()]
    if series is ABSENT:
        series = raw_series()
    return {
        "id": raw_id,
        "gameId": game_id,
        "kind": kind,
        "name": name,
        "slots": slots,
        "skills": skills,
        "series": series,
        "damage": 100,
        "rarity": 4,
    }


def weapon_root_generator() -> Iterator[dict[str, object]]:
    yield raw_weapon()


def slots_generator() -> Iterator[int]:
    yield 1


def skills_generator() -> Iterator[dict[str, object]]:
    yield raw_weapon_skill()


def test_fixture_normalizes_to_exact_three_weapons_in_input_order() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=load_weapon_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized == [
        {
            "equipment_id": "mhdb:weapon:great-sword:4001",
            "display_name": "テスト大剣",
            "part": "weapon",
            "weapon_kind": "great-sword",
            "skills": [{"skill_id": "mhdb:skill:-1002", "level": 1}],
            "slots": [
                {"kind": "weapon", "level": 2},
                {"kind": "weapon", "level": 1},
            ],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:weapon:great-sword:-4002",
            "display_name": "テストアーティア大剣",
            "part": "weapon",
            "weapon_kind": "great-sword",
            "skills": [],
            "slots": [
                {"kind": "weapon", "level": 3},
                {"kind": "weapon", "level": 2},
                {"kind": "weapon", "level": 1},
            ],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": True,
            "allows_group_skill_assignment": True,
        },
        {
            "equipment_id": "mhdb:weapon:bow:4001",
            "display_name": "テスト弓",
            "part": "weapon",
            "weapon_kind": "bow",
            "skills": [],
            "slots": [{"kind": "weapon", "level": 1}],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
    ]


def test_fixture_output_has_exact_key_order_and_no_upstream_fields() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=load_weapon_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    for weapon in normalized:
        assert list(weapon) == [
            "equipment_id",
            "display_name",
            "part",
            "weapon_kind",
            "skills",
            "slots",
            "series_skill_id",
            "group_skill_id",
            "allows_series_skill_assignment",
            "allows_group_skill_assignment",
        ]
        for skill in weapon["skills"]:  # type: ignore[union-attr]
            assert list(skill) == ["skill_id", "level"]
            assert "id" not in skill
        for slot in weapon["slots"]:  # type: ignore[union-attr]
            assert list(slot) == ["kind", "level"]
        for ignored in (
            "id",
            "gameId",
            "kind",
            "name",
            "series",
            "damage",
            "specials",
            "sharpness",
            "handicraft",
            "rarity",
            "affinity",
            "defense",
            "elderseal",
            "crafting",
            "coatings",
        ):
            assert ignored not in weapon


def test_fixture_preserves_ids_names_kinds_skills_slots_and_flags() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=load_weapon_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    assert [weapon["equipment_id"] for weapon in normalized] == [
        "mhdb:weapon:great-sword:4001",
        "mhdb:weapon:great-sword:-4002",
        "mhdb:weapon:bow:4001",
    ]
    assert [weapon["display_name"] for weapon in normalized] == [
        "テスト大剣",
        "テストアーティア大剣",
        "テスト弓",
    ]
    assert [weapon["weapon_kind"] for weapon in normalized] == [
        "great-sword",
        "great-sword",
        "bow",
    ]
    assert [weapon["skills"] for weapon in normalized] == [
        [{"skill_id": "mhdb:skill:-1002", "level": 1}],
        [],
        [],
    ]
    assert [weapon["slots"] for weapon in normalized] == [
        [{"kind": "weapon", "level": 2}, {"kind": "weapon", "level": 1}],
        [
            {"kind": "weapon", "level": 3},
            {"kind": "weapon", "level": 2},
            {"kind": "weapon", "level": 1},
        ],
        [{"kind": "weapon", "level": 1}],
    ]
    assert all(weapon["series_skill_id"] is None for weapon in normalized)
    assert all(weapon["group_skill_id"] is None for weapon in normalized)
    assert [weapon["allows_series_skill_assignment"] for weapon in normalized] == [
        False,
        True,
        False,
    ]
    assert [weapon["allows_group_skill_assignment"] for weapon in normalized] == [
        False,
        True,
        False,
    ]


def test_same_game_id_across_different_weapon_kinds_is_accepted() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[
            raw_weapon(901, game_id=4001, kind="great-sword"),
            raw_weapon(903, game_id=4001, kind="bow"),
        ],
        skill_snapshot=load_skill_fixture(),
    )

    assert [weapon["equipment_id"] for weapon in normalized] == [
        "mhdb:weapon:great-sword:4001",
        "mhdb:weapon:bow:4001",
    ]


def test_crafting_series_ids_are_never_copied_to_memberships() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=load_weapon_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    encoded = json.dumps(normalized)
    assert "5001" not in encoded
    assert "5002" not in encoded
    assert all(weapon["series_skill_id"] is None for weapon in normalized)
    assert all(weapon["group_skill_id"] is None for weapon in normalized)


def test_every_normalized_weapon_passes_existing_equipment_decoder() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=load_weapon_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    decoded = [
        decode_equipment_definition(
            value=weapon,
            path=f"$.equipment[{index}]",
        )
        for index, weapon in enumerate(normalized)
    ]

    assert all(weapon.part is EquipmentPart.WEAPON for weapon in decoded)
    assert [weapon.weapon_kind for weapon in decoded] == [
        WeaponKind.GREAT_SWORD,
        WeaponKind.GREAT_SWORD,
        WeaponKind.BOW,
    ]
    assert all(
        slot.kind is DecorationKind.WEAPON
        for weapon in decoded
        for slot in weapon.slots
    )


def test_normalized_fixture_output_is_json_serializable() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=load_weapon_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    encoded = json.dumps(normalized, ensure_ascii=False)

    assert "テストアーティア大剣" in encoded
    assert "\\u30c6" not in encoded


def test_combined_document_has_exact_shape_and_equipment_order() -> None:
    document = build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        weapon_value=load_weapon_fixture(),
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
    assert len(document["equipment"]) == 9  # type: ignore[arg-type]
    assert len(document["decorations"]) == 3  # type: ignore[arg-type]
    assert [
        equipment["equipment_id"]
        for equipment in document["equipment"]  # type: ignore[union-attr]
    ] == [
        "mhdb:weapon:great-sword:4001",
        "mhdb:weapon:great-sword:-4002",
        "mhdb:weapon:bow:4001",
        "mhdb:armor:-3001:head",
        "mhdb:armor:-3001:chest",
        "mhdb:armor:-3001:arms",
        "mhdb:armor:-3001:waist",
        "mhdb:armor:-3001:legs",
        "mhdb:armor:3002:head",
    ]
    assert "appraisal_charm_skill_groups" not in document
    assert "appraisal_charm_patterns" not in document

    decoded = decode_catalog(value=document)
    assert len(decoded.skills) == 4
    assert len(decoded.equipment) == 9
    assert len(decoded.decorations) == 3
    assert decoded.equipment[1].weapon_kind is WeaponKind.GREAT_SWORD
    assert decoded.equipment[1].allows_series_skill_assignment is True
    assert decoded.equipment[1].allows_group_skill_assignment is True
    assert decoded.equipment[3].series_skill_id == "mhdb:skill:1003"


def test_combined_document_can_be_written_and_loaded(tmp_path: Path) -> None:
    document = build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        weapon_value=load_weapon_fixture(),
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
    assert len(loaded.equipment) == 9
    assert len(loaded.decorations) == 3
    assert loaded.equipment[0].weapon_kind is WeaponKind.GREAT_SWORD
    assert loaded.equipment[1].allows_series_skill_assignment is True
    assert loaded.equipment[3].series_skill_id == "mhdb:skill:1003"


def test_normalization_does_not_mutate_any_input() -> None:
    skills = load_skill_fixture()
    weapons = load_weapon_fixture()
    armor_sets = load_armor_set_fixture()
    armor = load_armor_fixture()
    decorations = load_decoration_fixture()
    before = copy.deepcopy((skills, weapons, armor_sets, armor, decorations))

    normalize_mhdb_weapon_snapshot(value=weapons, skill_snapshot=skills)
    build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=skills,
        weapon_value=weapons,
        armor_set_value=armor_sets,
        armor_value=armor,
        decoration_value=decorations,
    )

    assert (skills, weapons, armor_sets, armor, decorations) == before


def test_repeated_calls_return_independent_nested_containers() -> None:
    values = {
        "skill_value": load_skill_fixture(),
        "weapon_value": load_weapon_fixture(),
        "armor_set_value": load_armor_set_fixture(),
        "armor_value": load_armor_fixture(),
        "decoration_value": load_decoration_fixture(),
    }
    first = build_skill_weapon_armor_and_decoration_catalog_document(**values)
    second = build_skill_weapon_armor_and_decoration_catalog_document(**values)

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
    assert second == build_skill_weapon_armor_and_decoration_catalog_document(**values)


def test_series_null_weapon_with_bonus_skills_produces_valid_catalog() -> None:
    document = build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        weapon_value=[raw_weapon(skills=[], series=None)],
        armor_set_value=[],
        armor_value=[],
        decoration_value=[],
    )

    decoded = decode_catalog(value=document)
    assert decoded.equipment[0].allows_series_skill_assignment is True
    assert decoded.equipment[0].allows_group_skill_assignment is True


@pytest.mark.parametrize(
    ("skills", "expected_detail"),
    [
        ([raw_skill()], "series skill"),
        (
            [
                raw_skill(),
                raw_skill(
                    503,
                    game_id=1003,
                    kind="set",
                    ranks=[raw_skill_rank(required_pieces=2)],
                ),
            ],
            "group skill",
        ),
    ],
)
def test_series_null_weapon_requires_available_bonus_skill_definitions(
    skills: list[dict[str, object]],
    expected_detail: str,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        build_skill_weapon_armor_and_decoration_catalog_document(
            skill_value=skills,
            weapon_value=[raw_weapon(skills=[], series=None)],
            armor_set_value=[],
            armor_value=[],
            decoration_value=[],
        )

    assert exc_info.value.path == "$"
    assert expected_detail in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_regular_weapon_does_not_require_bonus_skill_definitions() -> None:
    document = build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=[raw_skill()],
        weapon_value=[raw_weapon()],
        armor_set_value=[],
        armor_value=[],
        decoration_value=[],
    )

    decoded = decode_catalog(value=document)
    assert decoded.equipment[0].allows_series_skill_assignment is False
    assert decoded.equipment[0].allows_group_skill_assignment is False


@pytest.mark.parametrize("skill_snapshot", [None, {}, (), "skills"])
def test_skill_snapshot_shape_validation_is_delegated(skill_snapshot: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[],
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
        normalize_mhdb_weapon_snapshot(
            value=[],
            skill_snapshot=SkillList([raw_skill()]),
        )

    assert exc_info.value.path == "$.skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_raw_skill_database_id() -> None:
    skill = raw_skill()
    del skill["id"]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(value=[], skill_snapshot=[skill])

    assert exc_info.value.path == "$.skills[0].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("502", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_raw_skill_database_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[],
            skill_snapshot=[raw_skill(raw_id)],
        )

    assert exc_info.value.path == "$.skills[0].id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_duplicate_raw_skill_database_id() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[],
            skill_snapshot=[
                raw_skill(502, game_id=-1002),
                raw_skill(502, game_id=-1003),
            ],
        )

    assert exc_info.value.path == "$.skills[1].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_unknown_weapon_skill_id() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[raw_weapon_skill(999)])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].skill.id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("kind", ["armor", "set", "group"])
def test_rejects_non_weapon_skill_kind(kind: str) -> None:
    ranks = (
        [raw_skill_rank(required_pieces=2)]
        if kind in ("set", "group")
        else [raw_skill_rank()]
    )

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon()],
            skill_snapshot=[raw_skill(kind=kind, ranks=ranks)],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0]"
    assert "weapon" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_weapon_skill_level_above_maximum_rank() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[raw_weapon_skill(level=2)])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].level"
    assert "maximum" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "weapon_value",
    [None, {}, (), "weapons", weapon_root_generator()],
)
def test_rejects_non_list_weapon_root(weapon_value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=weapon_value,
            skill_snapshot=[raw_skill()],
            path="$.raw.weapons",
        )

    assert exc_info.value.path == "$.raw.weapons"
    assert "list" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_weapon_root_list_subclass() -> None:
    class WeaponList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=WeaponList([raw_weapon()]),
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_empty_weapon_root_is_allowed() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[],
        skill_snapshot=[raw_skill()],
    )

    assert normalized == []


@pytest.mark.parametrize("weapon", [None, "weapon", [], ()])
def test_rejects_non_dict_weapon_item(weapon: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[weapon],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0]"
    assert "object" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_weapon_item_dict_subclass() -> None:
    class WeaponDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[WeaponDict(raw_weapon())],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "missing_key",
    ["id", "gameId", "kind", "name", "slots", "skills", "series"],
)
def test_rejects_missing_weapon_keys(missing_key: str) -> None:
    weapon = raw_weapon()
    del weapon[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[weapon],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == f"$.weapons[0].{missing_key}"
    assert missing_key in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("901", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_raw_weapon_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(raw_id)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_duplicate_raw_weapon_id_at_later_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[
                raw_weapon(901, game_id=4001),
                raw_weapon(901, game_id=4002),
            ],
            skill_snapshot=[raw_skill()],
            path="$.raw.weapons",
        )

    assert exc_info.value.path == "$.raw.weapons[1].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("game_id", [True, False, 1.5, "4001", None])
def test_rejects_non_exact_int_weapon_game_id(game_id: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(game_id=game_id)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].gameId"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_duplicate_kind_and_game_id_pair_at_later_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[
                raw_weapon(901, game_id=4001, kind="bow"),
                raw_weapon(902, game_id=4001, kind="bow"),
            ],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[1].gameId"
    assert "pair" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("weapon_kind", list(WeaponKind))
def test_normalizer_accepts_every_exact_weapon_kind(
    weapon_kind: WeaponKind,
) -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[raw_weapon(kind=weapon_kind.value)],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["weapon_kind"] == weapon_kind.value
    assert normalized[0]["equipment_id"] == (f"mhdb:weapon:{weapon_kind.value}:4001")


@pytest.mark.parametrize(
    ("kind", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("Great-Sword", ValueError),
        ("great_sword", ValueError),
        ("gs", ValueError),
        ("", ValueError),
    ],
)
def test_rejects_invalid_weapon_kind(
    kind: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(kind=kind)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].kind"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_weapon_kind_string_subclass() -> None:
    class Kind(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(kind=Kind("great-sword"))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].kind"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    ("name", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" テスト大剣", ValueError),
        ("テスト大剣 ", ValueError),
    ],
)
def test_rejects_invalid_weapon_name(
    name: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(name=name)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].name"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_weapon_name_string_subclass() -> None:
    class Name(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(name=Name("Test Great Sword"))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].name"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "slots",
    [(1,), {1}, {"level": 1}, slots_generator(), None, "slots"],
)
def test_rejects_non_list_weapon_slots(slots: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(slots=slots)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].slots"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_weapon_slots_list_subclass() -> None:
    class SlotList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(slots=SlotList([1]))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].slots"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_more_than_three_weapon_slots() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(slots=[1, 2, 3, 4])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].slots"
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
def test_rejects_invalid_weapon_slot_level(
    slot: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(slots=[1, slot])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].slots[1]"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_weapon_slot_level_has_no_artificial_upper_bound() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[raw_weapon(slots=[999])],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["slots"] == [{"kind": "weapon", "level": 999}]


def test_empty_weapon_slots_are_accepted() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[raw_weapon(slots=[])],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["slots"] == []


def test_duplicate_weapon_slot_levels_are_preserved() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[raw_weapon(slots=[2, 2, 1])],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["slots"] == [
        {"kind": "weapon", "level": 2},
        {"kind": "weapon", "level": 2},
        {"kind": "weapon", "level": 1},
    ]


@pytest.mark.parametrize(
    "skills",
    [
        (raw_weapon_skill(),),
        {"skill": {"id": 502}},
        skills_generator(),
        None,
        "skills",
    ],
)
def test_rejects_non_list_weapon_skills(skills: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=skills)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_weapon_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=SkillList([raw_weapon_skill()]))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_empty_weapon_skills_are_accepted() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[raw_weapon(skills=[])],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["skills"] == []


@pytest.mark.parametrize("skill_rank", [None, "rank", [], ()])
def test_rejects_non_dict_weapon_skill_rank(skill_rank: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[skill_rank])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_weapon_skill_rank_dict_subclass() -> None:
    class SkillRankDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[SkillRankDict(raw_weapon_skill())])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("missing_key", ["skill", "level"])
def test_rejects_missing_weapon_skill_rank_keys(missing_key: str) -> None:
    skill_rank = raw_weapon_skill()
    del skill_rank[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[skill_rank])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == f"$.weapons[0].skills[0].{missing_key}"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("skill_stub", [None, True, 1, "skill", [], ()])
def test_rejects_invalid_weapon_skill_stub(skill_stub: object) -> None:
    skill_rank = raw_weapon_skill()
    skill_rank["skill"] = skill_stub

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[skill_rank])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].skill"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_weapon_skill_stub_dict_subclass() -> None:
    class SkillStubDict(dict[str, object]):
        pass

    skill_rank = raw_weapon_skill()
    skill_rank["skill"] = SkillStubDict({"id": 502})

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[skill_rank])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].skill"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_weapon_skill_id() -> None:
    skill_rank = raw_weapon_skill()
    skill_rank["skill"] = {"name": "missing id"}

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[skill_rank])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].skill.id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("502", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_weapon_skill_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[raw_weapon_skill(raw_id)])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].skill.id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


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
def test_rejects_invalid_weapon_skill_level(
    level: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(skills=[raw_weapon_skill(level=level)])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].skills[0].level"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_duplicate_resolved_skills_use_existing_equipment_invariant() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[
                raw_weapon(
                    skills=[
                        raw_weapon_skill(502, level=1),
                        raw_weapon_skill(502, level=1),
                    ]
                )
            ],
            skill_snapshot=[raw_skill()],
            path="$.raw.weapons",
        )

    assert exc_info.value.path == "$.raw.weapons[0]"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("series", [True, 1, "series", [], ()])
def test_rejects_invalid_series_type(series: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(series=series)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].series"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_series_dict_subclass() -> None:
    class SeriesDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(series=SeriesDict(raw_series()))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].series"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("missing_key", ["id", "gameId"])
def test_rejects_missing_series_keys(missing_key: str) -> None:
    series = raw_series()
    del series[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(series=series)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == f"$.weapons[0].series.{missing_key}"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("10001", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_series_id(
    raw_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(series=raw_series(raw_id))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].series.id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize("game_id", [True, False, 1.5, "5001", None])
def test_rejects_invalid_series_game_id(game_id: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(series=raw_series(game_id=game_id))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$.weapons[0].series.gameId"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_series_game_id_has_no_positive_minimum() -> None:
    normalized = normalize_mhdb_weapon_snapshot(
        value=[raw_weapon(series=raw_series(game_id=-5001))],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["series_skill_id"] is None
    assert normalized[0]["allows_series_skill_assignment"] is False


def test_custom_paths_are_preserved() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_weapon_snapshot(
            value=[raw_weapon(slots=[1, 0])],
            skill_snapshot=[raw_skill()],
            path="$.raw.weapons",
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.weapons[0].slots[1]"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_normalizer_functions_require_keyword_arguments() -> None:
    normalize_signature = inspect.signature(normalize_mhdb_weapon_snapshot)
    build_signature = inspect.signature(
        build_skill_weapon_armor_and_decoration_catalog_document
    )

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in normalize_signature.parameters.values()
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in build_signature.parameters.values()
    )
    assert normalize_signature.parameters["path"].default == "$.weapons"
    assert normalize_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["weapon_path"].default == "$.weapons"
    assert build_signature.parameters["armor_set_path"].default == "$.armor_sets"
    assert build_signature.parameters["armor_path"].default == "$.armor"
    assert build_signature.parameters["decoration_path"].default == "$.decorations"

    with pytest.raises(TypeError):
        normalize_mhdb_weapon_snapshot([], [])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        build_skill_weapon_armor_and_decoration_catalog_document(  # type: ignore[call-arg]
            [], [], [], [], []
        )


def test_mhdb_weapon_normalizers_are_not_exported_from_catalog_package() -> None:
    assert not hasattr(catalog_package, "normalize_mhdb_weapon_snapshot")
    assert not hasattr(
        catalog_package,
        "build_skill_weapon_armor_and_decoration_catalog_document",
    )
