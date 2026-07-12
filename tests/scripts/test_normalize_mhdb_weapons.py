from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart, WeaponKind
from scripts.normalize_mhdb_weapons import main, normalize_files


ROOT = Path(__file__).resolve().parents[2]
SKILL_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"
WEAPON_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_weapons_raw.json"
ARMOR_SET_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_armor_sets_raw.json"
ARMOR_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_armor_raw.json"
DECORATION_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_decorations_raw.json"


def copy_fixture(source: Path, destination: Path) -> bytes:
    content = source.read_bytes()
    destination.write_bytes(content)
    return content


def prepare_inputs(
    tmp_path: Path,
) -> tuple[
    tuple[Path, Path, Path, Path, Path],
    tuple[bytes, bytes, bytes, bytes, bytes],
]:
    paths = (
        tmp_path / "skills.json",
        tmp_path / "weapons.json",
        tmp_path / "armor_sets.json",
        tmp_path / "armor.json",
        tmp_path / "decorations.json",
    )
    sources = (
        SKILL_FIXTURE_PATH,
        WEAPON_FIXTURE_PATH,
        ARMOR_SET_FIXTURE_PATH,
        ARMOR_FIXTURE_PATH,
        DECORATION_FIXTURE_PATH,
    )
    contents = tuple(
        copy_fixture(source, destination) for source, destination in zip(sources, paths)
    )
    return paths, contents  # type: ignore[return-value]


def normalize_to(
    *,
    input_paths: tuple[Path, Path, Path, Path, Path],
    output: Path,
) -> None:
    skills, weapons, armor_sets, armor, decorations = input_paths
    normalize_files(
        skills_input_path=skills,
        weapons_input_path=weapons,
        armor_sets_input_path=armor_sets,
        armor_input_path=armor,
        decorations_input_path=decorations,
        output_path=output,
    )


def test_normalize_files_writes_loadable_combined_catalog(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    normalize_to(input_paths=input_paths, output=output_path)

    catalog = load_catalog(path=output_path)
    assert catalog.schema_version == 1
    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 9
    assert len(catalog.decorations) == 3
    weapons = catalog.equipment[:3]
    armor = catalog.equipment[3:]
    assert len(weapons) == 3
    assert len(armor) == 6
    assert all(equipment.part is EquipmentPart.WEAPON for equipment in weapons)
    assert [equipment.equipment_id for equipment in weapons] == [
        "mhdb:weapon:great-sword:4001",
        "mhdb:weapon:great-sword:-4002",
        "mhdb:weapon:bow:4001",
    ]
    assert [equipment.weapon_kind for equipment in weapons] == [
        WeaponKind.GREAT_SWORD,
        WeaponKind.GREAT_SWORD,
        WeaponKind.BOW,
    ]
    assert [equipment.display_name for equipment in weapons] == [
        "テスト大剣",
        "テストアーティア大剣",
        "テスト弓",
    ]
    assert weapons[1].allows_series_skill_assignment is True
    assert weapons[1].allows_group_skill_assignment is True
    assert armor[0].equipment_id == "mhdb:armor:-3001:head"
    assert armor[0].series_skill_id == "mhdb:skill:1003"


def test_normalize_files_writes_unicode_indentation_and_one_lf_newline(
    tmp_path: Path,
) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    normalize_to(input_paths=input_paths, output=output_path)

    content = output_path.read_bytes()
    text = content.decode("utf-8")
    assert "攻撃力強化（テスト）" in text
    assert "テストアーティア大剣" in text
    assert "テストヘルムα" in text
    assert "武器技珠【1】（テスト）" in text
    assert "\\u30c6" not in text
    assert '\n  "schema_version": 1,' in text
    assert '\n      "equipment_id": "mhdb:weapon:great-sword:4001",' in text
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")
    assert b"\r\n" not in content


def test_normalize_files_creates_output_parent_directory(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "missing" / "nested" / "catalog.json"

    normalize_to(input_paths=input_paths, output=output_path)

    assert output_path.is_file()


def test_normalize_files_do_not_modify_any_input(tmp_path: Path) -> None:
    input_paths, contents_before = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    normalize_to(input_paths=input_paths, output=output_path)

    assert tuple(path.read_bytes() for path in input_paths) == contents_before


@pytest.mark.parametrize("collision_index", range(5))
def test_rejects_output_collision_with_each_input(
    collision_index: int,
    tmp_path: Path,
) -> None:
    input_paths, contents_before = prepare_inputs(tmp_path)

    with pytest.raises(ValueError, match="input|output"):
        normalize_to(
            input_paths=input_paths,
            output=tmp_path / "." / input_paths[collision_index].name,
        )

    assert tuple(path.read_bytes() for path in input_paths) == contents_before


def test_main_normalizes_files_and_returns_zero(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    result = main([*(str(path) for path in input_paths), str(output_path)])

    assert result == 0
    loaded = load_catalog(path=output_path)
    assert len(loaded.skills) == 4
    assert len(loaded.equipment[:3]) == 3
    assert len(loaded.equipment[3:]) == 6
    assert len(loaded.decorations) == 3


def test_module_cli_execution_succeeds(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.normalize_mhdb_weapons",
            *(str(path) for path in input_paths),
            str(output_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert len(load_catalog(path=output_path).equipment) == 9


def test_normalize_files_requires_keyword_arguments() -> None:
    signature = inspect.signature(normalize_files)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        normalize_files(  # type: ignore[call-arg]
            Path("skills.json"),
            Path("weapons.json"),
            Path("armor_sets.json"),
            Path("armor.json"),
            Path("decorations.json"),
            Path("catalog.json"),
        )


def test_script_has_no_network_or_client_library_imports() -> None:
    script_path = ROOT / "scripts" / "normalize_mhdb_weapons.py"
    source = script_path.read_text(encoding="utf-8")
    lowered = source.lower()

    for forbidden in (
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "socket",
        "fetch(",
    ):
        assert forbidden not in lowered


def test_repeated_normalization_output_is_deterministic(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"

    normalize_to(input_paths=input_paths, output=first_output)
    normalize_to(input_paths=input_paths, output=second_output)

    assert first_output.read_bytes() == second_output.read_bytes()
    assert json.loads(first_output.read_text(encoding="utf-8")) == json.loads(
        second_output.read_text(encoding="utf-8")
    )
