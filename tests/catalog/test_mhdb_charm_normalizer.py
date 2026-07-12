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
from mhwilds_skill_sim.catalog.mhdb_charms import (
    build_skill_weapon_armor_charm_and_decoration_catalog_document,
    normalize_mhdb_charm_snapshot,
)
from mhwilds_skill_sim.domain.equipment import EquipmentPart, WeaponKind

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "fixtures"
SKILL_FIXTURE_PATH = FIXTURE_DIR / "mhdb_skills_raw.json"
WEAPON_FIXTURE_PATH = FIXTURE_DIR / "mhdb_weapons_raw.json"
ARMOR_SET_FIXTURE_PATH = FIXTURE_DIR / "mhdb_armor_sets_raw.json"
ARMOR_FIXTURE_PATH = FIXTURE_DIR / "mhdb_armor_raw.json"
CHARM_FIXTURE_PATH = FIXTURE_DIR / "mhdb_charms_raw.json"
DECORATION_FIXTURE_PATH = FIXTURE_DIR / "mhdb_decorations_raw.json"
ABSENT = object()


def load_fixture(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_skills() -> list[dict[str, object]]:
    return load_fixture(SKILL_FIXTURE_PATH)


def load_charms() -> list[dict[str, object]]:
    return load_fixture(CHARM_FIXTURE_PATH)


def raw_charm_skill(
    raw_skill_id: object = 501,
    *,
    level: object = 1,
) -> dict[str, object]:
    return {
        "skill": {
            "id": raw_skill_id,
            "name": "ignored skill stub extra",
        },
        "level": level,
        "description": "ignored skill-rank extra",
    }


def raw_rank(
    raw_id: object = 1201,
    *,
    name: object = "固定護石（テスト）",
    level: object = 1,
    skills: object = ABSENT,
) -> dict[str, object]:
    if skills is ABSENT:
        skills = [raw_charm_skill()]
    return {
        "id": raw_id,
        "name": name,
        "level": level,
        "skills": skills,
        "description": "ignored rank extra",
    }


def raw_charm(
    raw_id: object = 1101,
    *,
    game_id: object = -5001,
    randomized: object = False,
    ranks: object = ABSENT,
) -> dict[str, object]:
    if ranks is ABSENT:
        ranks = [raw_rank()]
    return {
        "id": raw_id,
        "gameId": game_id,
        "randomized": randomized,
        "ranks": ranks,
        "rarity": "ignored parent extra",
    }


def charm_root_generator() -> Iterator[dict[str, object]]:
    yield raw_charm()


def expect_charm_error(
    value: object,
    *,
    expected_path: str,
    expected_cause: type[Exception],
    skills: object | None = None,
    detail: str | None = None,
) -> CatalogDecodeError:
    if skills is None:
        skills = load_skills()
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_charm_snapshot(value=value, skill_snapshot=skills)

    error = exc_info.value
    assert error.path == expected_path
    assert isinstance(error.__cause__, expected_cause)
    if detail is not None:
        assert detail in error.detail
    return error


def build_document() -> dict[str, object]:
    return build_skill_weapon_armor_charm_and_decoration_catalog_document(
        skill_value=load_skills(),
        weapon_value=load_fixture(WEAPON_FIXTURE_PATH),
        armor_set_value=load_fixture(ARMOR_SET_FIXTURE_PATH),
        armor_value=load_fixture(ARMOR_FIXTURE_PATH),
        charm_value=load_charms(),
        decoration_value=load_fixture(DECORATION_FIXTURE_PATH),
    )


def test_fixture_normalizes_to_exact_fixed_charm_ranks_in_level_order() -> None:
    normalized = normalize_mhdb_charm_snapshot(
        value=load_charms(),
        skill_snapshot=load_skills(),
    )

    assert normalized == [
        {
            "equipment_id": "mhdb:charm:-5001:rank-1",
            "display_name": "攻撃の護石Ⅰ（テスト）",
            "part": "charm",
            "weapon_kind": None,
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 1}],
            "slots": [],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:charm:-5001:rank-2",
            "display_name": "攻撃の護石Ⅱ（テスト）",
            "part": "charm",
            "weapon_kind": None,
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 2}],
            "slots": [],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
        {
            "equipment_id": "mhdb:charm:5002:rank-1",
            "display_name": "技術の護石（テスト）",
            "part": "charm",
            "weapon_kind": None,
            "skills": [
                {"skill_id": "mhdb:skill:-1002", "level": 1},
                {"skill_id": "mhdb:skill:1001", "level": 1},
            ],
            "slots": [],
            "series_skill_id": None,
            "group_skill_id": None,
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        },
    ]


