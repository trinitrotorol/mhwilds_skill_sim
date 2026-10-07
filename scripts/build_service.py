"""Build both static applications and versioned catalogs as one release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from mhwilds_skill_sim.api.catalog_response import build_catalog_metadata_response
from mhwilds_skill_sim.browser.catalog_export import build_browser_search_catalog
from mhwilds_skill_sim.catalog.checker_export import (
    build_checker_catalog,
    validate_generated_at,
)
from mhwilds_skill_sim.catalog.loader import load_catalog
from scripts.merge_appraisal_rules import merge_files
from scripts.service_html import CHECKER_PATH, SIM_PATH, enrich_release_apps
from scripts.sync_mhdb_catalog import sync_files
from scripts.sync_appraisal_sheet import sync_files as sync_appraisal

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> bytes:
    content = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return content


def git_sha(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def git_dirty(path: Path) -> bool:
    """Include untracked source while respecting the repository ignore rules."""
    return bool(
        subprocess.check_output(
            [
                "git",
                "-C",
                str(path),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignore-submodules=none",
            ],
            text=True,
        ).strip()
    )


def build_service(
    source: Path | None = None,
    *,
    fixture: bool = False,
    appraisal_rules: Path | None = None,
    generated_at: str | None = None,
    require_clean: bool = False,
) -> dict[str, object]:
    stamp = validate_generated_at(
        generated_at
        if generated_at is not None
        else datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
    child = ROOT / "subprojects/inventory-checker"
    if not (child / "contracts/checker-catalog.v1.schema.json").is_file():
        raise ValueError("Initialize the pinned inventory-checker submodule first")
    parent_sha, checker_sha = git_sha(ROOT), git_sha(child)
    source_dirty = {"parent": git_dirty(ROOT), "checker": git_dirty(child)}
    if require_clean and any(source_dirty.values()):
        raise ValueError("Production builds require clean parent and checker sources")
    staging = ROOT / ".build/service-staging" / stamp.replace(":", "-")
    staging.mkdir(parents=True, exist_ok=False)
    source_path = staging / "catalog.json"
    if source is None:
        sync_files(raw_directory=staging / "raw", catalog_output_path=source_path)
    else:
        if "fixtures" in source.parts and not fixture:
            raise ValueError("Synthetic catalogs require explicit --fixture")
        shutil.copyfile(source, source_path)
    appraisal_provenance: dict[str, object] | None = None
    if source is None and appraisal_rules is None:
        appraisal_rules = staging / "appraisal-rules.json"
        appraisal_provenance = sync_appraisal(
            catalog_path=source_path,
            raw_directory=staging / "appraisal-source",
            rule_output_path=appraisal_rules,
        )
    if appraisal_rules:
        if appraisal_provenance is None:
            appraisal_provenance = {
                "kind": "provided-rule-snapshot",
                "rules_sha256": hashlib.sha256(
                    appraisal_rules.read_bytes()
                ).hexdigest(),
            }
        merged = staging / "catalog-with-appraisal.json"
        merge_files(
            catalog_input_path=source_path,
            appraisal_rules_input_path=appraisal_rules,
            output_path=merged,
        )
        source_path = merged
    catalog = load_catalog(path=source_path)
    if not catalog.skills or not catalog.equipment or not catalog.decorations:
        raise ValueError("Refusing an empty production catalog")
    revision = hashlib.sha256(source_path.read_bytes()).hexdigest()
    checker = build_checker_catalog(
        catalog=catalog, revision=revision, generated_at=stamp
    )
    from jsonschema import Draft202012Validator, FormatChecker

    checker_schema = json.loads(
        (child / "contracts/checker-catalog.v1.schema.json").read_text()
    )
    Draft202012Validator(checker_schema, format_checker=FormatChecker()).validate(
        checker
    )
    compact = build_browser_search_catalog(
        catalog=catalog,
        source_catalog_sha256=revision,
        include_generated_appraisal_charms=False,
    )
    for path, args in [
        (ROOT, ["--prefix", "apps/web", "run", "build"]),
        (child, ["run", "build"]),
    ]:
        subprocess.run(["sh", str(path / "scripts/npmw"), *args], cwd=path, check=True)
    output = staging / "assets"
    shutil.copytree(ROOT / "apps/web/dist" / SIM_PATH, output / SIM_PATH)
    shutil.copytree(child / "dist", output / CHECKER_PATH)
    enrich_release_apps(output)
    sim = output / SIM_PATH
    compact_bytes = write_json(sim / "browser-solver/catalog.json", compact)
    compact_hash = hashlib.sha256(compact_bytes).hexdigest()
    compact_name = f"catalog-{compact_hash}.json"
    (sim / "browser-solver/catalog.json").rename(sim / "browser-solver" / compact_name)
    write_json(
        sim / "browser-solver/manifest.json",
        {
            "format_version": 1,
            "catalog_file": compact_name,
            "compact_sha256": compact_hash,
            "source_catalog_sha256": revision,
            "raw_bytes": len(compact_bytes),
        },
    )
    write_json(sim / "catalog/checker-catalog.json", checker)
    if git_sha(ROOT) != parent_sha or git_sha(child) != checker_sha:
        raise ValueError(
            "Source commits changed during the build; rebuild from stable sources"
        )
    source_dirty = {
        "parent": source_dirty["parent"] or git_dirty(ROOT),
        "checker": source_dirty["checker"] or git_dirty(child),
    }
    if require_clean and any(source_dirty.values()):
        raise ValueError("Source files changed during the production build")
    manifest = {
        "schema_version": 1,
        "parent_sha": parent_sha,
        "checker_sha": checker_sha,
        "source_dirty": source_dirty,
        "catalog_revision": revision,
        "generated_at": stamp,
        "fixture": fixture,
        "remote_enabled": False,
        "appraisal_rules_available": bool(catalog.appraisal_charm_patterns),
        "features": build_catalog_metadata_response(catalog=catalog)["features"],
        "source": "https://wilds.mhdb.io",
        "appraisal_source": appraisal_provenance,
        "source_files": [
            {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted((staging / "raw").glob("*.json"))
        ],
        "counts": {
            "skills": len(catalog.skills),
            "decorations": len(catalog.decorations),
            "fixed_charms": len(checker["fixed_charms"]),
            "appraisal_patterns": len(catalog.appraisal_charm_patterns),
        },
    }
    write_json(sim / "release.json", manifest)
    headers = (
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: no-referrer\n"
        "  Content-Security-Policy: default-src 'self'; script-src 'self'; "
        "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
        "worker-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self'\n"
        f"/{SIM_PATH}/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        f"/{CHECKER_PATH}/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n"
        f"/{SIM_PATH}/browser-solver/catalog-*\n  Cache-Control: public, max-age=31536000, immutable\n"
        f"/{SIM_PATH}/catalog/*\n  Cache-Control: no-cache\n"
        f"/{SIM_PATH}/browser-solver/manifest.json\n  Cache-Control: no-cache\n"
        f"/{SIM_PATH}/release.json\n  Cache-Control: no-cache\n"
        f"/{SIM_PATH}/\n  Cache-Control: no-cache\n"
        f"/{CHECKER_PATH}/\n  Cache-Control: no-cache\n"
    )
    (output / "_headers").write_text(headers, encoding="utf-8")
    published = ROOT / ".build/service-assets"
    if published.exists():
        previous = staging / "previous-assets"
        published.rename(previous)
    output.rename(published)
    output = published
    # Only publish the staging pointer after all generation/build/schema checks pass.
    write_json(
        ROOT / ".build/service-current.json",
        {
            "assets": str(output.relative_to(ROOT)),
            "manifest": manifest,
        },
    )
    return {"assets": str(output), **manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--appraisal-rules", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument(
        "--generated-at", default=os.environ.get("SERVICE_GENERATED_AT")
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build_service(
                args.source,
                fixture=args.fixture,
                appraisal_rules=args.appraisal_rules,
                generated_at=args.generated_at,
                require_clean=args.require_clean,
            )
        )
    )


if __name__ == "__main__":
    main()
