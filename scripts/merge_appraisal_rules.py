"""Merge normalized appraisal charm rules into a Catalog JSON document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.catalog.appraisal_rule_import import (
    build_catalog_document_with_appraisal_charm_rules,
)


def merge_files(
    *,
    catalog_input_path: Path,
    appraisal_rules_input_path: Path,
    output_path: Path,
) -> None:
    resolved_output = output_path.resolve()
    resolved_inputs = (
        catalog_input_path.resolve(),
        appraisal_rules_input_path.resolve(),
    )
    if resolved_output in resolved_inputs:
        raise ValueError("output path must be different from input paths")

    catalog_value = json.loads(catalog_input_path.read_text(encoding="utf-8"))
    rule_value = json.loads(appraisal_rules_input_path.read_text(encoding="utf-8"))
    document = build_catalog_document_with_appraisal_charm_rules(
        catalog_value=catalog_value,
        rule_value=rule_value,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge appraisal charm rules into a normalized Catalog.",
    )
    parser.add_argument("catalog_input_json", type=Path)
    parser.add_argument("appraisal_rules_input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)

    merge_files(
        catalog_input_path=args.catalog_input_json,
        appraisal_rules_input_path=args.appraisal_rules_input_json,
        output_path=args.output_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
