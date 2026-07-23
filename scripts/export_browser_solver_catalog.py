"""Export a normalized Catalog for the local browser-solver feasibility spike."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.browser.catalog_export import (
    DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
    build_browser_search_catalog,
)
from mhwilds_skill_sim.catalog.loader import load_catalog


def export_browser_solver_catalog(
    *,
    catalog_path: Path,
    output_path: Path,
    maximum_expanded_equipment: int = DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
    pretty: bool = False,
) -> dict[str, object]:
    """Load, export, write, and summarize one browser search Catalog."""

    if not isinstance(catalog_path, Path):
        raise TypeError("catalog_path must be Path")
    if not isinstance(output_path, Path):
        raise TypeError("output_path must be Path")
    if type(maximum_expanded_equipment) is not int:
        raise TypeError("maximum_expanded_equipment must be int")
    if maximum_expanded_equipment < 0:
        raise ValueError("maximum_expanded_equipment must be at least zero")
    if type(pretty) is not bool:
        raise TypeError("pretty must be bool")
    if catalog_path.resolve() == output_path.resolve():
        raise ValueError("output_path must not overwrite catalog_path")

    source_bytes = catalog_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    catalog = load_catalog(path=catalog_path)
    browser_catalog = build_browser_search_catalog(
        catalog=catalog,
        source_catalog_sha256=source_sha256,
        maximum_expanded_equipment=maximum_expanded_equipment,
    )
    output_bytes = _serialize_json(value=browser_catalog, pretty=pretty)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_bytes)

    source_catalog = browser_catalog["source_catalog"]
    equipment_by_part = browser_catalog["equipment_by_part"]
    assert isinstance(source_catalog, dict)
    assert isinstance(equipment_by_part, dict)
    return {
        "format_version": browser_catalog["format_version"],
        "source_sha256": source_sha256,
        "raw_bytes": len(output_bytes),
        "gzip_bytes": len(gzip.compress(output_bytes, mtime=0)),
        "expanded_equipment_count": source_catalog["expanded_equipment_count"],
        "part_counts": {
            part: len(variants)
            for part, variants in equipment_by_part.items()
            if isinstance(variants, list)
        },
        "decoration_count": source_catalog["decoration_count"],
        "skill_count": source_catalog["skill_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a compact Catalog for the browser solver benchmark.",
    )
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("browser_catalog_json", type=Path)
    parser.add_argument(
        "--maximum-expanded-equipment",
        type=int,
        default=DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    summary = export_browser_solver_catalog(
        catalog_path=args.catalog_json,
        output_path=args.browser_catalog_json,
        maximum_expanded_equipment=args.maximum_expanded_equipment,
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


def _serialize_json(*, value: object, pretty: bool) -> bytes:
    options: dict[str, object] = {
        "ensure_ascii": False,
        "sort_keys": False,
    }
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return json.dumps(value, **options).encode("utf-8") + b"\n"


if __name__ == "__main__":
    raise SystemExit(main())