def test_fixture_output_has_exact_keys_and_excludes_upstream_fields() -> None:
    normalized = normalize_mhdb_charm_snapshot(
        value=load_charms(),
        skill_snapshot=load_skills(),
    )

    for charm in normalized:
        assert list(charm) == [
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
        assert all(list(skill) == ["skill_id", "level"] for skill in charm["skills"])
        for ignored in (
            "id",
            "gameId",
            "randomized",
            "ranks",
            "name",
            "level",
            "rarity",
            "description",
            "crafting",
        ):
            assert ignored not in charm


def test_fixture_output_decodes_and_is_unicode_json_serializable() -> None:
    normalized = normalize_mhdb_charm_snapshot(
        value=load_charms(),
        skill_snapshot=load_skills(),
    )

    decoded = [
        decode_equipment_definition(value=value, path=f"$.charms[{index}]")
        for index, value in enumerate(normalized)
    ]
    encoded = json.dumps(normalized, ensure_ascii=False)

    assert all(charm.part is EquipmentPart.CHARM for charm in decoded)
    assert all(charm.weapon_kind is None for charm in decoded)
    assert all(charm.slots == () for charm in decoded)
    assert all(charm.series_skill_id is None for charm in decoded)
    assert all(charm.group_skill_id is None for charm in decoded)
    assert all(not charm.allows_series_skill_assignment for charm in decoded)
    assert all(not charm.allows_group_skill_assignment for charm in decoded)
    assert "攻撃の護石Ⅰ（テスト）" in encoded
    assert "\\u653b" not in encoded
    assert "5003" not in encoded


def test_combined_document_has_exact_shape_and_equipment_order() -> None:
    document = build_document()

    assert list(document) == [
        "schema_version",
        "skills",
        "equipment",
        "decorations",
    ]
    assert len(document["skills"]) == 4
    assert len(document["equipment"]) == 12
    assert len(document["decorations"]) == 3
    equipment_ids = [item["equipment_id"] for item in document["equipment"]]
    assert equipment_ids[:3] == [
        "mhdb:weapon:great-sword:4001",
        "mhdb:weapon:great-sword:-4002",
        "mhdb:weapon:bow:4001",
    ]
    assert equipment_ids[3:9] == [
        "mhdb:armor:-3001:head",
        "mhdb:armor:-3001:chest",
        "mhdb:armor:-3001:arms",
        "mhdb:armor:-3001:waist",
        "mhdb:armor:-3001:legs",
        "mhdb:armor:3002:head",
    ]
    assert equipment_ids[9:] == [
        "mhdb:charm:-5001:rank-1",
        "mhdb:charm:-5001:rank-2",
        "mhdb:charm:5002:rank-1",
    ]
    assert "appraisal_charm_skill_groups" not in document
    assert "appraisal_charm_patterns" not in document

    decoded = decode_catalog(value=document)
    assert decoded.equipment[1].weapon_kind is WeaponKind.GREAT_SWORD
    assert decoded.equipment[1].allows_series_skill_assignment is True
    assert decoded.equipment[3].series_skill_id == "mhdb:skill:1003"
    assert decoded.equipment[9].part is EquipmentPart.CHARM


def test_combined_document_can_be_written_and_loaded(tmp_path: Path) -> None:
    output = tmp_path / "catalog.json"
    output.write_text(
        json.dumps(build_document(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = load_catalog(path=output)

    assert len(loaded.skills) == 4
    assert len(loaded.equipment) == 12
    assert len(loaded.decorations) == 3
    assert loaded.equipment[-1].equipment_id == "mhdb:charm:5002:rank-1"


def test_normalization_does_not_mutate_inputs() -> None:
    skills = load_skills()
    weapons = load_fixture(WEAPON_FIXTURE_PATH)
    armor_sets = load_fixture(ARMOR_SET_FIXTURE_PATH)
    armor = load_fixture(ARMOR_FIXTURE_PATH)
    charms = load_charms()
    decorations = load_fixture(DECORATION_FIXTURE_PATH)
    before = copy.deepcopy((skills, weapons, armor_sets, armor, charms, decorations))

    normalize_mhdb_charm_snapshot(value=charms, skill_snapshot=skills)
    build_skill_weapon_armor_charm_and_decoration_catalog_document(
        skill_value=skills,
        weapon_value=weapons,
        armor_set_value=armor_sets,
        armor_value=armor,
        charm_value=charms,
        decoration_value=decorations,
    )

    assert (skills, weapons, armor_sets, armor, charms, decorations) == before


def test_repeated_calls_return_independent_nested_containers() -> None:
    values = {"value": load_charms(), "skill_snapshot": load_skills()}
    first = normalize_mhdb_charm_snapshot(**values)
    second = normalize_mhdb_charm_snapshot(**values)

    assert first == second
    assert first is not second
    assert first[0] is not second[0]
    assert first[0]["skills"] is not second[0]["skills"]
    assert first[0]["slots"] is not second[0]["slots"]
    first[0]["display_name"] = "changed"
    first[0]["skills"][0]["level"] = 99
    assert second == normalize_mhdb_charm_snapshot(**values)

    first_document = build_document()
    second_document = build_document()
    assert first_document == second_document
    assert first_document is not second_document
    assert first_document["skills"] is not second_document["skills"]
    assert first_document["equipment"] is not second_document["equipment"]
    assert first_document["equipment"][-1] is not second_document["equipment"][-1]
    assert first_document["decorations"] is not second_document["decorations"]


@pytest.mark.parametrize("skill_snapshot", [None, {}, (), "skills"])
def test_skill_snapshot_shape_validation_is_delegated(skill_snapshot: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_charm_snapshot(
            value=[],
            skill_snapshot=skill_snapshot,
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_skill_snapshot_list_and_item_subclasses_are_rejected_by_task_045() -> None:
    class SkillList(list[object]):
        pass

    class SkillDict(dict[str, object]):
        pass

    for skill_snapshot, expected_path in (
        (SkillList(load_skills()), "$.skills"),
        (list([SkillDict(load_skills()[0])]), "$.skills[0]"),
    ):
        with pytest.raises(CatalogDecodeError) as exc_info:
            normalize_mhdb_charm_snapshot(value=[], skill_snapshot=skill_snapshot)
        assert exc_info.value.path == expected_path
        assert isinstance(exc_info.value.__cause__, TypeError)


def test_strict_skill_validation_is_delegated_before_database_id_indexing() -> None:
    skill = load_skills()[0]
    del skill["gameId"]

    expect_charm_error(
        [],
        skills=[skill],
        expected_path="$.skills[0].gameId",
        expected_cause=ValueError,
    )


def test_rejects_missing_raw_skill_database_id() -> None:
    skill = load_skills()[0]
    del skill["id"]

    expect_charm_error(
        [],
        skills=[skill],
        expected_path="$.skills[0].id",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("raw_id", "cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("501", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_raw_skill_database_id(
    raw_id: object,
    cause: type[Exception],
) -> None:
    skill = load_skills()[0]
    skill["id"] = raw_id

    expect_charm_error(
        [],
        skills=[skill],
        expected_path="$.skills[0].id",
        expected_cause=cause,
    )


def test_rejects_duplicate_raw_skill_database_id() -> None:
    skills = load_skills()[:2]
    skills[1]["id"] = skills[0]["id"]

    expect_charm_error(
        [],
        skills=skills,
        expected_path="$.skills[1].id",
        expected_cause=ValueError,
    )


def test_rejects_unknown_charm_skill_database_id() -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[raw_charm_skill(999)])])],
        expected_path="$.charms[0].ranks[0].skills[0].skill.id",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("raw_skill_id", [503, 504])
def test_rejects_series_and_group_charm_skills(raw_skill_id: int) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[raw_charm_skill(raw_skill_id)])])],
        expected_path="$.charms[0].ranks[0].skills[0]",
        expected_cause=ValueError,
        detail="armor or weapon",
    )


