from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

import mhwilds_skill_sim.catalog as catalog_package
from mhwilds_skill_sim.catalog.appraisal_rule_import import (
    build_catalog_document_with_appraisal_charm_rules,
    normalize_appraisal_charm_rule_snapshot,
)
from mhwilds_skill_sim.catalog.decoder import (
    decode_appraisal_charm_pattern_definition,
    decode_appraisal_charm_skill_group_definition,
    decode_catalog,
    decode_skill_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.mhdb_charms import (
    build_skill_weapon_armor_charm_and_decoration_catalog_document,
)
from mhwilds_skill_sim.catalog.mhdb_skills import normalize_mhdb_skill_snapshot
from mhwilds_skill_sim.domain.equipment import EquipmentPart, WeaponKind
from mhwilds_skill_sim.domain.skill import (
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIRECTORY = ROOT / "data" / "fixtures"
RULE_FIXTURE_PATH = FIXTURE_DIRECTORY / "appraisal_rules_raw.json"
SKILL_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_skills_raw.json"
WEAPON_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_weapons_raw.json"
ARMOR_SET_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_armor_sets_raw.json"
ARMOR_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_armor_raw.json"
CHARM_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_charms_raw.json"
DECORATION_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_decorations_raw.json"
ABSENT = object()


class TupleSubclass(tuple[object, ...]):
    pass


class DictSubclass(dict[object, object]):
    pass


class ListSubclass(list[object]):
    pass


class StringSubclass(str):
    pass


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rule_fixture() -> dict[str, object]:
    return load_json(RULE_FIXTURE_PATH)  # type: ignore[return-value]


def load_skill_fixture() -> list[dict[str, object]]:
    return load_json(SKILL_FIXTURE_PATH)  # type: ignore[return-value]


def normalized_skill_definitions() -> tuple[SkillDefinition, ...]:
    normalized = normalize_mhdb_skill_snapshot(value=load_skill_fixture())
    return tuple(
        decode_skill_definition(value=skill, path=f"$.skills[{index}]")
        for index, skill in enumerate(normalized)
    )


def skill_definition(
    skill_id: str,
    *,
    display_name: str | None,
    kind: SkillKind = SkillKind.ARMOR,
    maximum_level: int = 3,
) -> SkillDefinition:
    required_piece_offset = 1 if kind in (SkillKind.SERIES, SkillKind.GROUP) else 0
    return SkillDefinition(
        skill_id=skill_id,
        display_name=display_name,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(
                level=level,
                required_pieces=(
                    level + required_piece_offset
                    if kind in (SkillKind.SERIES, SkillKind.GROUP)
                    else None
                ),
            )
            for level in range(1, maximum_level + 1)
        ),
    )


def simple_rule(
    *,
    group_id: object = "A",
    display_name: object = "攻撃力強化（テスト）",
    level: object = 1,
    rarity_key: object = "8",
    slots: object = ABSENT,
    skill_patterns: object = ABSENT,
) -> dict[str, object]:
    if slots is ABSENT:
        slots = ["[1]ーー"]
    if skill_patterns is ABSENT:
        skill_patterns = [["A"]]
    return {
        "groups": {group_id: {display_name: level}},
        "rarity_patterns": {
            rarity_key: [
                {
                    "slots": slots,
                    "skill_patterns": skill_patterns,
                }
            ]
        },
    }


def base_catalog_document() -> dict[str, object]:
    return build_skill_weapon_armor_charm_and_decoration_catalog_document(
        skill_value=load_skill_fixture(),
        weapon_value=load_json(WEAPON_FIXTURE_PATH),
        armor_set_value=load_json(ARMOR_SET_FIXTURE_PATH),
        armor_value=load_json(ARMOR_FIXTURE_PATH),
        charm_value=load_json(CHARM_FIXTURE_PATH),
        decoration_value=load_json(DECORATION_FIXTURE_PATH),
    )


def expect_rule_error(
    value: object,
    *,
    expected_path: str,
    expected_cause: type[Exception],
    skill_definitions: tuple[SkillDefinition, ...] | None = None,
    detail: str | None = None,
) -> CatalogDecodeError:
    if skill_definitions is None:
        skill_definitions = normalized_skill_definitions()
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_appraisal_charm_rule_snapshot(
            value=value,
            skill_definitions=skill_definitions,
        )

    error = exc_info.value
    assert error.path == expected_path
    assert isinstance(error.__cause__, expected_cause)
    if detail is not None:
        assert detail in error.detail
    return error


def test_fixture_normalizes_exact_groups_and_atomic_patterns() -> None:
    normalized = normalize_appraisal_charm_rule_snapshot(
        value=load_rule_fixture(),
        skill_definitions=normalized_skill_definitions(),
    )

    assert list(normalized) == [
        "appraisal_charm_skill_groups",
        "appraisal_charm_patterns",
    ]
    assert normalized["appraisal_charm_skill_groups"] == [
        {
            "group_id": "imported:appraisal-group:A",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 1}],
        },
        {
            "group_id": "imported:appraisal-group:B",
            "skills": [
                {"skill_id": "mhdb:skill:1001", "level": 2},
                {"skill_id": "mhdb:skill:-1002", "level": 1},
            ],
        },
        {
            "group_id": "imported:appraisal-group:J",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 3}],
        },
    ]
    patterns = normalized["appraisal_charm_patterns"]
    assert len(patterns) == 10
    assert [pattern["pattern_id"] for pattern in patterns] == [
        "imported:appraisal-pattern:rarity-7:block-1:skills-1:slots-1",
        "imported:appraisal-pattern:rarity-8:block-1:skills-1:slots-1",
        "imported:appraisal-pattern:rarity-8:block-1:skills-1:slots-2",
        "imported:appraisal-pattern:rarity-8:block-1:skills-1:slots-3",
        "imported:appraisal-pattern:rarity-8:block-1:skills-2:slots-1",
        "imported:appraisal-pattern:rarity-8:block-1:skills-2:slots-2",
        "imported:appraisal-pattern:rarity-8:block-1:skills-2:slots-3",
        "imported:appraisal-pattern:rarity-8:block-1:skills-3:slots-1",
        "imported:appraisal-pattern:rarity-8:block-1:skills-3:slots-2",
        "imported:appraisal-pattern:rarity-8:block-1:skills-3:slots-3",
    ]
    assert [pattern["rarity"] for pattern in patterns] == [7, *([8] * 9)]
    assert patterns[0]["slots"] == [{"kind": "armor", "level": 2}]
    assert patterns[1]["slots"] == [{"kind": "weapon", "level": 1}]
    assert patterns[2]["slots"] == [
        {"kind": "weapon", "level": 1},
        {"kind": "armor", "level": 1},
    ]
    assert patterns[3]["slots"] == [
        {"kind": "weapon", "level": 1},
        {"kind": "armor", "level": 1},
        {"kind": "armor", "level": 1},
    ]
    assert patterns[-1]["skill_group_ids"] == [
        "imported:appraisal-group:A",
        "imported:appraisal-group:A",
        "imported:appraisal-group:A",
    ]


