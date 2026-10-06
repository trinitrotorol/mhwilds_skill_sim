"""Fetch attributed appraisal numeric facts and generate reproducible rule input."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from mhwilds_skill_sim.catalog.appraisal_sheet import (
    ENGLISH_SKILLS_URL,
    GROUPS_URL,
    MAX_SOURCE_BYTES,
    PATTERNS_URL,
    SHEET_URL,
    extract_appraisal_rule_snapshot,
)
from mhwilds_skill_sim.catalog.loader import load_catalog


def fetch_source(url: str, *, timeout_seconds: float = 30) -> bytes:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout must be finite and positive")
    if url not in (PATTERNS_URL, GROUPS_URL, ENGLISH_SKILLS_URL):
        raise ValueError("Only the documented public source URLs are supported")
    request = Request(
        url,
        headers={
            "User-Agent": "mhwilds-skill-sim/0.1",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        final = urlparse(response.url)
        allowed_host = final.hostname in ("docs.google.com", "wilds.mhdb.io") or (
            final.hostname is not None
            and final.hostname.endswith(".googleusercontent.com")
        )
        if response.status != 200 or final.scheme != "https" or not allowed_host:
            raise ValueError("Untrusted or failed source response")
        expected_type = "application/json" if url == ENGLISH_SKILLS_URL else "text/csv"
        if response.headers.get_content_type() != expected_type:
            raise ValueError("Unexpected source content type")
        content = response.read(MAX_SOURCE_BYTES + 1)
        if len(content) > MAX_SOURCE_BYTES:
            raise ValueError("Source exceeds the 5 MiB safety size limit")
        return content


def sync_files(
    *,
    catalog_path: Path,
    raw_directory: Path,
    rule_output_path: Path,
    patterns_csv: Path | None = None,
    groups_csv: Path | None = None,
    english_skills_json: Path | None = None,
    timeout_seconds: float = 30,
) -> dict[str, object]:
    offline = (patterns_csv, groups_csv, english_skills_json)
    if any(p is not None for p in offline) and not all(p is not None for p in offline):
        raise ValueError("Offline operation requires all three source files")
    sources = [
        ("patterns.csv", PATTERNS_URL, patterns_csv),
        ("groups.csv", GROUPS_URL, groups_csv),
        ("skills-en.json", ENGLISH_SKILLS_URL, english_skills_json),
    ]
    raw_targets = [raw_directory / filename for filename, _, _ in sources]
    outputs = [*raw_targets, raw_directory / "metadata.json", rule_output_path]
    resolved = [p.resolve() for p in outputs]
    if len(set(resolved)) != len(resolved) or catalog_path.resolve() in resolved:
        raise ValueError("Output paths must not collide with each other or catalog")
    content = [
        path.read_bytes()
        if path
        else fetch_source(url, timeout_seconds=timeout_seconds)
        for _, url, path in sources
    ]
    if any(len(body) > MAX_SOURCE_BYTES for body in content):
        raise ValueError("Source exceeds the 5 MiB safety size limit")
    catalog = load_catalog(path=catalog_path)
    rules = extract_appraisal_rule_snapshot(
        patterns_csv=content[0].decode("utf-8-sig"),
        groups_csv=content[1].decode("utf-8-sig"),
        english_skills=json.loads(content[2]),
        skill_definitions=catalog.skills,
    )
    metadata: dict[str, object] = {
        "source": SHEET_URL,
        "attribution": {
            "mining": "Dtlnor",
            "grouping": "Aki at Wiggler",
            "japanese_reference": "https://x.com/the_anchor7/status/1955990911713993025",
        },
        "retrieved_at": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "use": "Numeric game facts only; no third-party code, prose, layout or images",
        "license": "No explicit sheet/code redistribution license asserted",
        "sources": [
            {"file": filename, "url": url, "sha256": hashlib.sha256(body).hexdigest()}
            for (filename, url, _), body in zip(sources, content)
        ],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
    }
    rules_bytes = (json.dumps(rules, ensure_ascii=False, indent=2) + "\n").encode()
    metadata["rules_sha256"] = hashlib.sha256(rules_bytes).hexdigest()
    # All fetch, parsing, identity joins and rule validation finish before writes.
    for target, body in zip(raw_targets, content):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    raw_directory.joinpath("metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rule_output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = rule_output_path.with_suffix(rule_output_path.suffix + ".tmp")
    temporary.write_bytes(rules_bytes)
    temporary.replace(rule_output_path)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("raw_directory", type=Path)
    parser.add_argument("rule_output", type=Path)
    parser.add_argument("--patterns-csv", type=Path)
    parser.add_argument("--groups-csv", type=Path)
    parser.add_argument("--english-skills-json", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            sync_files(
                catalog_path=args.catalog,
                raw_directory=args.raw_directory,
                rule_output_path=args.rule_output,
                patterns_csv=args.patterns_csv,
                groups_csv=args.groups_csv,
                english_skills_json=args.english_skills_json,
                timeout_seconds=args.timeout_seconds,
            )
        )
    )


if __name__ == "__main__":
    main()
