from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
from scripts.normalize_mhdb_skills import main, normalize_file


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "mhdb_skills_raw.json"


def copy_fixture(path: Path) -> bytes:
    content = FIXTURE_PATH.read_bytes()
    path.write_bytes(content)
    return content


def test_normalize_file_writes_loadable_skill_only_catalog(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "normalized.json"
    copy_fixture(input_path)

    normalize_file(input_path=input_path, output_path=output_path)

    catalog = load_catalog(path=output_path)
    assert catalog.schema_version == 1
    assert len(catalog.skills) == 4
    assert catalog.equipment == ()
    assert catalog.decorations == ()
    assert [skill.skill_id for skill in catalog.skills] == [
        "mhdb:skill:1001",
        "mhdb:skill:-1002",
        "mhdb:skill:1003",
        "mhdb:skill:1004",
    ]
    assert [skill.display_name for skill in catalog.skills] == [
        "攻撃力強化（テスト）",
        "武器技術（テスト）",
        "シリーズボーナス（テスト）",
        "グループボーナス（テスト）",
    ]


def test_normalize_file_writes_unicode_indentation_and_one_lf_newline(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "normalized.json"
    copy_fixture(input_path)

    normalize_file(input_path=input_path, output_path=output_path)

    content = output_path.read_bytes()
    text = content.decode("utf-8")
    assert "攻撃力強化（テスト）" in text
    assert "\\u653b" not in text
    assert '\n  "schema_version": 1,' in text
    assert '\n      "skill_id": "mhdb:skill:1001",' in text
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")
    assert b"\r\n" not in content


def test_normalize_file_creates_output_parent_directory(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "missing" / "nested" / "normalized.json"
    copy_fixture(input_path)

    normalize_file(input_path=input_path, output_path=output_path)

    assert output_path.is_file()


def test_normalize_file_does_not_modify_input(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "normalized.json"
    before = copy_fixture(input_path)

    normalize_file(input_path=input_path, output_path=output_path)

    assert input_path.read_bytes() == before


def test_normalize_file_rejects_same_resolved_input_and_output_path(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "raw.json"
    before = copy_fixture(input_path)
    equivalent_output = tmp_path / "." / "raw.json"

    with pytest.raises(ValueError, match="input|output"):
        normalize_file(
            input_path=input_path,
            output_path=equivalent_output,
        )

    assert input_path.read_bytes() == before


def test_main_normalizes_file_and_returns_zero(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "normalized.json"
    copy_fixture(input_path)

    result = main([str(input_path), str(output_path)])

    assert result == 0
    assert load_catalog(path=output_path).skills


def test_module_cli_execution_succeeds(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "normalized.json"
    copy_fixture(input_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.normalize_mhdb_skills",
            str(input_path),
            str(output_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    assert load_catalog(path=output_path).skills


def test_normalize_file_requires_keyword_arguments() -> None:
    signature = inspect.signature(normalize_file)

    assert signature.parameters["input_path"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["output_path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        normalize_file(Path("input.json"), Path("output.json"))  # type: ignore[call-arg]


def test_script_has_no_network_or_client_library_imports() -> None:
    script_path = ROOT / "scripts" / "normalize_mhdb_skills.py"
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
    input_path = tmp_path / "raw.json"
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    copy_fixture(input_path)

    normalize_file(input_path=input_path, output_path=first_output)
    normalize_file(input_path=input_path, output_path=second_output)

    assert first_output.read_bytes() == second_output.read_bytes()
    assert json.loads(first_output.read_text(encoding="utf-8")) == json.loads(
        second_output.read_text(encoding="utf-8")
    )