def test_normalized_rule_has_exact_nested_key_order_and_decodes() -> None:
    normalized = normalize_appraisal_charm_rule_snapshot(
        value=load_rule_fixture(),
        skill_definitions=normalized_skill_definitions(),
    )

    for index, group in enumerate(normalized["appraisal_charm_skill_groups"]):
        assert list(group) == ["group_id", "skills"]
        assert all(list(skill) == ["skill_id", "level"] for skill in group["skills"])
        decode_appraisal_charm_skill_group_definition(
            value=group,
            path=f"$.groups[{index}]",
        )
    for index, pattern in enumerate(normalized["appraisal_charm_patterns"]):
        assert list(pattern) == ["pattern_id", "rarity", "skill_group_ids", "slots"]
        assert all(list(slot) == ["kind", "level"] for slot in pattern["slots"])
        decode_appraisal_charm_pattern_definition(
            value=pattern,
            path=f"$.patterns[{index}]",
        )
    encoded = json.dumps(normalized, ensure_ascii=False)
    assert "imported:appraisal-group:A" in encoded
    assert "\\u" not in encoded


def test_normalization_does_not_mutate_input_and_returns_independent_containers() -> (
    None
):
    value = load_rule_fixture()
    before = copy.deepcopy(value)
    skills = normalized_skill_definitions()

    first = normalize_appraisal_charm_rule_snapshot(
        value=value,
        skill_definitions=skills,
    )
    second = normalize_appraisal_charm_rule_snapshot(
        value=value,
        skill_definitions=skills,
    )

    assert value == before
    assert first == second
    assert first is not second
    assert (
        first["appraisal_charm_skill_groups"]
        is not second["appraisal_charm_skill_groups"]
    )
    assert (
        first["appraisal_charm_skill_groups"][0]
        is not second["appraisal_charm_skill_groups"][0]
    )
    assert first["appraisal_charm_patterns"] is not second["appraisal_charm_patterns"]
    assert (
        first["appraisal_charm_patterns"][1]["slots"]
        is not second["appraisal_charm_patterns"][1]["slots"]
    )


