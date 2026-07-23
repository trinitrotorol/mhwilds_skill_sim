from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

from mhwilds_skill_sim.browser.catalog_export import (
    BrowserCatalogSizeError,
    build_browser_search_catalog,
    write_browser_search_catalog,
)
from mhwilds_skill_sim.catalog.model import Catalog


ROOT = Path(__file__).resolve().parents[2]
COMMITTED_TINY_BROWSER_CATALOG = (
    ROOT
    / "apps"
    / "web"
    / "src"
    / "browser-solver"
    / "fixtures"
    / "tiny-browser-catalog.json"
)


class CatalogSubclass(Catalog):
    pass


def test_export_signature_is_keyword_only() -> None:
    signature = inspect.signature(build_browser_search_catalog)
    assert tuple(signature.parameters) == (
        "catalog",
        "source_catalog_sha256",
        "maximum_expanded_equipment",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_tiny_export_has_exact_order_indexes_and_generated_candidates(
    tiny_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    value = build_browser_search_catalog(
        catalog=tiny_catalog,
        source_catalog_sha256=tiny_sha256,
    )

    assert list(value) == [
        "format_version",
        "source_catalog",
        "skills",
        "equipment_by_part",
        "decorations",
    ]
    assert list(value["source_catalog"]) == [  # type: ignore[arg-type]
        "schema_version",
        "sha256",
        "source_equipment_count",
        "generated_appraisal_charm_count",
        "expanded_equipment_count",
        "decoration_count",
        "skill_count",
    ]
    assert value["source_catalog"] == {  # type: ignore[comparison-overlap]
        "schema_version": 1,
        "sha256": tiny_sha256,
        "source_equipment_count": 9,
        "generated_appraisal_charm_count": 8,
        "expanded_equipment_count": 17,
        "decoration_count": 5,
        "skill_count": 6,
    }
    equipment_by_part = value["equipment_by_part"]
    assert isinstance(equipment_by_part, dict)
    assert list(equipment_by_part) == [
        "weapon",
        "head",
        "chest",
        "arms",
        "waist",
        "legs",
        "charm",
    ]
    variants = [
        variant
        for part_variants in equipment_by_part.values()
        for variant in part_variants
    ]
    assert [variant["variant_id"] for variant in variants] == list(range(17))
    assert [variant["equipment_id"] for variant in equipment_by_part["charm"]][:2] == [
        "fixture:charm:power",
        "fixture:charm:precision",
    ]
    assert all(
        variant["equipment_id"].startswith("generated:appraisal-charm:")
        for variant in equipment_by_part["charm"][2:]
    )

    skills = value["skills"]
    assert isinstance(skills, list)
    assert [skill["skill_id"] for skill in skills] == [
        definition.skill_id for definition in tiny_catalog.skills
    ]
    assert skills[4]["required_pieces"] == [2, 4]
    assert skills[5]["required_pieces"] == [3]
    compound = value["decorations"][4]  # type: ignore[index]
    assert compound["skills"] == [[0, 1], [1, 1]]


def test_part_major_variant_ids_remain_contiguous_for_interleaved_source(
    tiny_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    equipment = tiny_catalog.equipment
    interleaved = (
        equipment[0],
        equipment[1],
        equipment[3],
        equipment[2],
        *equipment[4:],
    )
    catalog = Catalog(
        schema_version=tiny_catalog.schema_version,
        equipment=interleaved,
        decorations=tiny_catalog.decorations,
        skills=tiny_catalog.skills,
        appraisal_charm_skill_groups=tiny_catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=tiny_catalog.appraisal_charm_patterns,
    )

    value = build_browser_search_catalog(
        catalog=catalog,
        source_catalog_sha256=tiny_sha256,
    )
    equipment_by_part = value["equipment_by_part"]
    assert isinstance(equipment_by_part, dict)
    flattened = [
        variant["variant_id"]
        for part_variants in equipment_by_part.values()
        for variant in part_variants
    ]
    assert flattened == list(range(len(flattened)))
    assert [variant["equipment_id"] for variant in equipment_by_part["head"]] == [
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
    ]


def test_export_accepts_catalog_subclass_and_does_not_mutate_input(
    tiny_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    catalog = CatalogSubclass(
        schema_version=tiny_catalog.schema_version,
        equipment=tiny_catalog.equipment,
        decorations=tiny_catalog.decorations,
        skills=tiny_catalog.skills,
        appraisal_charm_skill_groups=tiny_catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=tiny_catalog.appraisal_charm_patterns,
    )
    before = copy.deepcopy(catalog)

    json.dumps(
        build_browser_search_catalog(
            catalog=catalog,
            source_catalog_sha256=tiny_sha256,
        )
    )

    assert catalog == before


@pytest.mark.parametrize("invalid_catalog", [None, {}, object()])
def test_export_rejects_invalid_catalog(
    invalid_catalog: object,
    tiny_sha256: str,
) -> None:
    with pytest.raises(TypeError, match="catalog must be Catalog"):
        build_browser_search_catalog(
            catalog=invalid_catalog,  # type: ignore[arg-type]
            source_catalog_sha256=tiny_sha256,
        )


@pytest.mark.parametrize(
    "source_hash",
    ["", "A" * 64, "g" * 64, "0" * 63, 1, None],
)
def test_export_rejects_invalid_source_hash(
    tiny_catalog: Catalog,
    source_hash: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match="source_catalog_sha256"):
        build_browser_search_catalog(
            catalog=tiny_catalog,
            source_catalog_sha256=source_hash,  # type: ignore[arg-type]
        )


def test_preflight_stops_before_expansion_limit(
    tiny_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    with pytest.raises(BrowserCatalogSizeError) as error_info:
        build_browser_search_catalog(
            catalog=tiny_catalog,
            source_catalog_sha256=tiny_sha256,
            maximum_expanded_equipment=16,
        )

    assert error_info.value.estimated_count == 17
    assert error_info.value.maximum_count == 16
    assert "17" in str(error_info.value)
    assert "16" in str(error_info.value)


def test_artian_variants_keep_distinct_ids_for_same_equipment_id(
    artian_variant_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    value = build_browser_search_catalog(
        catalog=artian_variant_catalog,
        source_catalog_sha256=tiny_sha256,
    )
    equipment_by_part = value["equipment_by_part"]
    assert isinstance(equipment_by_part, dict)
    weapon_variants = equipment_by_part["weapon"]
    assert isinstance(weapon_variants, list)

    assert len(weapon_variants) == 4
    assert {variant["equipment_id"] for variant in weapon_variants} == {
        "fixture:weapon:training-blade"
    }
    assert len({variant["variant_id"] for variant in weapon_variants}) == 4
    assert {
        (
            tuple(variant["series_skill_ids"]),
            tuple(variant["group_skill_ids"]),
        )
        for variant in weapon_variants
    } == {
        ((4,), (5,)),
        ((4,), (7,)),
        ((6,), (5,)),
        ((6,), (7,)),
    }


def test_export_preserves_primary_and_additional_membership_indexes(
    primary_additional_membership_catalog: Catalog,
    tiny_sha256: str,
) -> None:
    value = build_browser_search_catalog(
        catalog=primary_additional_membership_catalog,
        source_catalog_sha256=tiny_sha256,
    )
    equipment_by_part = value["equipment_by_part"]
    assert isinstance(equipment_by_part, dict)
    head_variants = equipment_by_part["head"]
    assert isinstance(head_variants, list)
    head = head_variants[0]

    assert head["equipment_id"] == "fixture:head:precision-alpha"
    assert head["series_skill_id"] == 4
    assert head["series_skill_ids"] == [4, 6]
    assert head["group_skill_id"] == 5
    assert head["group_skill_ids"] == [5, 7]


def test_compact_writer_is_deterministic_utf8_lf_and_creates_parent(
    tiny_browser_catalog: dict[str, object],
    tmp_path: Path,
) -> None:
    first = tmp_path / "one" / "catalog.json"
    second = tmp_path / "two" / "catalog.json"
    before = copy.deepcopy(tiny_browser_catalog)

    write_browser_search_catalog(value=tiny_browser_catalog, output_path=first)
    write_browser_search_catalog(value=tiny_browser_catalog, output_path=second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes().endswith(b"\n")
    assert b"\r\n" not in first.read_bytes()
    assert b"\n" not in first.read_bytes()[:-1]
    assert json.loads(first.read_text(encoding="utf-8")) == tiny_browser_catalog
    assert tiny_browser_catalog == before


def test_committed_tiny_browser_catalog_exactly_regenerates(
    tiny_browser_catalog: dict[str, object],
) -> None:
    regenerated = (
        json.dumps(
            tiny_browser_catalog,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )

    assert regenerated == COMMITTED_TINY_BROWSER_CATALOG.read_bytes()
