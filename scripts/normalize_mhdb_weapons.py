"""Normalize offline MHDB skill, weapon, armor, and decoration snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from mhwilds_skill_sim.catalog.mhdb_weapons import (
    build_skill_weapon_armor_and_decoration_catalog_document,
)


def normalize_files(
    *,
    skills_input_path: Path,
    weapons_input_path: Path,
    armor_sets_input_path: Path,
    armor_input_path: Path,
    decorations_input_path: Path,
    output_path: Path,
) -> None:
    resolved_output = output_path.resolve()
    resolved_inputs = (
        skills_input_path.resolve(),
        weapons_input_path.resolve(),
        armor_sets_input_path.resolve(),
        armor_input_path.resolve(),
        decorations_input_path.resolve(),
    )
    if resolved_output in resolved_inputs:
        raise ValueError("output path must be different from input paths")

    skill_value = json.loads(skills_input_path.read_text(encoding="utf-8"))
    weapon_value = json.loads(weapons_input_path.read_text(encoding="utf-8"))
    armor_set_value = json.loads(armor_sets_input_path.read_text(encoding="utf-8"))
    armor_value = json.loads(armor_input_path.read_text(encoding="utf-8"))
    decoration_value = json.loads(decorations_input_path.read_text(encoding="utf-8"))
    document = build_skill_weapon_armor_and_decoration_catalog_document(
        skill_value=skill_value,
        weapon_value=weapon_value,
        armor_set_value=armor_set_value,
        armor_value=armor_value,
        decoration_value=decoration_value,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize offline MHDB skill, weapon, armor, and decoration snapshots."
        ),
    )
    parser.add_argument("skills_input_json", type=Path)
    parser.add_argument("weapons_input_json", type=Path)
    parser.add_argument("armor_sets_input_json", type=Path)
    parser.add_argument("armor_input_json", type=Path)
    parser.add_argument("decorations_input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)

    normalize_files(
        skills_input_path=args.skills_input_json,
        weapons_input_path=args.weapons_input_json,
        armor_sets_input_path=args.armor_sets_input_json,
        armor_input_path=args.armor_input_json,
        decorations_input_path=args.decorations_input_json,
        output_path=args.output_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