def test_normalizer_requires_keyword_arguments_and_defaults() -> None:
    signature = inspect.signature(normalize_appraisal_charm_rule_snapshot)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert signature.parameters["path"].default == "$.appraisal_rules"
    with pytest.raises(TypeError):
        normalize_appraisal_charm_rule_snapshot(  # type: ignore[call-arg]
            load_rule_fixture(), normalized_skill_definitions()
        )


@pytest.mark.parametrize(
    "skill_definitions",
    [None, [], {}, "skills", iter(())],
)
def test_rejects_non_tuple_skill_definitions(skill_definitions: object) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        normalize_appraisal_charm_rule_snapshot(
            value=load_rule_fixture(),
            skill_definitions=skill_definitions,  # type: ignore[arg-type]
        )


def test_rejects_tuple_subclass_and_invalid_element() -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        normalize_appraisal_charm_rule_snapshot(
            value=load_rule_fixture(),
            skill_definitions=TupleSubclass(normalized_skill_definitions()),
        )
    with pytest.raises(TypeError, match=r"skill_definitions\[1\]"):
        normalize_appraisal_charm_rule_snapshot(
            value=load_rule_fixture(),
            skill_definitions=(normalized_skill_definitions()[0], object()),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_skill_definition_id() -> None:
    skill = normalized_skill_definitions()[0]

    with pytest.raises(ValueError, match="skill_definitions.*duplicate.*skill_id"):
        normalize_appraisal_charm_rule_snapshot(
            value=load_rule_fixture(),
            skill_definitions=(skill, skill),
        )


def test_unknown_none_series_and_group_display_names_are_not_resolved() -> None:
    unnamed = skill_definition("skill:unnamed", display_name=None)
    series = skill_definition(
        "skill:series",
        display_name="シリーズ名",
        kind=SkillKind.SERIES,
    )
    group = skill_definition(
        "skill:group",
        display_name="グループ名",
        kind=SkillKind.GROUP,
    )
    skills = (*normalized_skill_definitions(), unnamed, series, group)

    for display_name in ("不明スキル", "シリーズ名", "グループ名"):
        expect_rule_error(
            simple_rule(display_name=display_name),
            skill_definitions=skills,
            expected_path=f"$.appraisal_rules.groups.A.{display_name}",
            expected_cause=ValueError,
            detail=display_name,
        )


def test_rejects_ambiguous_eligible_display_name() -> None:
    skills = (
        skill_definition("skill:first", display_name="同名スキル"),
        skill_definition(
            "skill:second",
            display_name="同名スキル",
            kind=SkillKind.WEAPON,
        ),
    )

    with pytest.raises(ValueError, match="skill_definitions.*同名スキル"):
        normalize_appraisal_charm_rule_snapshot(
            value=simple_rule(display_name="同名スキル"),
            skill_definitions=skills,
        )


@pytest.mark.parametrize(
    ("level", "cause"),
    [
        (True, TypeError),
        (False, TypeError),
        (None, TypeError),
        (1.0, TypeError),
        ("1", TypeError),
        (0, ValueError),
        (-1, ValueError),
        (4, ValueError),
    ],
)
def test_rejects_invalid_or_excessive_skill_level(
    level: object,
    cause: type[Exception],
) -> None:
    expect_rule_error(
        simple_rule(level=level),
        expected_path="$.appraisal_rules.groups.A.攻撃力強化（テスト）",
        expected_cause=cause,
    )


@pytest.mark.parametrize("value", [None, [], (), "rules"])
def test_rejects_non_dict_rule_root(value: object) -> None:
    expect_rule_error(
        value,
        expected_path="$.appraisal_rules",
        expected_cause=TypeError,
    )


def test_rejects_rule_root_dict_subclass() -> None:
    expect_rule_error(
        DictSubclass(load_rule_fixture()),
        expected_path="$.appraisal_rules",
        expected_cause=TypeError,
    )


def test_reports_missing_and_extra_root_keys_together_deterministically() -> None:
    value: dict[object, object] = {
        "z_extra": None,
        "a_extra": None,
    }

    error = expect_rule_error(
        value,
        expected_path="$.appraisal_rules",
        expected_cause=ValueError,
    )

    assert error.detail == (
        "missing keys: groups, rarity_patterns; unexpected keys: a_extra, z_extra"
    )


@pytest.mark.parametrize("groups", [None, [], (), "groups", DictSubclass()])
def test_rejects_non_exact_groups_object(groups: object) -> None:
    value = load_rule_fixture()
    value["groups"] = groups

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.groups",
        expected_cause=TypeError,
    )


