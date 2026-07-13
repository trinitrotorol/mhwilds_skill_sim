from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.decoder import decode_catalog
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.mhdb_armor import (
    build_skill_armor_and_decoration_catalog_document,
    normalize_mhdb_armor_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIRECTORY = ROOT / "data" / "fixtures"


def load_fixture(name: str) -> list[dict[str, object]]:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


def raw_skill_rank(game_id: int, *, level: int = 1) -> dict[str, object]:
    return {
        "skill": {
            "gameId": game_id,
            "name": "ignored skill stub",
        },
        "level": level,
        "description": "ignored skill-rank field",
    }


def raw_armor(
    *,
    skills: list[dict[str, object]],
    armor_set_id: int = 701,
) -> dict[str, object]:
    return {
        "id": 9801,
        "name": "所属テストヘルム",
        "kind": "head",
        "armorSet": {
            "id": armor_set_id,
            "name": "ignored armor-set stub",
        },
        "skills": skills,
        "slots": [1],
    }


def raw_bonus_skill(
    game_id: int,
    *,
    kind: str,
    maximum_level: int = 2,
) -> dict[str, object]:
    return {
        "id": game_id + 10000,
        "gameId": game_id,
        "name": f"追加{kind}スキル{game_id}",
        "kind": kind,
        "ranks": [
            {
                "level": level,
                "setPiecesRequired": level * 2,
                "description": "ignored bonus rank",
            }
            for level in range(1, maximum_level + 1)
        ],
    }


def cross_membership_skills() -> list[dict[str, object]]:
    skills = load_fixture("mhdb_skills_raw.json")
    skills.extend(
        [
            raw_bonus_skill(1103, kind="set"),
            raw_bonus_skill(1203, kind="set"),
            raw_bonus_skill(1104, kind="group"),
            raw_bonus_skill(1204, kind="group"),
        ]
    )
    return skills


def cross_membership_armor() -> dict[str, object]:
    return raw_armor(
        skills=[
            raw_skill_rank(1203, level=2),
            raw_skill_rank(1001, level=2),
            raw_skill_rank(1104, level=2),
            raw_skill_rank(1103),
            raw_skill_rank(1204),
            raw_skill_rank(1003, level=2),
            raw_skill_rank(1004),
        ]
    )


def test_live_shape_fixture_separates_primary_markers_from_fixed_skills() -> None:
    raw = load_fixture("mhdb_armor_raw.json")
    first_raw_skills = raw[0]["skills"]

    assert [
        skill_rank["skill"]["gameId"]  # type: ignore[index]
        for skill_rank in first_raw_skills  # type: ignore[union-attr]
    ] == [1001, 1003, 1004]

    normalized = normalize_mhdb_armor_snapshot(
        value=raw,
        armor_set_snapshot=load_fixture("mhdb_armor_sets_raw.json"),
        skill_snapshot=load_fixture("mhdb_skills_raw.json"),
    )
    first = normalized[0]

    assert first["skills"] == [{"skill_id": "mhdb:skill:1001", "level": 1}]
    assert first["series_skill_id"] == "mhdb:skill:1003"
    assert first["group_skill_id"] == "mhdb:skill:1004"
    assert "additional_series_skill_ids" not in first
    assert "additional_group_skill_ids" not in first


def test_cross_memberships_preserve_raw_order_and_exact_output_key_order() -> None:
    skills = cross_membership_skills()
    armor_sets = load_fixture("mhdb_armor_sets_raw.json")
    armor = cross_membership_armor()
    before = copy.deepcopy((skills, armor_sets, armor))

    normalized = normalize_mhdb_armor_snapshot(
        value=[armor],
        armor_set_snapshot=armor_sets,
        skill_snapshot=skills,
    )

    assert (skills, armor_sets, armor) == before
    assert normalized == [
        {
            "equipment_id": "mhdb:armor:-3001:head",
            "display_name": "所属テストヘルム",
            "part": "head",
            "skills": [{"skill_id": "mhdb:skill:1001", "level": 2}],
            "slots": [{"kind": "armor", "level": 1}],
            "series_skill_id": "mhdb:skill:1003",
            "group_skill_id": "mhdb:skill:1004",
            "additional_series_skill_ids": [
                "mhdb:skill:1203",
                "mhdb:skill:1103",
            ],
            "additional_group_skill_ids": [
                "mhdb:skill:1104",
                "mhdb:skill:1204",
            ],
            "allows_series_skill_assignment": False,
            "allows_group_skill_assignment": False,
        }
    ]
    assert list(normalized[0]) == [
        "equipment_id",
        "display_name",
        "part",
        "skills",
        "slots",
        "series_skill_id",
        "group_skill_id",
        "additional_series_skill_ids",
        "additional_group_skill_ids",
        "allows_series_skill_assignment",
        "allows_group_skill_assignment",
    ]


def test_raw_markers_remain_additional_when_armor_set_has_no_primary() -> None:
    skills = cross_membership_skills()
    armor_sets = load_fixture("mhdb_armor_sets_raw.json")
    armor_sets[0]["setBonusSkill"] = None
    armor_sets[0]["groupBonusSkill"] = None

    normalized = normalize_mhdb_armor_snapshot(
        value=[
            raw_armor(
                skills=[
                    raw_skill_rank(1103),
                    raw_skill_rank(1104),
                ]
            )
        ],
        armor_set_snapshot=armor_sets,
        skill_snapshot=skills,
    )

    assert normalized[0]["series_skill_id"] is None
    assert normalized[0]["group_skill_id"] is None
    assert normalized[0]["additional_series_skill_ids"] == ["mhdb:skill:1103"]
    assert normalized[0]["additional_group_skill_ids"] == ["mhdb:skill:1104"]


@pytest.mark.parametrize(
    ("game_id", "marker_name"),
    [
        (1003, "series"),
        (1004, "group"),
    ],
)
def test_duplicate_marker_is_rejected_at_second_raw_path(
    game_id: int,
    marker_name: str,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[
                raw_armor(
                    skills=[
                        raw_skill_rank(game_id),
                        raw_skill_rank(game_id),
                    ]
                )
            ],
            armor_set_snapshot=load_fixture("mhdb_armor_sets_raw.json"),
            skill_snapshot=load_fixture("mhdb_skills_raw.json"),
        )

    assert exc_info.value.path == "$.armor[0].skills[1]"
    assert marker_name in exc_info.value.detail
    assert "duplicated" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("game_id", "level"),
    [
        (1003, 3),
        (1004, 2),
    ],
)
def test_bonus_marker_level_must_not_exceed_catalog_rank(
    game_id: int,
    level: int,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[raw_skill_rank(game_id, level=level)])],
            armor_set_snapshot=load_fixture("mhdb_armor_sets_raw.json"),
            skill_snapshot=load_fixture("mhdb_skills_raw.json"),
        )

    assert exc_info.value.path == "$.armor[0].skills[0].level"
    assert "maximum" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_weapon_marker_is_rejected_with_supported_kind_detail() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        normalize_mhdb_armor_snapshot(
            value=[raw_armor(skills=[raw_skill_rank(-1002)])],
            armor_set_snapshot=load_fixture("mhdb_armor_sets_raw.json"),
            skill_snapshot=load_fixture("mhdb_skills_raw.json"),
        )

    assert exc_info.value.path == "$.armor[0].skills[0]"
    assert all(
        kind in exc_info.value.detail for kind in ("armor", "set", "group", "weapon")
    )
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_cross_membership_document_passes_catalog_decoder() -> None:
    document = build_skill_armor_and_decoration_catalog_document(
        skill_value=cross_membership_skills(),
        armor_set_value=load_fixture("mhdb_armor_sets_raw.json"),
        armor_value=[cross_membership_armor()],
        decoration_value=load_fixture("mhdb_decorations_raw.json"),
    )

    catalog = decode_catalog(value=document)
    equipment = catalog.equipment[0]

    assert equipment.series_skill_id == "mhdb:skill:1003"
    assert equipment.group_skill_id == "mhdb:skill:1004"
    assert equipment.additional_series_skill_ids == (
        "mhdb:skill:1203",
        "mhdb:skill:1103",
    )
    assert equipment.additional_group_skill_ids == (
        "mhdb:skill:1104",
        "mhdb:skill:1204",
    )
    assert equipment.series_skill_ids == (
        "mhdb:skill:1003",
        "mhdb:skill:1203",
        "mhdb:skill:1103",
    )
    assert equipment.group_skill_ids == (
        "mhdb:skill:1004",
        "mhdb:skill:1104",
        "mhdb:skill:1204",
    )
