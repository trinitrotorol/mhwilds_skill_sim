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
    decode_skill_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.mhdb_skills import (
    build_skill_only_catalog_document,
    normalize_mhdb_skill_snapshot,
)
from mhwilds_skill_sim.domain.skill import SkillKind


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"
ABSENT = object()


def load_fixture() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def raw_rank(
    level: object = 1,
    *,
    set_pieces_required: object = ABSENT,
) -> dict[str, object]:
    value: dict[str, object] = {
        "level": level,
        "description": "ignored rank field",
    }
    if set_pieces_required is not ABSENT:
        value["setPiecesRequired"] = set_pieces_required
    return value


def raw_skill(
    game_id: object = 1001,
    *,
    name: object = "攻撃力強化（テスト）",
    kind: object = "armor",
    ranks: object = ABSENT,
) -> dict[str, object]:
    if ranks is ABSENT:
        ranks = [raw_rank()]
    return {
        "gameId": game_id,
        "name": name,
        "kind": kind,
        "ranks": ranks,
        "description": "ignored skill field",
        "stub": {"ignored": True},
    }


def root_generator() -> Iterator[dict[str, object]]:
    yield raw_skill()


def rank_generator() -> Iterator[dict[str, object]]:
    yield raw_rank()


def test_fixture_normalizes_to_exact_four_skills_in_input_order() -> None:
    normalized = normalize_mhdb_skill_snapshot(value=load_fixture())

    assert normalized == [
        {
            "skill_id": "mhdb:skill:1001",
            "display_name": "攻撃力強化（テスト）",
            "kind": "armor",
            "ranks": [
                {"level": 1, "required_pieces": None},
                {"level": 2, "required_pieces": None},
                {"level": 3, "required_pieces": None},
            ],
        },
        {
            "skill_id": "mhdb:skill:-1002",
            "display_name": "武器技術（テスト）",
            "kind": "weapon",
            "ranks": [{"level": 1, "required_pieces": None}],
        },
        {
            "skill_id": "mhdb:skill:1003",
            "display_name": "シリーズボーナス（テスト）",
            "kind": "set",
            "ranks": [
                {"level": 1, "required_pieces": 2},
                {"level": 2, "required_pieces": 4},
            ],
        },
        {
            "skill_id": "mhdb:skill:1004",
            "display_name": "グループボーナス（テスト）",
            "kind": "group",
            "ranks": [{"level": 1, "required_pieces": 3}],
        },
    ]


def test_fixture_output_has_exact_nested_key_order_and_no_upstream_extras() -> None:
    normalized = normalize_mhdb_skill_snapshot(value=load_fixture())

    for skill in normalized:
        assert list(skill) == ["skill_id", "display_name", "kind", "ranks"]
        assert "gameId" not in skill
        assert "description" not in skill
        assert "icon" not in skill
        assert "stub" not in skill
        for rank in skill["ranks"]:  # type: ignore[union-attr]
            assert list(rank) == ["level", "required_pieces"]
            assert "setPiecesRequired" not in rank
            assert "description" not in rank


def test_fixture_preserves_all_kinds_names_thresholds_and_negative_id() -> None:
    normalized = normalize_mhdb_skill_snapshot(value=load_fixture())

    assert [skill["skill_id"] for skill in normalized] == [
        "mhdb:skill:1001",
        "mhdb:skill:-1002",
        "mhdb:skill:1003",
        "mhdb:skill:1004",
    ]
    assert [skill["display_name"] for skill in normalized] == [
        "攻撃力強化（テスト）",
        "武器技術（テスト）",
        "シリーズボーナス（テスト）",
        "グループボーナス（テスト）",
    ]
    assert [skill["kind"] for skill in normalized] == [
        "armor",
        "weapon",
        "set",
        "group",
    ]
    assert normalized[2]["ranks"] == [
        {"level": 1, "required_pieces": 2},
        {"level": 2, "required_pieces": 4},
    ]
    assert normalized[3]["ranks"] == [{"level": 1, "required_pieces": 3}]


def test_every_normalized_fixture_skill_passes_existing_decoder() -> None:
    normalized = normalize_mhdb_skill_snapshot(value=load_fixture())

    decoded = [
        decode_skill_definition(value=skill, path=f"$.skills[{index}]")
        for index, skill in enumerate(normalized)
    ]

    assert [skill.kind for skill in decoded] == [
        SkillKind.ARMOR,
        SkillKind.WEAPON,
        SkillKind.SERIES,
        SkillKind.GROUP,
    ]
    assert [skill.display_name for skill in decoded] == [
        "攻撃力強化（テスト）",
        "武器技術（テスト）",
        "シリーズボーナス（テスト）",
        "グループボーナス（テスト）",
    ]


def test_normalized_fixture_output_is_json_serializable_without_ascii_escaping() -> (
    None
):
    normalized = normalize_mhdb_skill_snapshot(value=load_fixture())

    encoded = json.dumps(normalized, ensure_ascii=False)

    assert "攻撃力強化（テスト）" in encoded
    assert "\\u653b" not in encoded