def test_rejects_empty_groups_object() -> None:
    value = load_rule_fixture()
    value["groups"] = {}

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.groups",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("group_id", "cause"),
    [
        (1, TypeError),
        (StringSubclass("A"), TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" A", ValueError),
        ("A ", ValueError),
    ],
)
def test_rejects_invalid_group_id(
    group_id: object,
    cause: type[Exception],
) -> None:
    path = (
        f"$.appraisal_rules.groups.{group_id}"
        if type(group_id) is str
        else f"$.appraisal_rules.groups[{group_id!r}]"
    )
    expect_rule_error(
        simple_rule(group_id=group_id),
        expected_path=path,
        expected_cause=cause,
    )


@pytest.mark.parametrize("group", [None, [], (), "group", DictSubclass()])
def test_rejects_non_exact_group_contents(group: object) -> None:
    value = load_rule_fixture()
    value["groups"] = {"A": group}

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.groups.A",
        expected_cause=TypeError,
    )


def test_rejects_empty_group_contents() -> None:
    value = load_rule_fixture()
    value["groups"] = {"A": {}}

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.groups.A",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("display_name", "cause"),
    [
        (1, TypeError),
        (StringSubclass("攻撃力強化（テスト）"), TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" 攻撃力強化（テスト）", ValueError),
        ("攻撃力強化（テスト） ", ValueError),
    ],
)
def test_rejects_invalid_skill_display_name_key(
    display_name: object,
    cause: type[Exception],
) -> None:
    path = (
        f"$.appraisal_rules.groups.A.{display_name}"
        if type(display_name) is str
        else f"$.appraisal_rules.groups.A[{display_name!r}]"
    )
    expect_rule_error(
        simple_rule(display_name=display_name),
        expected_path=path,
        expected_cause=cause,
    )


