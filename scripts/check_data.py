"""Validate JSON files under the data directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def iter_json_files(data_dir: Path) -> list[Path]:
    """Return JSON files below data_dir in stable order."""
    if not data_dir.exists():
        return []

    return sorted(path for path in data_dir.rglob("*.json") if path.is_file())


def check_data(data_dir: Path) -> int:
    """Validate JSON files below data_dir and return a process exit code."""
    json_files = iter_json_files(data_dir)
    error_count = 0

    for path in json_files:
        try:
            with path.open(encoding="utf-8") as file:
                json.load(file)
        except json.JSONDecodeError as exc:
            print(f"{path}: invalid JSON: {exc}", file=sys.stderr)
            error_count += 1
        except OSError as exc:
            print(f"{path}: cannot read file: {exc}", file=sys.stderr)
            error_count += 1

    print(f"Checked {len(json_files)} JSON file(s).")
    return 1 if error_count else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the data checker."""
    parser = argparse.ArgumentParser(description="Validate JSON files under data.")
    parser.add_argument("data_dir", nargs="?", default="data")
    args = parser.parse_args(argv)

    return check_data(Path(args.data_dir))


if __name__ == "__main__":
    raise SystemExit(main())
