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
    decode_decoration_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.mhdb_decorations import (
    build_skill_and_decoration_catalog_document,
    normalize_mhdb_decoration_snapshot,
)
from mhwilds_skill_sim.domain.slot import DecorationKind


ROOT = Path(__file__).resolve().parents[2]
SKILL_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"
DECORATION_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_decorations_raw.json"
ABSENT = object()


def load_skill_fixture() -> list[dict[str, object]]:
    return json.loads(SKILL_FIXTURE_PATH.read_text(encoding="utf-8"))


def load_decoration_fixture() -> list[dict[str, object]]:
    return json.loads(DECORATION_FIXTURE_PATH.read_text(encoding="utf-8"))


def raw_skill_rank(
    level: int = 1,
    *,
    required_pieces: object = ABSENT,
) -> dict[str, object]:
    value: dict[str, object] = {"level": level, "description": "ignored"}
    if required_pieces is not ABSENT:
        value["setPiecesRequired"] = required_pieces
    return value


def raw_skill(
    raw_id: object = 501,
    *,
    game_id: object = 1001,
    name: str = "攻撃力強化（テスト）",
    kind: str = "armor",
    ranks: object = ABSENT,
) -> dict[str, object]:
    if ranks is ABSENT:
        ranks = [raw_skill_rank()]
    return {
        "id": raw_id,
        "gameId": game_id,
        "name": name,
        "kind": kind,
        "ranks": ranks,
        "description": "ignored skill extra",
    }


def raw_decoration_skill(
    raw_skill_id: object = 501,
    *,
    level: object = 1,
) -> dict[str, object]:
    return {
        "skill": {
            "id": raw_skill_id,
            "name": "ignored skill stub",
        },
        "level": level,
        "description": "ignored rank extra",
    }


def raw_decoration(
    game_id: object = 2002,
    *,
    name: object = "攻撃珠【1】（テスト）",
    slot: object = 1,
    kind: object = "armor",
    skills: object = ABSENT,
) -> dict[str, object]:
    if skills is ABSENT:
        skills = [raw_decoration_skill()]
    return {
        "id": 602,
        "gameId": game_id,
        "name": name,
        "slot": slot,
        "kind": kind,
        "skills": skills,
        "description": "ignored decoration extra",
        "rarity": 5,
    }


def root_generator() -> Iterator[dict[str, object]]:
    yield raw_decoration()


def skills_generator() -> Iterator[dict[str, object]]:
    yield raw_decoration_skill()


def test_fixture_normalizes_to_exact_three_decorations_in_input_order() -> None:
    normalized = normalize_mhdb_decoration_snapshot(
        value=load_decoration_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    assert normalized == [
        {
            "decoration_id": "mhdb:decoration:-2001",
            "display_name": "武器技珠【1】（テスト）",
            "required_slot": {"kind": "weapon", "level": 1},
            "skills": [{"skill_id": "mhdb:skill:-1002", "level": 1}],
        },
        {
            "decoration_id": "mhdb:decoration:2002",
            "display_name": "攻撃珠【1】（テスト）",
            "required_slot": {"kind": "armor", "level": 1},
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 1}],
        },
        {
            "decoration_id": "mhdb:decoration:2003",
            "display_name": "攻撃珠Ⅱ【2】（テスト）",
            "required_slot": {"kind": "armor", "level": 2},
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 2}],
        },
    ]


