from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from scripts.profile_browser_solver_oracle import (
    main,
    profile_browser_solver_oracle,
)


ROOT = Path(__file__).resolve().parents[2]
TINY_CATALOG_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"


def test_profile_function_has_keyword_only_signature() -> None:
    signature = inspect.signature(profile_browser_solver_oracle)
    assert tuple(signature.parameters) == (
        "catalog_path",
        "output_path",
        "workload_path",
        "timeout_seconds",
        "pretty",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_profile_writes_hash_linked_report_from_user_workload(
    tmp_path: Path,
) -> None:
    workload_path = tmp_path / "workload.json"
    workload_path.write_text(
        json.dumps(
            [
                {
                    "requirements": [],
                    "preferences": [
                        {
                            "skill_id": "skill:attack-boost",
                            "target_level": 1,
                        }
                    ],
                    "max_results": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "nested" / "oracle.json"

    summary = profile_browser_solver_oracle(
        catalog_path=TINY_CATALOG_PATH,
        output_path=output_path,
        workload_path=workload_path,
        timeout_seconds=5,
        pretty=True,
    )
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["case_count"] == 1
    assert summary["optimal_count"] == 1
    assert report["source_catalog_sha256"] == summary["source_catalog_sha256"]
    assert report["cases"][0]["name"] == "workload-1"
    assert report["cases"][0]["preference_score"] == 1
    assert "candidate" not in report["cases"][0]
    assert output_path.read_bytes().endswith(b"\n")


def test_profile_refuses_to_overwrite_source_catalog() -> None:
    before = TINY_CATALOG_PATH.read_bytes()

    with pytest.raises(ValueError, match="overwrite catalog_path"):
        profile_browser_solver_oracle(
            catalog_path=TINY_CATALOG_PATH,
            output_path=TINY_CATALOG_PATH,
        )

    assert TINY_CATALOG_PATH.read_bytes() == before


def test_main_prints_summary_and_propagates_workload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workload_path = tmp_path / "workload.json"
    workload_path.write_text(
        json.dumps(
            [
                {
                    "name": "empty",
                    "request": {
                        "requirements": [],
                        "preferences": [],
                        "max_results": 1,
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "oracle.json"

    exit_code = main(
        [
            str(TINY_CATALOG_PATH),
            str(output_path),
            "--workload",
            str(workload_path),
            "--timeout-seconds",
            "5",
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["case_count"] == 1
    assert "cases" not in summary