@pytest.mark.parametrize(
    "rarity_patterns",
    [None, [], (), "patterns", DictSubclass()],
)
def test_rejects_non_exact_rarity_patterns_object(rarity_patterns: object) -> None:
    value = load_rule_fixture()
    value["rarity_patterns"] = rarity_patterns

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.rarity_patterns",
        expected_cause=TypeError,
    )


def test_empty_rarity_patterns_are_allowed() -> None:
    value = load_rule_fixture()
    value["rarity_patterns"] = {}

    normalized = normalize_appraisal_charm_rule_snapshot(
        value=value,
        skill_definitions=normalized_skill_definitions(),
    )

    assert normalized["appraisal_charm_patterns"] == []


@pytest.mark.parametrize(
    ("rarity_key", "cause"),
    [
        (8, TypeError),
        (StringSubclass("8"), TypeError),
        ("", ValueError),
        ("0", ValueError),
        ("-1", ValueError),
        ("05", ValueError),
        ("8.0", ValueError),
        ("８", ValueError),
        (" 8", ValueError),
        ("8 ", ValueError),
    ],
)
def test_rejects_invalid_rarity_key(
    rarity_key: object,
    cause: type[Exception],
) -> None:
    path = (
        f"$.appraisal_rules.rarity_patterns.{rarity_key}"
        if type(rarity_key) is str
        else f"$.appraisal_rules.rarity_patterns[{rarity_key!r}]"
    )
    expect_rule_error(
        simple_rule(rarity_key=rarity_key),
        expected_path=path,
        expected_cause=cause,
    )


def test_rarities_are_sorted_numerically_independent_of_input_order() -> None:
    block = {"slots": ["①ーー"], "skill_patterns": [["A"]]}
    value = {
        "groups": {"A": {"攻撃力強化（テスト）": 1}},
        "rarity_patterns": {
            "12": [copy.deepcopy(block)],
            "8": [copy.deepcopy(block)],
            "5": [copy.deepcopy(block)],
        },
    }

    normalized = normalize_appraisal_charm_rule_snapshot(
        value=value,
        skill_definitions=normalized_skill_definitions(),
    )

    assert [
        pattern["rarity"] for pattern in normalized["appraisal_charm_patterns"]
    ] == [
        5,
        8,
        12,
    ]


@pytest.mark.parametrize("blocks", [None, {}, (), "blocks", ListSubclass()])
def test_rejects_non_exact_rarity_block_list(blocks: object) -> None:
    value = simple_rule()
    value["rarity_patterns"] = {"8": blocks}

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.rarity_patterns.8",
        expected_cause=TypeError,
    )


def test_empty_rarity_block_list_is_allowed() -> None:
    value = simple_rule()
    value["rarity_patterns"] = {"8": []}

    normalized = normalize_appraisal_charm_rule_snapshot(
        value=value,
        skill_definitions=normalized_skill_definitions(),
    )

    assert normalized["appraisal_charm_patterns"] == []


@pytest.mark.parametrize("block", [None, [], (), "block", DictSubclass()])
def test_rejects_non_exact_pattern_block(block: object) -> None:
    value = simple_rule()
    value["rarity_patterns"] = {"8": [block]}

    expect_rule_error(
        value,
        expected_path="$.appraisal_rules.rarity_patterns.8[0]",
        expected_cause=TypeError,
    )


def test_rejects_missing_and_extra_pattern_block_keys() -> None:
    value = simple_rule()
    value["rarity_patterns"] = {"8": [{"future": None}]}

    error = expect_rule_error(
        value,
        expected_path="$.appraisal_rules.rarity_patterns.8[0]",
        expected_cause=ValueError,
    )

    assert error.detail == (
        "missing keys: slots, skill_patterns; unexpected keys: future"
    )


