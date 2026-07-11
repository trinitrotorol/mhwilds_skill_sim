from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from scripts.normalize_mhdb_decorations import main, normalize_files


ROOT = Path(__file__).resolve().parents[2]
SKILL_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"
DECORATION_FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_decorations_raw.json"


def copy_fixture(source: Path, destination: Path) -> bytes:
    content = source.read_bytes()
    destination.write_bytes(content)
    return content


def prepare_inputs(tmp_path: Path) -> tuple[Path, Path, bytes, bytes]:
    skills_path = tmp_path / "skills.json"
    decorations_path = tmp_path / "decorations.json"
    skills_content = copy_fixture(SKILL_FIXTURE_PATH, skills_path)
    decorations_content = copy_fixture(DECORATION_FIXTURE_PATH, decorations_path)
    return skills_path, decorations_path, skills_content, decorations_content


def test_normalize_files_writes_loadable_combined_catalog(tmp_path: Path) -> None:
    skills_path, decorations_path, _, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    normalize_files(
        skills_input_path=skills_path,
        decorations_input_path=decorations_path,
        output_path=output_path,
    )

    catalog = load_catalog(path=output_path)
    assert catalog.schema_version == 1
    assert len(catalog.skills) == 4
    assert len(catalog.decorations) == 3
    assert catalog.equipment == ()
    assert [decoration.decoration_id for decoration in catalog.decorations] == [
        "mhdb:decoration:-2001",
        "mhdb:decoration:2002",
        "mhdb:decoration:2003",
    ]
    assert [decoration.display_name for decoration in catalog.decorations] == [
        "武器技珠【1】（テスト）",
        "攻撃珠【1】（テスト）",
        "攻撃珠Ⅱ【2】（テスト）",
    ]


def test_normalize_files_writes_unicode_indentation_and_one_lf_newline(
    tmp_path: Path,
) -> None:
    skills_path, decorations_path, _, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    normalize_files(
        skills_input_path=skills_path,
        decorations_input_path=decorations_path,
        output_path=output_path,
    )

    content = output_path.read_bytes()
    text = content.decode("utf-8")
    assert "攻撃力強化（テスト）" in text
    assert "武器技珠【1】（テスト）" in text
    assert "\\u653b" not in text
    assert '\n  "schema_version": 1,' in text
    assert '\n      "decoration_id": "mhdb:decoration:-2001",' in text
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")
    assert b"\r\n" not in content


def test_normalize_files_creates_output_parent_directory(tmp_path: Path) -> None:
    skills_path, decorations_path, _, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "missing" / "nested" / "catalog.json"

    normalize_files(
        skills_input_path=skills_path,
        decorations_input_path=decorations_path,
        output_path=output_path,
    )

    assert output_path.is_file()


def test_normalize_files_do_not_modify_inputs(tmp_path: Path) -> None:
    skills_path, decorations_path, skills_before, decorations_before = prepare_inputs(
        tmp_path
    )
    output_path = tmp_path / "catalog.json"

    normalize_files(
        skills_input_path=skills_path,
        decorations_input_path=decorations_path,
        output_path=output_path,
    )

    assert skills_path.read_bytes() == skills_before
    assert decorations_path.read_bytes() == decorations_before


def test_rejects_output_collision_with_skills_input(tmp_path: Path) -> None:
    skills_path, decorations_path, skills_before, decorations_before = prepare_inputs(
        tmp_path
    )

    with pytest.raises(ValueError, match="input|output"):
        normalize_files(
            skills_input_path=skills_path,
            decorations_input_path=decorations_path,
            output_path=tmp_path / "." / "skills.json",
        )

    assert skills_path.read_bytes() == skills_before
    assert decorations_path.read_bytes() == decorations_before


def test_rejects_output_collision_with_decorations_input(tmp_path: Path) -> None:
    skills_path, decorations_path, skills_before, decorations_before = prepare_inputs(
        tmp_path
    )

    with pytest.raises(ValueError, match="input|output"):
        normalize_files(
            skills_input_path=skills_path,
            decorations_input_path=decorations_path,
            output_path=tmp_path / "." / "decorations.json",
        )

    assert skills_path.read_bytes() == skills_before
    assert decorations_path.read_bytes() == decorations_before


def test_main_normalizes_files_and_returns_zero(tmp_path: Path) -> None:
    skills_path, decorations_path, _, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    result = main([str(skills_path), str(decorations_path), str(output_path)])

    assert result == 0
    loaded = load_catalog(path=output_path)
    assert len(loaded.skills) == 4
    assert len(loaded.decorations) == 3


def test_module_cli_execution_succeeds(tmp_path: Path) -> None:
    skills_path, decorations_path, _, _ = prepare_inputs(tmp_path)
    output_path = tmp_path / "catalog.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.normalize_mhdb_decorations",
            str(skills_path),
            str(decorations_path),
            str(output_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert len(load_catalog(path=output_path).decorations) == 3


def test_normalize_files_requires_keyword_arguments() -> None:
    signature = inspect.signature(normalize_files)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        normalize_files(  # type: ignore[call-arg]
            Path("skills.json"),
            Path("decorations.json"),
            Path("catalog.json"),
        )


def test_script_has_no_network_or_client_library_imports() -> None:
    script_path = ROOT / "scripts" / "normalize_mhdb_decorations.py"
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
    skills_path, decorations_path, _, _ = prepare_inputs(tmp_path)
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"

    normalize_files(
        skills_input_path=skills_path,
        decorations_input_path=decorations_path,
        output_path=first_output,
    )
    normalize_files(
        skills_input_path=skills_path,
        decorations_input_path=decorations_path,
        output_path=second_output,
    )

    assert first_output.read_bytes() == second_output.read_bytes()
    assert json.loads(first_output.read_text(encoding="utf-8")) == json.loads(
        second_output.read_text(encoding="utf-8")
    )
