"""Fetch MHDB snapshots and write a normalized Catalog."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.catalog.mhdb_sync import (
    fetch_mhdb_snapshot_bundle,
    write_mhdb_sync_outputs,
)


def sync_files(
    *,
    raw_directory: Path,
    catalog_output_path: Path,
    locale: str = "ja",
    timeout_seconds: float = 30.0,
) -> None:
    bundle = fetch_mhdb_snapshot_bundle(
        locale=locale,
        timeout_seconds=timeout_seconds,
    )
    write_mhdb_sync_outputs(
        bundle=bundle,
        raw_directory=raw_directory,
        catalog_output_path=catalog_output_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch MHDB snapshots and write a normalized Catalog.",
    )
    parser.add_argument("raw_directory", type=Path)
    parser.add_argument("catalog_output_json", type=Path)
    parser.add_argument("--locale", default="ja")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)

    sync_files(
        raw_directory=args.raw_directory,
        catalog_output_path=args.catalog_output_json,
        locale=args.locale,
        timeout_seconds=args.timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