@pytest.mark.parametrize("slots", [None, {}, (), "slots", ListSubclass()])
def test_rejects_non_exact_slots_list(slots: object) -> None:
    expect_rule_error(
        simple_rule(slots=slots),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].slots",
        expected_cause=TypeError,
    )


def test_rejects_empty_slots_list() -> None:
    expect_rule_error(
        simple_rule(slots=[]),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].slots",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("slot", [None, 1, StringSubclass("①ーー")])
def test_rejects_non_exact_slot_string(slot: object) -> None:
    expect_rule_error(
        simple_rule(slots=[slot]),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].slots[0]",
        expected_cause=TypeError,
    )


@pytest.mark.parametrize(
    "skill_patterns",
    [None, {}, (), "patterns", ListSubclass()],
)
def test_rejects_non_exact_skill_patterns_list(skill_patterns: object) -> None:
    expect_rule_error(
        simple_rule(skill_patterns=skill_patterns),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].skill_patterns",
        expected_cause=TypeError,
    )


def test_rejects_empty_skill_patterns_list() -> None:
    expect_rule_error(
        simple_rule(skill_patterns=[]),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].skill_patterns",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize("pattern", [None, {}, (), "A", ListSubclass(["A"])])
def test_rejects_non_exact_skill_pattern(pattern: object) -> None:
    expect_rule_error(
        simple_rule(skill_patterns=[pattern]),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].skill_patterns[0]",
        expected_cause=TypeError,
    )


@pytest.mark.parametrize("pattern", [[], ["A"] * 4])
def test_rejects_skill_pattern_outside_one_to_three_ids(pattern: list[str]) -> None:
    expect_rule_error(
        simple_rule(skill_patterns=[pattern]),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].skill_patterns[0]",
        expected_cause=ValueError,
    )


@pytest.mark.parametrize(
    ("group_id", "cause"),
    [
        (1, TypeError),
        (StringSubclass("A"), TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" A", ValueError),
        ("A ", ValueError),
        ("Z", ValueError),
    ],
)
def test_rejects_invalid_or_unknown_skill_pattern_group_id(
    group_id: object,
    cause: type[Exception],
) -> None:
    expect_rule_error(
        simple_rule(skill_patterns=[["A", group_id]]),
        expected_path=("$.appraisal_rules.rarity_patterns.8[0].skill_patterns[0][1]"),
        expected_cause=cause,
    )


def test_repeated_skill_pattern_group_ids_are_accepted() -> None:
    normalized = normalize_appraisal_charm_rule_snapshot(
        value=simple_rule(skill_patterns=[["A", "A", "A"]]),
        skill_definitions=normalized_skill_definitions(),
    )

    assert normalized["appraisal_charm_patterns"][0]["skill_group_ids"] == [
        "imported:appraisal-group:A",
        "imported:appraisal-group:A",
        "imported:appraisal-group:A",
    ]


def test_slot_parser_accepts_all_armor_symbols_and_valid_forms() -> None:
    slots = ["①ーー", "②①ー", "③ーー", "④③②", "ーーー"]
    normalized = normalize_appraisal_charm_rule_snapshot(
        value=simple_rule(slots=slots),
        skill_definitions=normalized_skill_definitions(),
    )

    assert [pattern["slots"] for pattern in normalized["appraisal_charm_patterns"]] == [
        [{"kind": "armor", "level": 1}],
        [
            {"kind": "armor", "level": 2},
            {"kind": "armor", "level": 1},
        ],
        [{"kind": "armor", "level": 3}],
        [
            {"kind": "armor", "level": 4},
            {"kind": "armor", "level": 3},
            {"kind": "armor", "level": 2},
        ],
        [],
    ]