def test_rejects_charm_skill_level_above_maximum() -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[raw_charm_skill(level=4)])])],
        expected_path="$.charms[0].ranks[0].skills[0].level",
        expected_cause=ValueError,
        detail="maximum",
    )


@pytest.mark.parametrize(
    "value",
    [None, {}, (), "charms", charm_root_generator()],
)
def test_rejects_non_list_charm_root(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_charm_snapshot(
            value=value,
            skill_snapshot=load_skills(),
            path="$.raw.charms",
        )

    assert exc_info.value.path == "$.raw.charms"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_charm_root_list_subclass_and_allows_empty_list() -> None:
    class CharmList(list[object]):
        pass

    expect_charm_error(
        CharmList([raw_charm()]),
        expected_path="$.charms",
        expected_cause=TypeError,
    )
    assert normalize_mhdb_charm_snapshot(value=[], skill_snapshot=load_skills()) == []


@pytest.mark.parametrize("value", [None, "charm", [], ()])
def test_rejects_non_dict_parent(value: object) -> None:
    expect_charm_error(
        [value],
        expected_path="$.charms[0]",
        expected_cause=TypeError,
    )


def test_rejects_parent_dict_subclass() -> None:
    class CharmDict(dict[str, object]):
        pass

    expect_charm_error(
        [CharmDict(raw_charm())],
        expected_path="$.charms[0]",
        expected_cause=TypeError,
    )


@pytest.mark.parametrize("key", ["id", "gameId", "randomized", "ranks"])
def test_rejects_missing_parent_required_field(key: str) -> None:
    charm = raw_charm()
    del charm[key]

    expect_charm_error(
        [charm],
        expected_path=f"$.charms[0].{key}",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("raw_id", "cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("1101", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_parent_id(raw_id: object, cause: type[Exception]) -> None:
    expect_charm_error(
        [raw_charm(raw_id)],
        expected_path="$.charms[0].id",
        expected_cause=cause,
    )


def test_rejects_later_duplicate_parent_id() -> None:
    expect_charm_error(
        [raw_charm(), raw_charm(game_id=5002)],
        expected_path="$.charms[1].id",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("game_id", [True, False, 1.5, "5001", None])
def test_rejects_invalid_parent_game_id(game_id: object) -> None:
    expect_charm_error(
        [raw_charm(game_id=game_id)],
        expected_path="$.charms[0].gameId",
        expected_cause=TypeError,
    )


def test_rejects_later_duplicate_game_id_including_randomized_parent() -> None:
    expect_charm_error(
        [raw_charm(), raw_charm(1102, game_id=-5001, randomized=True, ranks=[])],
        expected_path="$.charms[1].gameId",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("randomized", [0, 1, "false", None, [], {}])
def test_rejects_non_bool_randomized(randomized: object) -> None:
    expect_charm_error(
        [raw_charm(randomized=randomized)],
        expected_path="$.charms[0].randomized",
        expected_cause=TypeError,
    )


@pytest.mark.parametrize("ranks", [None, {}, (), "ranks"])
def test_rejects_non_list_parent_ranks(ranks: object) -> None:
    expect_charm_error(
        [raw_charm(ranks=ranks)],
        expected_path="$.charms[0].ranks",
        expected_cause=TypeError,
    )


def test_rejects_parent_ranks_list_subclass() -> None:
    class RankList(list[object]):
        pass

    expect_charm_error(
        [raw_charm(ranks=RankList([raw_rank()]))],
        expected_path="$.charms[0].ranks",
        expected_cause=TypeError,
    )


def test_rejects_empty_fixed_ranks_but_skips_randomized_rank_contents() -> None:
    expect_charm_error(
        [raw_charm(ranks=[])],
        expected_path="$.charms[0].ranks",
        expected_cause=ValueError,
    )
    randomized = [raw_charm(randomized=True, ranks=[None, {"malformed": "ignored"}])]
    before = copy.deepcopy(randomized)

    assert (
        normalize_mhdb_charm_snapshot(
            value=randomized,
            skill_snapshot=load_skills(),
        )
        == []
    )
    assert randomized == before


@pytest.mark.parametrize("rank", [None, "rank", [], ()])
def test_rejects_non_dict_fixed_rank(rank: object) -> None:
    expect_charm_error(
        [raw_charm(ranks=[rank])],
        expected_path="$.charms[0].ranks[0]",
        expected_cause=TypeError,
    )


def test_rejects_fixed_rank_dict_subclass() -> None:
    class RankDict(dict[str, object]):
        pass

    expect_charm_error(
        [raw_charm(ranks=[RankDict(raw_rank())])],
        expected_path="$.charms[0].ranks[0]",
        expected_cause=TypeError,
    )


@pytest.mark.parametrize("key", ["id", "name", "level", "skills"])
def test_rejects_missing_fixed_rank_field(key: str) -> None:
    rank = raw_rank()
    del rank[key]

    expect_charm_error(
        [raw_charm(ranks=[rank])],
        expected_path=f"$.charms[0].ranks[0].{key}",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("raw_id", "cause"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("1201", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_rank_id(raw_id: object, cause: type[Exception]) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(raw_id)])],
        expected_path="$.charms[0].ranks[0].id",
        expected_cause=cause,
    )


def test_rejects_later_duplicate_rank_id() -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(), raw_rank(level=2)])],
        expected_path="$.charms[0].ranks[1].id",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("name", "cause"),
    [
        (None, TypeError),
        (1, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" leading", ValueError),
        ("trailing ", ValueError),
    ],
)
def test_rejects_invalid_rank_name(name: object, cause: type[Exception]) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(name=name)])],
        expected_path="$.charms[0].ranks[0].name",
        expected_cause=cause,
    )