def test_fixture_output_has_exact_nested_key_order_and_no_raw_ids() -> None:
    normalized = normalize_mhdb_decoration_snapshot(
        value=load_decoration_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    for decoration in normalized:
        assert list(decoration) == [
            "decoration_id",
            "display_name",
            "required_slot",
            "skills",
        ]
        assert list(decoration["required_slot"]) == ["kind", "level"]  # type: ignore[arg-type]
        assert "id" not in decoration
        assert "gameId" not in decoration
        assert "description" not in decoration
        assert "rarity" not in decoration
        assert "icon" not in decoration
        for skill in decoration["skills"]:  # type: ignore[union-attr]
            assert list(skill) == ["skill_id", "level"]
            assert "skill" not in skill
            assert "id" not in skill


def test_fixture_preserves_names_kinds_slots_and_resolved_levels() -> None:
    normalized = normalize_mhdb_decoration_snapshot(
        value=load_decoration_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    assert [decoration["decoration_id"] for decoration in normalized] == [
        "mhdb:decoration:-2001",
        "mhdb:decoration:2002",
        "mhdb:decoration:2003",
    ]
    assert [decoration["display_name"] for decoration in normalized] == [
        "武器技珠【1】（テスト）",
        "攻撃珠【1】（テスト）",
        "攻撃珠Ⅱ【2】（テスト）",
    ]
    assert [decoration["required_slot"] for decoration in normalized] == [
        {"kind": "weapon", "level": 1},
        {"kind": "armor", "level": 1},
        {"kind": "armor", "level": 2},
    ]
    assert [decoration["skills"] for decoration in normalized] == [
        [{"skill_id": "mhdb:skill:-1002", "level": 1}],
        [{"skill_id": "mhdb:skill:1001", "level": 1}],
        [{"skill_id": "mhdb:skill:1001", "level": 2}],
    ]


def test_every_normalized_decoration_passes_existing_decoder() -> None:
    normalized = normalize_mhdb_decoration_snapshot(
        value=load_decoration_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    decoded = [
        decode_decoration_definition(
            value=decoration,
            path=f"$.decorations[{index}]",
        )
        for index, decoration in enumerate(normalized)
    ]

    assert [decoration.required_slot.kind for decoration in decoded] == [
        DecorationKind.WEAPON,
        DecorationKind.ARMOR,
        DecorationKind.ARMOR,
    ]
    assert [decoration.display_name for decoration in decoded] == [
        "武器技珠【1】（テスト）",
        "攻撃珠【1】（テスト）",
        "攻撃珠Ⅱ【2】（テスト）",
    ]


def test_normalized_fixture_output_is_json_serializable() -> None:
    normalized = normalize_mhdb_decoration_snapshot(
        value=load_decoration_fixture(),
        skill_snapshot=load_skill_fixture(),
    )

    encoded = json.dumps(normalized, ensure_ascii=False)

    assert "武器技珠【1】（テスト）" in encoded
    assert "\\u6b66" not in encoded


def test_combined_document_has_exact_shape_and_passes_catalog_decoder() -> None:
    document = build_skill_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
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
    assert document["equipment"] == []
    assert len(document["decorations"]) == 3  # type: ignore[arg-type]
    assert "appraisal_charm_skill_groups" not in document
    assert "appraisal_charm_patterns" not in document

    decoded = decode_catalog(value=document)
    assert len(decoded.skills) == 4
    assert len(decoded.decorations) == 3
    assert decoded.equipment == ()


def test_combined_document_can_be_written_and_loaded(
    tmp_path: Path,
) -> None:
    document = build_skill_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        decoration_value=load_decoration_fixture(),
    )
    output_path = tmp_path / "catalog.json"
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = load_catalog(path=output_path)

    assert len(loaded.skills) == 4
    assert len(loaded.decorations) == 3
    assert loaded.decorations[0].skills[0].skill_id == "mhdb:skill:-1002"


def test_normalization_does_not_mutate_either_input() -> None:
    skills = load_skill_fixture()
    decorations = load_decoration_fixture()
    skills_before = copy.deepcopy(skills)
    decorations_before = copy.deepcopy(decorations)

    normalize_mhdb_decoration_snapshot(
        value=decorations,
        skill_snapshot=skills,
    )
    build_skill_and_decoration_catalog_document(
        skill_value=skills,
        decoration_value=decorations,
    )

    assert skills == skills_before
    assert decorations == decorations_before


def test_repeated_calls_return_independent_nested_containers() -> None:
    skills = load_skill_fixture()
    decorations = load_decoration_fixture()
    first = build_skill_and_decoration_catalog_document(
        skill_value=skills,
        decoration_value=decorations,
    )
    second = build_skill_and_decoration_catalog_document(
        skill_value=skills,
        decoration_value=decorations,
    )

    assert first == second
    assert first is not second
    assert first["skills"] is not second["skills"]
    assert first["decorations"] is not second["decorations"]
    assert first["decorations"][0] is not second["decorations"][0]  # type: ignore[index]
    assert (
        first["decorations"][0]["required_slot"]
        is not second["decorations"][0]["required_slot"]
    )  # type: ignore[index]
    assert first["decorations"][0]["skills"] is not second["decorations"][0]["skills"]  # type: ignore[index]
    assert (
        first["decorations"][0]["skills"][0]
        is not second["decorations"][0]["skills"][0]
    )  # type: ignore[index]

    first["decorations"][0]["display_name"] = "changed"  # type: ignore[index]
    first["decorations"][0]["skills"][0]["level"] = 999  # type: ignore[index]
    assert second == build_skill_and_decoration_catalog_document(
        skill_value=skills,
        decoration_value=decorations,
    )


@pytest.mark.parametrize("skill_snapshot", [None, {}, (), "skills"])
def test_skill_snapshot_shape_validation_is_delegated(
    skill_snapshot: object,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
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
        normalize_mhdb_decoration_snapshot(
            value=[],
            skill_snapshot=SkillList([raw_skill()]),
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_raw_skill_database_id() -> None:
    skill_value = raw_skill()
    del skill_value["id"]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[],
            skill_snapshot=[skill_value],
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.skills[0].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_id", "expected_cause"),
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
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[],
            skill_snapshot=[raw_skill(raw_id)],
        )

    assert exc_info.value.path == "$.skills[0].id"
    assert "id" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_duplicate_raw_skill_database_id_at_duplicate_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[],
            skill_snapshot=[
                raw_skill(501, game_id=1001),
                raw_skill(501, game_id=1002, name="Other Skill"),
            ],
        )

    assert exc_info.value.path == "$.skills[1].id"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_duplicate_skill_game_id_remains_rejected_by_skill_normalizer() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[],
            skill_snapshot=[
                raw_skill(501, game_id=1001),
                raw_skill(502, game_id=1001, name="Other Skill"),
            ],
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.skills[1].gameId"
    assert "gameId" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("value", [None, {}, (), "decorations", root_generator()])
def test_rejects_non_list_decoration_root(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=value,
            skill_snapshot=[raw_skill()],
            path="$.raw.decorations",
        )

    assert exc_info.value.path == "$.raw.decorations"
    assert "list" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_decoration_root_list_subclass() -> None:
    class DecorationList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=DecorationList([raw_decoration()]),
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("value", [None, "decoration", [], ()])
def test_rejects_non_dict_decoration_item(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[value],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0]"
    assert "object" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_decoration_item_dict_subclass() -> None:
    class DecorationDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[DecorationDict(raw_decoration())],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "missing_key",
    ["gameId", "name", "slot", "kind", "skills"],
)
def test_rejects_missing_decoration_keys(missing_key: str) -> None:
    value = raw_decoration()
    del value[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[value],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == f"$[0].{missing_key}"
    assert missing_key in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("game_id", [True, False, 1.5, "2002", None])
def test_rejects_non_exact_int_decoration_game_id(game_id: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(game_id)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].gameId"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_duplicate_decoration_game_id_at_duplicate_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[
                raw_decoration(2002),
                raw_decoration(2002, name="Other Decoration"),
            ],
            skill_snapshot=[raw_skill()],
            path="$.raw.decorations",
        )

    assert exc_info.value.path == "$.raw.decorations[1].gameId"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("name", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" 攻撃珠", ValueError),
        ("攻撃珠 ", ValueError),
    ],
)
def test_rejects_invalid_decoration_name(
    name: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(name=name)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].name"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_decoration_name_string_subclass() -> None:
    class Name(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(name=Name("Attack Jewel"))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].name"
    assert isinstance(exc_info.value.__cause__, TypeError)


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
def test_rejects_invalid_decoration_slot(
    slot: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(slot=slot)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].slot"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_decoration_slot_has_no_artificial_upper_bound() -> None:
    normalized = normalize_mhdb_decoration_snapshot(
        value=[raw_decoration(slot=999)],
        skill_snapshot=[raw_skill()],
    )

    assert normalized[0]["required_slot"] == {"kind": "armor", "level": 999}