def test_build_skill_only_catalog_document_has_exact_shape_and_decodes() -> None:
    document = build_skill_only_catalog_document(value=load_fixture())

    assert list(document) == [
        "schema_version",
        "skills",
        "equipment",
        "decorations",
    ]
    assert document["schema_version"] == 1
    assert len(document["skills"]) == 4  # type: ignore[arg-type]
    assert document["equipment"] == []
    assert document["decorations"] == []
    assert "appraisal_charm_skill_groups" not in document
    assert "appraisal_charm_patterns" not in document

    decoded = decode_catalog(value=document)
    assert len(decoded.skills) == 4
    assert decoded.equipment == ()
    assert decoded.decorations == ()


def test_empty_snapshot_and_document_are_valid() -> None:
    assert normalize_mhdb_skill_snapshot(value=[]) == []
    assert build_skill_only_catalog_document(value=[]) == {
        "schema_version": 1,
        "skills": [],
        "equipment": [],
        "decorations": [],
    }


def test_normalization_does_not_mutate_input() -> None:
    raw = load_fixture()
    before = copy.deepcopy(raw)

    normalize_mhdb_skill_snapshot(value=raw)
    build_skill_only_catalog_document(value=raw)

    assert raw == before


def test_repeated_calls_return_independent_nested_containers() -> None:
    raw = load_fixture()
    first = build_skill_only_catalog_document(value=raw)
    second = build_skill_only_catalog_document(value=raw)

    assert first == second
    assert first is not second
    assert first["skills"] is not second["skills"]
    assert first["equipment"] is not second["equipment"]
    assert first["decorations"] is not second["decorations"]
    assert first["skills"][0] is not second["skills"][0]  # type: ignore[index]
    assert first["skills"][0]["ranks"] is not second["skills"][0]["ranks"]  # type: ignore[index]
    assert first["skills"][0]["ranks"][0] is not second["skills"][0]["ranks"][0]  # type: ignore[index]

    first["skills"][0]["display_name"] = "changed"  # type: ignore[index]
    first["skills"][0]["ranks"][0]["level"] = 999  # type: ignore[index]
    assert second == build_skill_only_catalog_document(value=raw)


@pytest.mark.parametrize("value", [None, {}, (), "skills", root_generator()])
def test_rejects_non_list_root(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=value, path="$.snapshot")

    assert exc_info.value.path == "$.snapshot"
    assert "list" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_root_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=SkillList([raw_skill()]),
            path="$.snapshot",
        )

    assert exc_info.value.path == "$.snapshot"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("value", [None, "skill", [], ()])
def test_rejects_non_dict_raw_skill(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[value])

    assert exc_info.value.path == "$[0]"
    assert "object" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_raw_skill_dict_subclass() -> None:
    class SkillDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[SkillDict(raw_skill())])

    assert exc_info.value.path == "$[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize("missing_key", ["gameId", "name", "kind", "ranks"])
def test_rejects_missing_raw_skill_keys(missing_key: str) -> None:
    value = raw_skill()
    del value[missing_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[value])

    assert exc_info.value.path == f"$[0].{missing_key}"
    assert missing_key in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("game_id", [True, False, 1.5, "1001", None])
def test_rejects_non_exact_int_game_id(game_id: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(game_id)])

    assert exc_info.value.path == "$[0].gameId"
    assert "gameId" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_duplicate_game_id_at_duplicate_item_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[
                raw_skill(1001),
                raw_skill(1001, name="Duplicate Name"),
            ],
            path="$.snapshot",
        )

    assert exc_info.value.path == "$.snapshot[1].gameId"
    assert "gameId" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("name", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" 攻撃力強化", ValueError),
        ("攻撃力強化 ", ValueError),
    ],
)
def test_rejects_invalid_name(
    name: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(name=name)])

    assert exc_info.value.path == "$[0].name"
    assert "name" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_name_string_subclass() -> None:
    class Name(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(name=Name("Attack"))])

    assert exc_info.value.path == "$[0].name"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    ("kind", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (None, TypeError),
        ("Armor", ValueError),
        ("series", ValueError),
        ("normal", ValueError),
        ("", ValueError),
    ],
)
def test_rejects_invalid_kind(
    kind: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(kind=kind)])

    assert exc_info.value.path == "$[0].kind"
    assert "kind" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_rejects_kind_string_subclass() -> None:
    class Kind(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(kind=Kind("armor"))])

    assert exc_info.value.path == "$[0].kind"
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "ranks",
    [(raw_rank(),), {"level": 1}, rank_generator(), None],
)
def test_rejects_non_list_ranks(ranks: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(ranks=ranks)])

    assert exc_info.value.path == "$[0].ranks"
    assert "ranks" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_ranks_list_subclass() -> None:
    class RankList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(ranks=RankList([raw_rank()]))])

    assert exc_info.value.path == "$[0].ranks"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_empty_ranks() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(ranks=[])])

    assert exc_info.value.path == "$[0].ranks"
    assert "empty" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("rank_value", [None, "rank", [], ()])
