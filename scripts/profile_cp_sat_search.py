"""Profile one offline CP-SAT search against a normalized Catalog."""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Sequence

from mhwilds_skill_sim.api.search_request import decode_search_request_payload
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.solver.cp_sat_search import (
    search_catalog_build_candidates_with_cp_sat,
)


def profile_cp_sat_search(
    *,
    catalog_path: Path,
    request_path: Path,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    """Load, search, and summarize one CP-SAT probe without mutating inputs."""

    if not isinstance(catalog_path, Path):
        raise TypeError("catalog_path must be Path")
    if not isinstance(request_path, Path):
        raise TypeError("request_path must be Path")

    normalized_timeout = _normalize_timeout_seconds(value=timeout_seconds)

    total_start = perf_counter()
    catalog = load_catalog(path=catalog_path)
    catalog_loaded = perf_counter()

    with request_path.open("r", encoding="utf-8") as request_file:
        payload = json.load(request_file)
    request = decode_search_request_payload(payload=payload)

    search_start = perf_counter()
    result = search_catalog_build_candidates_with_cp_sat(
        catalog=catalog,
        requirements=request.requirements,
        max_results=request.max_results,
        weapon_kind=request.weapon_kind,
        timeout_seconds=normalized_timeout,
    )
    search_end = perf_counter()

    return {
        "catalog": {
            "schema_version": catalog.schema_version,
            "equipment_count": len(catalog.equipment),
            "decoration_count": len(catalog.decorations),
            "skill_count": len(catalog.skills),
            "appraisal_charm_skill_group_count": len(
                catalog.appraisal_charm_skill_groups
            ),
            "appraisal_charm_pattern_count": len(catalog.appraisal_charm_patterns),
        },
        "request": {
            "requirements": [
                {
                    "skill_id": requirement.skill_id,
                    "min_level": requirement.min_level,
                }
                for requirement in request.requirements
            ],
            "max_results": request.max_results,
            "weapon_kind": (
                request.weapon_kind.value if request.weapon_kind is not None else None
            ),
            "timeout_seconds": normalized_timeout,
        },
        "timing_seconds": {
            "catalog_load": _round_seconds(catalog_loaded - total_start),
            "search": _round_seconds(search_end - search_start),
            "total": _round_seconds(search_end - total_start),
        },
        "result": {
            "candidate_count": len(result.candidates),
            "exhausted": result.exhausted,
            "timed_out": result.timed_out,
        },
    }


def _normalize_timeout_seconds(*, value: object) -> float:
    if type(value) not in (int, float):
        raise TypeError("timeout_seconds must be int or float")

    try:
        normalized = float(value)
    except OverflowError as exc:
        raise ValueError("timeout_seconds must be finite") from exc

    if not isfinite(normalized):
        raise ValueError("timeout_seconds must be finite")
    if normalized <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    return normalized


def _round_seconds(value: float) -> float:
    return round(float(value), 6)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile an offline CP-SAT search against a normalized Catalog.",
    )
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("request_json", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    report = profile_cp_sat_search(
        catalog_path=args.catalog_json,
        request_path=args.request_json,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )

    result_report = report["result"]
    assert isinstance(result_report, dict)
    return 2 if result_report["timed_out"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