@pytest.mark.parametrize(
    ("kind", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("Weapon", ValueError),
        ("body", ValueError),
        ("", ValueError),
    ],
)
def test_rejects_invalid_decoration_kind(
    kind: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(kind=kind)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].kind"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_decoration_kind_string_subclass() -> None:
    class Kind(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(kind=Kind("armor"))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].kind"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "skills",
    [(raw_decoration_skill(),), {"skill": {"id": 501}}, skills_generator(), None],
)
def test_rejects_non_list_decoration_skills(skills: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=skills)],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_decoration_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=SkillList([raw_decoration_skill()]))],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_empty_decoration_skills() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("skill_value", [None, "skill", [], ()])
def test_rejects_non_dict_decoration_skill_rank(skill_value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[skill_value])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_decoration_skill_rank_dict_subclass() -> None:
    class SkillRankDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[
                raw_decoration(
                    skills=[SkillRankDict(raw_decoration_skill())],
                )
            ],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("missing_key", ["skill", "level"])
def test_rejects_missing_decoration_skill_rank_keys(missing_key: str) -> None:
    skill_value = raw_decoration_skill()
    del skill_value[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[skill_value])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == f"$[0].skills[0].{missing_key}"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("skill_stub", [None, "skill", [], ()])
def test_rejects_non_dict_skill_stub(skill_stub: object) -> None:
    skill_value = raw_decoration_skill()
    skill_value["skill"] = skill_stub

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[skill_value])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].skill"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_skill_stub_dict_subclass() -> None:
    class SkillStubDict(dict[str, object]):
        pass

    skill_value = raw_decoration_skill()
    skill_value["skill"] = SkillStubDict({"id": 501})

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[skill_value])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].skill"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_skill_stub_id() -> None:
    skill_value = raw_decoration_skill()
    skill_value["skill"] = {"name": "missing id"}

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[skill_value])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].skill.id"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("raw_skill_id", "expected_cause"),
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
def test_rejects_invalid_skill_stub_id(
    raw_skill_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[
                raw_decoration(
                    skills=[raw_decoration_skill(raw_skill_id)],
                )
            ],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].skill.id"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_unresolved_raw_skill_id() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[raw_decoration_skill(999)])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].skill.id"
    assert "existing" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


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
def test_rejects_invalid_decoration_skill_level(
    level: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[
                raw_decoration(
                    skills=[raw_decoration_skill(level=level)],
                )
            ],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].level"
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_decoration_skill_level_above_maximum_rank() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[raw_decoration_skill(level=2)])],
            skill_snapshot=[raw_skill()],
        )

    assert exc_info.value.path == "$[0].skills[0].level"
    assert "maximum" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_weapon_decoration_with_armor_skill() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[
                raw_decoration(
                    kind="weapon",
                    skills=[raw_decoration_skill(501)],
                )
            ],
            skill_snapshot=[raw_skill(501, kind="armor")],
        )

    assert exc_info.value.path == "$[0].skills[0]"
    assert "kind" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_rejects_armor_decoration_with_weapon_skill() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[raw_decoration_skill(502)])],
            skill_snapshot=[
                raw_skill(
                    502,
                    game_id=-1002,
                    name="Weapon Skill",
                    kind="weapon",
                )
            ],
        )

    assert exc_info.value.path == "$[0].skills[0]"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("kind", ["set", "group"])