@pytest.mark.parametrize(
    ("level", "cause"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_rank_level(level: object, cause: type[Exception]) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(level=level)])],
        expected_path="$.charms[0].ranks[0].level",
        expected_cause=cause,
    )


def test_rejects_duplicate_and_noncontiguous_rank_levels() -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(), raw_rank(1202)])],
        expected_path="$.charms[0].ranks[1].level",
        expected_cause=ValueError,
    )
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(level=2)])],
        expected_path="$.charms[0].ranks[0].level",
        expected_cause=ValueError,
        detail="1, 2, ..., N",
    )
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(), raw_rank(1202, level=3)])],
        expected_path="$.charms[0].ranks[1].level",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("skills", [None, {}, (), "skills"])
def test_rejects_non_list_rank_skills(skills: object) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=skills)])],
        expected_path="$.charms[0].ranks[0].skills",
        expected_cause=TypeError,
    )


def test_rejects_rank_skills_list_subclass_and_empty_list() -> None:
    class SkillRankList(list[object]):
        pass

    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=SkillRankList([raw_charm_skill()]))])],
        expected_path="$.charms[0].ranks[0].skills",
        expected_cause=TypeError,
    )
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[])])],
        expected_path="$.charms[0].ranks[0].skills",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("skill_rank", [None, "skill", [], ()])