def test_slot_parser_accepts_weapon_only_and_weapon_plus_armor_forms() -> None:
    slots = ["[1]ーー", "[1]①ー", "[1]①①", "[2]②ー", "[12]④③"]
    normalized = normalize_appraisal_charm_rule_snapshot(
        value=simple_rule(slots=slots),
        skill_definitions=normalized_skill_definitions(),
    )

    assert [pattern["slots"] for pattern in normalized["appraisal_charm_patterns"]] == [
        [{"kind": "weapon", "level": 1}],
        [
            {"kind": "weapon", "level": 1},
            {"kind": "armor", "level": 1},
        ],
        [
            {"kind": "weapon", "level": 1},
            {"kind": "armor", "level": 1},
            {"kind": "armor", "level": 1},
        ],
        [
            {"kind": "weapon", "level": 2},
            {"kind": "armor", "level": 2},
        ],
        [
            {"kind": "weapon", "level": 12},
            {"kind": "armor", "level": 4},
            {"kind": "armor", "level": 3},
        ],
    ]


@pytest.mark.parametrize(
    "slot",
    [
        "[0]ーー",
        "[01]ーー",
        "[-1]ーー",
        "[x]ーー",
        "[]ーー",
        "[1ーー",
        "1]ーー",
        "[[1]ーー",
        "[1]ー",
        "[1]ーーー",
        "①ー",
        "①ーーー",
        "①xー",
        "⑤ーー",
        "①ー①",
        "[1]ー①",
    ],
)
def test_slot_parser_rejects_malformed_notation_with_precise_path(slot: str) -> None:
    expect_rule_error(
        simple_rule(slots=[slot]),
        expected_path="$.appraisal_rules.rarity_patterns.8[0].slots[0]",
        expected_cause=ValueError,
        detail=slot,
    )


def test_catalog_merge_preserves_fixed_data_and_adds_rules() -> None:
    merged = build_catalog_document_with_appraisal_charm_rules(
        catalog_value=base_catalog_document(),
        rule_value=load_rule_fixture(),
    )

    assert list(merged) == [
        "schema_version",
        "skills",
        "appraisal_charm_skill_groups",
        "appraisal_charm_patterns",
        "equipment",
        "decorations",
    ]
    catalog = decode_catalog(value=merged)
    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 12
    assert len(catalog.decorations) == 3
    assert len(catalog.appraisal_charm_skill_groups) == 3
    assert len(catalog.appraisal_charm_patterns) == 10
    assert all(
        equipment.part is EquipmentPart.WEAPON for equipment in catalog.equipment[:3]
    )
    assert all(
        equipment.part not in (EquipmentPart.WEAPON, EquipmentPart.CHARM)
        for equipment in catalog.equipment[3:9]
    )
    assert all(
        equipment.part is EquipmentPart.CHARM for equipment in catalog.equipment[9:]
    )
    assert catalog.equipment[1].weapon_kind is WeaponKind.GREAT_SWORD
    assert catalog.equipment[1].allows_series_skill_assignment is True
    assert catalog.equipment[1].allows_group_skill_assignment is True


def test_merged_catalog_can_be_written_and_loaded(tmp_path: Path) -> None:
    merged = build_catalog_document_with_appraisal_charm_rules(
        catalog_value=base_catalog_document(),
        rule_value=load_rule_fixture(),
    )
    output = tmp_path / "catalog.json"
    output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = load_catalog(path=output)

    assert len(loaded.skills) == 4
    assert len(loaded.equipment) == 12
    assert len(loaded.decorations) == 3
    assert len(loaded.appraisal_charm_skill_groups) == 3
    assert len(loaded.appraisal_charm_patterns) == 10


@pytest.mark.parametrize("include_empty_keys", [False, True])
def test_catalog_merge_accepts_absent_or_both_empty_appraisal_keys(
    include_empty_keys: bool,
) -> None:
    source = base_catalog_document()
    if include_empty_keys:
        source["appraisal_charm_skill_groups"] = []
        source["appraisal_charm_patterns"] = []

    merged = build_catalog_document_with_appraisal_charm_rules(
        catalog_value=source,
        rule_value=load_rule_fixture(),
    )

    assert len(merged["appraisal_charm_skill_groups"]) == 3
    assert len(merged["appraisal_charm_patterns"]) == 10


