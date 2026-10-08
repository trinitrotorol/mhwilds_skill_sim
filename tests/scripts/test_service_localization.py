"""English names must use stable IDs without replacing the search catalog."""

from dataclasses import replace
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from scripts.service_localization import build_english_names


@pytest.fixture
def catalogs():
    source = load_catalog(
        path=Path(__file__).resolve().parents[2] / "data/fixtures/tiny_catalog.json"
    )
    translated = replace(
        source,
        **{
            group: tuple(
                replace(item, display_name=f"English {index}")
                for index, item in enumerate(getattr(source, group))
            )
            for group in ("skills", "equipment", "decorations")
        },
    )
    return source, translated


def test_names_use_stable_ids_and_leave_solver_data_unchanged(catalogs):
    source, translated = catalogs
    result = build_english_names(catalog=source, english_catalog=translated)
    assert result["locale"] == "en"
    assert result["schema_version"] == 1
    for group, identity in (
        ("skills", "skill_id"),
        ("equipment", "equipment_id"),
        ("decorations", "decoration_id"),
    ):
        assert result["names"][group] == {
            getattr(item, identity): f"English {index}"
            for index, item in enumerate(getattr(source, group))
        }
        assert all(
            item.display_name != f"English {index}"
            for index, item in enumerate(getattr(source, group))
        )


@pytest.mark.parametrize("group", ["skills", "equipment", "decorations"])
def test_missing_id_cannot_silently_ship_partial_english_catalog(catalogs, group):
    source, translated = catalogs
    changed = {group: getattr(translated, group)[1:]}
    if group == "skills":
        # Keep the synthetic source internally valid after removing a skill.
        changed.update(
            equipment=(),
            decorations=(),
            appraisal_charm_skill_groups=(),
            appraisal_charm_patterns=(),
        )
    incomplete = replace(translated, **changed)
    with pytest.raises(ValueError, match=f"English {group} names missing"):
        build_english_names(catalog=source, english_catalog=incomplete)


def test_extra_upstream_items_do_not_change_released_catalog_ids(catalogs):
    source, translated = catalogs
    limited = replace(source, equipment=source.equipment[:1])
    result = build_english_names(catalog=limited, english_catalog=translated)
    assert set(result["names"]["equipment"]) == {limited.equipment[0].equipment_id}


def test_missing_display_name_is_rejected(catalogs):
    source, translated = catalogs
    unnamed = replace(
        translated,
        skills=(
            replace(translated.skills[0], display_name=None),
            *translated.skills[1:],
        ),
    )
    with pytest.raises(ValueError, match="English skills names missing"):
        build_english_names(catalog=source, english_catalog=unnamed)