def test_rejects_non_dict_skill_rank(skill_rank: object) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[skill_rank])])],
        expected_path="$.charms[0].ranks[0].skills[0]",
        expected_cause=TypeError,
    )


def test_rejects_skill_rank_dict_subclass() -> None:
    class SkillRankDict(dict[str, object]):
        pass

    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[SkillRankDict(raw_charm_skill())])])],
        expected_path="$.charms[0].ranks[0].skills[0]",
        expected_cause=TypeError,
    )


@pytest.mark.parametrize("key", ["skill", "level"])
def test_rejects_missing_skill_rank_field(key: str) -> None:
    skill_rank = raw_charm_skill()
    del skill_rank[key]

    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[skill_rank])])],
        expected_path=f"$.charms[0].ranks[0].skills[0].{key}",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("skill", [None, "skill", [], ()])
def test_rejects_non_dict_skill_stub(skill: object) -> None:
    skill_rank = raw_charm_skill()
    skill_rank["skill"] = skill

    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[skill_rank])])],
        expected_path="$.charms[0].ranks[0].skills[0].skill",
        expected_cause=TypeError,
    )


def test_rejects_skill_stub_dict_subclass() -> None:
    class SkillStubDict(dict[str, object]):
        pass

    skill_rank = raw_charm_skill()
    skill_rank["skill"] = SkillStubDict({"id": 501})
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[skill_rank])])],
        expected_path="$.charms[0].ranks[0].skills[0].skill",
        expected_cause=TypeError,
    )


