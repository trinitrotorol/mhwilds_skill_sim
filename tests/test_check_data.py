from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_data_check(data_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.check_data", str(data_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_data_check_succeeds_with_no_json(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    result = run_data_check(data_dir)

    assert result.returncode == 0
    assert "Checked 0 JSON file(s)." in result.stdout


def test_data_check_succeeds_with_valid_json(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    nested_dir = data_dir / "nested"
    nested_dir.mkdir(parents=True)
    (nested_dir / "valid.json").write_text('{"skill": "attack"}\n', encoding="utf-8")

    result = run_data_check(data_dir)

    assert result.returncode == 0
    assert "Checked 1 JSON file(s)." in result.stdout


def test_data_check_fails_with_invalid_json(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    invalid_json = data_dir / "invalid.json"
    invalid_json.write_text('{"skill": ', encoding="utf-8")

    result = run_data_check(data_dir)

    assert result.returncode != 0
    assert str(invalid_json) in result.stderr
