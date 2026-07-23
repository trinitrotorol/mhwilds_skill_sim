"""Validate a generated browser-solver benchmark report with Python rules."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.browser.report_validation import (
    validate_browser_solver_report,
)
from mhwilds_skill_sim.catalog.loader import load_catalog


def validate_browser_solver_report_files(
    *,
    catalog_path: Path,
    browser_catalog_path: Path,
    oracle_path: Path,
    browser_report_path: Path,
) -> dict[str, object]:
    """Load four inputs and return the independent Python validation summary."""

    for field_name, value in (
        ("catalog_path", catalog_path),
        ("browser_catalog_path", browser_catalog_path),
        ("oracle_path", oracle_path),
        ("browser_report_path", browser_report_path),
    ):
        if not isinstance(value, Path):
            raise TypeError(f"{field_name} must be Path")

    source_sha256 = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    catalog = load_catalog(path=catalog_path)
    browser_catalog = _load_json_object(
        path=browser_catalog_path,
        location="browser catalog",
    )
    oracle_report = _load_json_object(path=oracle_path, location="oracle report")
    browser_report = _load_json_object(
        path=browser_report_path,
        location="browser report",
    )

    source_metadata = browser_catalog.get("source_catalog")
    if type(source_metadata) is not dict:
        raise TypeError("browser catalog source_catalog must be object")
    if source_metadata.get("sha256") != source_sha256:
        raise ValueError("browser catalog hash does not match source Catalog bytes")

    return validate_browser_solver_report(
        catalog=catalog,
        browser_catalog=browser_catalog,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a browser solver report against its CP-SAT oracle.",
    )
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("browser_catalog_json", type=Path)
    parser.add_argument("oracle_json", type=Path)
    parser.add_argument("browser_report_json", type=Path)
    args = parser.parse_args(argv)

    summary = validate_browser_solver_report_files(
        catalog_path=args.catalog_json,
        browser_catalog_path=args.browser_catalog_json,
        oracle_path=args.oracle_json,
        browser_report_path=args.browser_report_json,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if summary["completed_parity_failure_count"] else 0


def _load_json_object(*, path: Path, location: str) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as input_file:
        value = json.load(input_file)
    if type(value) is not dict:
        raise TypeError(f"{location} must be an object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
