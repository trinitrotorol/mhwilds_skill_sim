from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart
from scripts.normalize_mhdb_charms import main, normalize_files

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "fixtures"
SOURCES = (
    FIXTURE_DIR / "mhdb_skills_raw.json",
    FIXTURE_DIR / "mhdb_weapons_raw.json",
    FIXTURE_DIR / "mhdb_armor_sets_raw.json",
    FIXTURE_DIR / "mhdb_armor_raw.json",
    FIXTURE_DIR / "mhdb_charms_raw.json",
    FIXTURE_DIR / "mhdb_decorations_raw.json",
)


def copy_fixture(source: Path, destination: Path) -> bytes:
    content = source.read_bytes()
    destination.write_bytes(content)
    return content


def prepare_inputs(
    tmp_path: Path,
) -> tuple[
    tuple[Path, Path, Path, Path, Path, Path],
    tuple[bytes, bytes, bytes, bytes, bytes, bytes],
]:
    paths = tuple(tmp_path / source.name for source in SOURCES)
    contents = tuple(
        copy_fixture(source, destination) for source, destination in zip(SOURCES, paths)
    )
    return paths, contents  # type: ignore[return-value]


def normalize_to(
    *,
    input_paths: tuple[Path, Path, Path, Path, Path, Path],
    output: Path,
) -> None:
    skills, weapons, armor_sets, armor, charms, decorations = input_paths
    normalize_files(
        skills_input_path=skills,
        weapons_input_path=weapons,
        armor_sets_input_path=armor_sets,
        armor_input_path=armor,
        charms_input_path=charms,
        decorations_input_path=decorations,
        output_path=output,
    )


def test_normalize_files_writes_loadable_combined_catalog(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output = tmp_path / "catalog.json"

    normalize_to(input_paths=input_paths, output=output)

    catalog = load_catalog(path=output)
    assert catalog.schema_version == 1
    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 12
    assert len(catalog.decorations) == 3
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
    assert [equipment.equipment_id for equipment in catalog.equipment[9:]] == [
        "mhdb:charm:-5001:rank-1",
        "mhdb:charm:-5001:rank-2",
        "mhdb:charm:5002:rank-1",
    ]
    assert all("5003" not in item.equipment_id for item in catalog.equipment)


def test_normalize_files_writes_unicode_indentation_and_one_lf_newline(
    tmp_path: Path,
) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output = tmp_path / "catalog.json"

    normalize_to(input_paths=input_paths, output=output)

    content = output.read_bytes()
    text = content.decode("utf-8")
    assert "攻撃の護石Ⅰ（テスト）" in text
    assert "技術の護石（テスト）" in text
    assert "\\u653b" not in text
    assert '\n  "schema_version": 1,' in text
    assert '\n      "equipment_id": "mhdb:charm:-5001:rank-1",' in text
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")
    assert b"\r\n" not in content


def test_normalize_files_creates_output_parent_directory(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output = tmp_path / "missing" / "nested" / "catalog.json"

    normalize_to(input_paths=input_paths, output=output)

    assert output.is_file()


def test_normalize_files_do_not_modify_any_input(tmp_path: Path) -> None:
    input_paths, contents_before = prepare_inputs(tmp_path)

    normalize_to(input_paths=input_paths, output=tmp_path / "catalog.json")

    assert tuple(path.read_bytes() for path in input_paths) == contents_before


@pytest.mark.parametrize("collision_index", range(6))
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
    output = tmp_path / "catalog.json"

    result = main([*(str(path) for path in input_paths), str(output)])

    assert result == 0
    catalog = load_catalog(path=output)
    assert len(catalog.skills) == 4
    assert len(catalog.equipment[:3]) == 3
    assert len(catalog.equipment[3:9]) == 6
    assert len(catalog.equipment[9:]) == 3
    assert len(catalog.decorations) == 3


def test_module_cli_execution_succeeds(tmp_path: Path) -> None:
    input_paths, _ = prepare_inputs(tmp_path)
    output = tmp_path / "catalog.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.normalize_mhdb_charms",
            *(str(path) for path in input_paths),
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert len(load_catalog(path=output).equipment) == 12


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
            Path("charms.json"),
            Path("decorations.json"),
            Path("catalog.json"),
        )


def test_script_has_no_network_or_client_library_imports() -> None:
    source = (ROOT / "scripts" / "normalize_mhdb_charms.py").read_text(encoding="utf-8")
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
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    normalize_to(input_paths=input_paths, output=first)
    normalize_to(input_paths=input_paths, output=second)

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8")) == json.loads(
        second.read_text(encoding="utf-8")
    )