def test_rejects_set_and_group_skills(kind: str) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(skills=[raw_decoration_skill(503)])],
            skill_snapshot=[
                raw_skill(
                    503,
                    game_id=1003,
                    name="Bonus Skill",
                    kind=kind,
                    ranks=[raw_skill_rank(required_pieces=2)],
                )
            ],
        )

    assert exc_info.value.path == "$[0].skills[0]"
    assert "armor or weapon" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_duplicate_resolved_skill_ids_use_existing_decoration_invariant() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[
                raw_decoration(
                    skills=[
                        raw_decoration_skill(501, level=1),
                        raw_decoration_skill(501, level=1),
                    ]
                )
            ],
            skill_snapshot=[raw_skill()],
            path="$.raw.decorations",
        )

    assert exc_info.value.path == "$.raw.decorations[0]"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_custom_paths_are_preserved() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_decoration_snapshot(
            value=[raw_decoration(slot=0)],
            skill_snapshot=[raw_skill()],
            path="$.raw.decorations",
            skill_path="$.raw.skills",
        )

    assert exc_info.value.path == "$.raw.decorations[0].slot"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_normalizer_functions_require_keyword_arguments() -> None:
    normalize_signature = inspect.signature(normalize_mhdb_decoration_snapshot)
    build_signature = inspect.signature(build_skill_and_decoration_catalog_document)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in normalize_signature.parameters.values()
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in build_signature.parameters.values()
    )
    assert normalize_signature.parameters["path"].default == "$"
    assert normalize_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["skill_path"].default == "$.skills"
    assert build_signature.parameters["decoration_path"].default == "$.decorations"

    with pytest.raises(TypeError):
        normalize_mhdb_decoration_snapshot([], [])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        build_skill_and_decoration_catalog_document([], [])  # type: ignore[call-arg]


def test_mhdb_decoration_normalizers_are_not_exported_from_catalog_package() -> None:
    assert not hasattr(catalog_package, "normalize_mhdb_decoration_snapshot")
    assert not hasattr(
        catalog_package,
        "build_skill_and_decoration_catalog_document",
    )
