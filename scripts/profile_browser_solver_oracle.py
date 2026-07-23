"""Build an offline CP-SAT oracle report for browser-solver benchmarks."""

from __future__ import annotations

import argparse
import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.browser.oracle import (
    build_browser_solver_oracle_report,
    build_representative_browser_solver_cases,
)
from mhwilds_skill_sim.catalog.loader import load_catalog


def profile_browser_solver_oracle(
    *,
    catalog_path: Path,
    output_path: Path,
    workload_path: Path | None = None,
    timeout_seconds: float = 30.0,
    pretty: bool = False,
) -> dict[str, object]:
    """Write one oracle report and return a compact execution summary."""

    if not isinstance(catalog_path, Path):
        raise TypeError("catalog_path must be Path")
    if not isinstance(output_path, Path):
        raise TypeError("output_path must be Path")
    if workload_path is not None and not isinstance(workload_path, Path):
        raise TypeError("workload_path must be Path or None")
    if type(pretty) is not bool:
        raise TypeError("pretty must be bool")
    normalized_timeout = _normalize_timeout_seconds(value=timeout_seconds)
    output_resolved = output_path.resolve()
    if catalog_path.resolve() == output_resolved:
        raise ValueError("output_path must not overwrite catalog_path")
    if workload_path is not None and workload_path.resolve() == output_resolved:
        raise ValueError("output_path must not overwrite workload_path")

    source_bytes = catalog_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    catalog = load_catalog(path=catalog_path)
    if workload_path is None:
        cases = build_representative_browser_solver_cases(catalog=catalog)
    else:
        cases = _load_workload(path=workload_path)

    oracle = build_browser_solver_oracle_report(
        catalog=catalog,
        cases=cases,
        timeout_seconds=normalized_timeout,
    )
    report = {
        "format_version": oracle["format_version"],
        "source_catalog_sha256": source_sha256,
        "timeout_seconds": oracle["timeout_seconds"],
        "omitted_cases": oracle["omitted_cases"],
        "cases": oracle["cases"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_serialize_json(value=report, pretty=pretty))

    case_reports = report["cases"]
    assert isinstance(case_reports, list)
    statuses = [
        case["status"]
        for case in case_reports
        if isinstance(case, dict) and isinstance(case.get("status"), str)
    ]
    elapsed_seconds = [
        case["elapsed_seconds"]
        for case in case_reports
        if isinstance(case, dict) and type(case.get("elapsed_seconds")) in (int, float)
    ]
    return {
        "format_version": report["format_version"],
        "source_catalog_sha256": source_sha256,
        "case_count": len(case_reports),
        "optimal_count": statuses.count("optimal"),
        "infeasible_count": statuses.count("infeasible"),
        "timed_out_count": statuses.count("timed-out"),
        "total_elapsed_seconds": round(sum(elapsed_seconds), 6),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile ranked CP-SAT cases for the browser solver oracle.",
    )
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("oracle_json", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--workload", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    summary = profile_browser_solver_oracle(
        catalog_path=args.catalog_json,
        output_path=args.oracle_json,
        workload_path=args.workload,
        timeout_seconds=args.timeout_seconds,
        pretty=args.pretty,
    )
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )
    return 0


def _load_workload(*, path: Path) -> tuple[dict[str, object], ...]:
    with path.open("r", encoding="utf-8") as workload_file:
        value = json.load(workload_file)

    if type(value) is dict and set(value) == {"cases"}:
        value = value["cases"]
    if type(value) is not list:
        raise TypeError("workload must be a list or an object containing cases")

    cases: list[dict[str, object]] = []
    for index, item in enumerate(value):
        if type(item) is not dict:
            raise TypeError(f"workload[{index}] must be object")

        if set(item) == {"name", "request"}:
            name = item["name"]
            request = item["request"]
        elif "name" in item:
            name = item["name"]
            request = {key: child for key, child in item.items() if key != "name"}
        else:
            name = f"workload-{index + 1}"
            request = item

        cases.append({"name": name, "request": request})
    return tuple(cases)


def _serialize_json(*, value: object, pretty: bool) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text.encode("utf-8") + b"\n"


def _normalize_timeout_seconds(*, value: object) -> float:
    if type(value) not in (int, float):
        raise TypeError("timeout_seconds must be int or float")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise ValueError("timeout_seconds must be finite") from error
    if not isfinite(normalized):
        raise ValueError("timeout_seconds must be finite")
    if normalized <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())