def test_rejects_non_dict_rank(rank_value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(ranks=[raw_rank(), rank_value])])

    assert exc_info.value.path == "$[0].ranks[1]"
    assert "object" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_rank_dict_subclass() -> None:
    class RankDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(ranks=[RankDict(raw_rank())])])

    assert exc_info.value.path == "$[0].ranks[0]"
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_rejects_missing_rank_level() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[raw_skill(ranks=[{"description": "missing"}])]
        )

    assert exc_info.value.path == "$[0].ranks[0].level"
    assert "level" in exc_info.value.detail
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
def test_rejects_invalid_rank_level(
    level: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[raw_skill(ranks=[raw_rank(level)])],
            path="$.snapshot",
        )

    assert exc_info.value.path == "$.snapshot[0].ranks[0].level"
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    ("levels", "expected_raw_index"),
    [
        ([1, 1], 1),
        ([1, 3], 1),
        ([2], 0),
        ([3, 1], 0),
    ],
)
def test_rejects_duplicate_missing_or_noncontiguous_rank_levels(
    levels: list[int],
    expected_raw_index: int,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[raw_skill(ranks=[raw_rank(level) for level in levels])]
        )

    assert exc_info.value.path == f"$[0].ranks[{expected_raw_index}].level"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("kind", ["armor", "weapon"])
@pytest.mark.parametrize("set_pieces_required", [True, 1, 0, "1", {}])
def test_normal_skills_reject_non_null_set_pieces_required(
    kind: str,
    set_pieces_required: object,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[
                raw_skill(
                    kind=kind,
                    ranks=[
                        raw_rank(set_pieces_required=set_pieces_required),
                    ],
                )
            ]
        )

    assert exc_info.value.path == "$[0].ranks[0].setPiecesRequired"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("kind", ["armor", "weapon"])
def test_normal_skills_accept_absent_and_null_set_pieces_required(kind: str) -> None:
    normalized = normalize_mhdb_skill_snapshot(
        value=[
            raw_skill(
                kind=kind,
                ranks=[
                    raw_rank(),
                    raw_rank(2, set_pieces_required=None),
                ],
            )
        ]
    )

    assert normalized[0]["ranks"] == [
        {"level": 1, "required_pieces": None},
        {"level": 2, "required_pieces": None},
    ]


@pytest.mark.parametrize("kind", ["set", "group"])
def test_piece_skills_reject_missing_set_pieces_required(kind: str) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(kind=kind, ranks=[raw_rank()])])

    assert exc_info.value.path == "$[0].ranks[0].setPiecesRequired"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("kind", ["set", "group"])
@pytest.mark.parametrize(
    ("set_pieces_required", "expected_cause"),
    [
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_piece_skills_reject_invalid_set_pieces_required(
    kind: str,
    set_pieces_required: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[
                raw_skill(
                    kind=kind,
                    ranks=[
                        raw_rank(set_pieces_required=set_pieces_required),
                    ],
                )
            ]
        )

    assert exc_info.value.path == "$[0].ranks[0].setPiecesRequired"
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize("kind", ["set", "group"])
@pytest.mark.parametrize(
    ("thresholds", "expected_raw_index"),
    [
        ([2, 2], 1),
        ([4, 2], 1),
        ([2, 4, 3], 2),
    ],
)
def test_piece_skill_thresholds_must_strictly_increase_after_level_sorting(
    kind: str,
    thresholds: list[int],
    expected_raw_index: int,
) -> None:
    ranks = [
        raw_rank(level, set_pieces_required=threshold)
        for level, threshold in enumerate(thresholds, start=1)
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(value=[raw_skill(kind=kind, ranks=ranks)])

    assert exc_info.value.path == f"$[0].ranks[{expected_raw_index}].setPiecesRequired"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_custom_path_is_preserved_for_nested_errors() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_skill_snapshot(
            value=[raw_skill(ranks=[raw_rank(0)])],
            path="$.mhdb.skills",
        )

    assert exc_info.value.path == "$.mhdb.skills[0].ranks[0].level"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_normalizer_functions_require_keyword_arguments() -> None:
    for function in (
        normalize_mhdb_skill_snapshot,
        build_skill_only_catalog_document,
    ):
        signature = inspect.signature(function)
        assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        normalize_mhdb_skill_snapshot([])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        build_skill_only_catalog_document([])  # type: ignore[call-arg]


def test_mhdb_normalizers_are_not_exported_from_catalog_package() -> None:
    assert not hasattr(catalog_package, "normalize_mhdb_skill_snapshot")
    assert not hasattr(catalog_package, "build_skill_only_catalog_document")