def test_catalog_merge_rejects_only_one_appraisal_key() -> None:
    source = base_catalog_document()
    source["appraisal_charm_skill_groups"] = []

    with pytest.raises(CatalogDecodeError) as exc_info:
        build_catalog_document_with_appraisal_charm_rules(
            catalog_value=source,
            rule_value=load_rule_fixture(),
        )

    assert exc_info.value.path == "$.catalog"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("field", ["groups", "patterns"])
def test_catalog_merge_rejects_existing_nonempty_appraisal_rules(field: str) -> None:
    source = base_catalog_document()
    rules = normalize_appraisal_charm_rule_snapshot(
        value=load_rule_fixture(),
        skill_definitions=normalized_skill_definitions(),
    )
    source["appraisal_charm_skill_groups"] = rules["appraisal_charm_skill_groups"]
    source["appraisal_charm_patterns"] = (
        rules["appraisal_charm_patterns"] if field == "patterns" else []
    )

    with pytest.raises(CatalogDecodeError) as exc_info:
        build_catalog_document_with_appraisal_charm_rules(
            catalog_value=source,
            rule_value=load_rule_fixture(),
        )

    assert exc_info.value.path == "$.catalog"


@pytest.mark.parametrize("catalog_value", [None, [], (), "catalog", DictSubclass()])
def test_catalog_merge_rejects_non_exact_catalog_dict(catalog_value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        build_catalog_document_with_appraisal_charm_rules(
            catalog_value=catalog_value,
            rule_value=load_rule_fixture(),
            catalog_path="$.source",
        )

    assert exc_info.value.path == "$.source"


def test_catalog_merge_preserves_decoder_error_path() -> None:
    source = base_catalog_document()
    source["schema_version"] = 0

    with pytest.raises(CatalogDecodeError) as exc_info:
        build_catalog_document_with_appraisal_charm_rules(
            catalog_value=source,
            rule_value=load_rule_fixture(),
            catalog_path="$.source",
        )

    assert exc_info.value.path == "$.source.schema_version"


def test_catalog_merge_does_not_mutate_inputs_and_returns_independent_copies() -> None:
    source = base_catalog_document()
    rules = load_rule_fixture()
    before = copy.deepcopy((source, rules))

    first = build_catalog_document_with_appraisal_charm_rules(
        catalog_value=source,
        rule_value=rules,
    )
    second = build_catalog_document_with_appraisal_charm_rules(
        catalog_value=source,
        rule_value=rules,
    )

    assert (source, rules) == before
    assert first == second
    assert first is not second
    assert first["skills"] is not second["skills"]
    assert first["skills"][0] is not second["skills"][0]
    assert first["equipment"] is not second["equipment"]
    assert first["equipment"][0] is not second["equipment"][0]
    assert first["decorations"] is not second["decorations"]
    assert (
        first["appraisal_charm_skill_groups"]
        is not second["appraisal_charm_skill_groups"]
    )


def test_catalog_merge_requires_keyword_arguments_and_defaults() -> None:
    signature = inspect.signature(build_catalog_document_with_appraisal_charm_rules)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    assert signature.parameters["catalog_path"].default == "$.catalog"
    assert signature.parameters["rule_path"].default == "$.appraisal_rules"
    with pytest.raises(TypeError):
        build_catalog_document_with_appraisal_charm_rules(  # type: ignore[call-arg]
            base_catalog_document(), load_rule_fixture()
        )


def test_import_functions_are_not_exported_from_catalog_package() -> None:
    assert not hasattr(catalog_package, "normalize_appraisal_charm_rule_snapshot")
    assert not hasattr(
        catalog_package,
        "build_catalog_document_with_appraisal_charm_rules",
    )
