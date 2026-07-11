"""Normalize an offline MHDB skill snapshot into Catalog JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.catalog.mhdb_skills import (
    build_skill_only_catalog_document,
)


def normalize_file(
    *,
    input_path: Path,
    output_path: Path,
) -> None:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("input and output paths must be different")

    value = json.loads(input_path.read_text(encoding="utf-8"))
    document = build_skill_only_catalog_document(value=value)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize an offline MHDB skill snapshot.",
    )
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)

    normalize_file(
        input_path=args.input_json,
        output_path=args.output_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