def test_rejects_missing_skill_stub_id() -> None:
    skill_rank = raw_charm_skill()
    skill_rank["skill"] = {"name": "missing id"}

    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[skill_rank])])],
        expected_path="$.charms[0].ranks[0].skills[0].skill.id",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("raw_skill_id", "cause"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("501", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_skill_stub_id(
    raw_skill_id: object,
    cause: type[Exception],
) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[raw_charm_skill(raw_skill_id)])])],
        expected_path="$.charms[0].ranks[0].skills[0].skill.id",
        expected_cause=cause,
    )


@pytest.mark.parametrize(
    ("level", "cause"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_rejects_invalid_skill_rank_level(
    level: object,
    cause: type[Exception],
) -> None:
    expect_charm_error(
        [raw_charm(ranks=[raw_rank(skills=[raw_charm_skill(level=level)])])],
        expected_path="$.charms[0].ranks[0].skills[0].level",
        expected_cause=cause,
    )


def test_duplicate_resolved_skills_are_rejected_by_equipment_invariant() -> None:
    expect_charm_error(
        [
            raw_charm(
                ranks=[raw_rank(skills=[raw_charm_skill(501), raw_charm_skill(501)])]
            )
        ],
        expected_path="$.charms[0].ranks[0]",
        expected_cause=ValueError,
        detail="duplicate skill_id",
    )


def test_custom_paths_are_preserved() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_charm_snapshot(
            value=[raw_charm(ranks=[raw_rank(level=2)])],
            skill_snapshot=load_skills(),
            path="$.raw.charms",
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.charms[0].ranks[0].level"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_normalizer_functions_require_keyword_arguments_and_defaults() -> None:
    normalize_signature = inspect.signature(normalize_mhdb_charm_snapshot)
    build_signature = inspect.signature(
        build_skill_weapon_armor_charm_and_decoration_catalog_document
    )

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in normalize_signature.parameters.values()
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in build_signature.parameters.values()
    )
    assert normalize_signature.parameters["path"].default == "$.charms"
    assert normalize_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["weapon_path"].default == "$.weapons"
    assert build_signature.parameters["armor_set_path"].default == "$.armor_sets"
    assert build_signature.parameters["armor_path"].default == "$.armor"
    assert build_signature.parameters["charm_path"].default == "$.charms"
    assert build_signature.parameters["decoration_path"].default == "$.decorations"

    with pytest.raises(TypeError):
        normalize_mhdb_charm_snapshot([], [])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        build_skill_weapon_armor_charm_and_decoration_catalog_document(  # type: ignore[call-arg]
            [], [], [], [], [], []
        )


def test_charm_normalizers_are_not_exported_from_catalog_package() -> None:
    assert not hasattr(catalog_package, "normalize_mhdb_charm_snapshot")
    assert not hasattr(
        catalog_package,
        "build_skill_weapon_armor_charm_and_decoration_catalog_document",
    )
