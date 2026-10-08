"""Release staging must validate metadata before any writes or subprocesses."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import scripts.build_service as script
from mhwilds_skill_sim.catalog.mhdb_charms import (
    build_skill_weapon_armor_charm_and_decoration_catalog_document,
)

FIXTURES = Path(__file__).resolve().parents[2] / "data/fixtures"


def prepare_release(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    child = workspace / "subprojects/inventory-checker"
    schema = child / "contracts/checker-catalog.v1.schema.json"
    schema.parent.mkdir(parents=True)
    # Contract conformance is checked independently; isolate publication here.
    schema.write_text('{"type":"object"}', encoding="utf-8")
    for dist in [
        workspace / "apps/web/dist" / script.SIM_PATH,
        workspace / "apps/web/dist" / script.LEGACY_SIM_PATH,
        child / "dist",
    ]:
        dist.mkdir(parents=True)
        (dist / "index.html").write_text(
            '<!doctype html><html lang="ja"><head><title>Application</title></head>'
            '<body><div id="root"></div><script type="module" '
            'src="./assets/app.js"></script></body></html>',
            encoding="utf-8",
        )

    def read(name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            build_skill_weapon_armor_charm_and_decoration_catalog_document(
                skill_value=read("mhdb_skills_raw.json"),
                weapon_value=read("mhdb_weapons_raw.json"),
                armor_set_value=read("mhdb_armor_sets_raw.json"),
                armor_value=read("mhdb_armor_raw.json"),
                charm_value=read("mhdb_charms_raw.json"),
                decoration_value=read("mhdb_decorations_raw.json"),
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "ROOT", workspace)
    monkeypatch.setattr(script, "git_sha", lambda path: "a" * 40)
    monkeypatch.setattr(script, "git_dirty", lambda path: False)
    monkeypatch.setattr(script.subprocess, "run", lambda *args, **kwargs: None)
    return workspace, source


@pytest.mark.parametrize(
    "stamp", ["../../outside", "", "2026-10-06T00:00:00+00:00", "2026-02-30T00:00:00Z"]
)
def test_invalid_timestamp_cannot_create_staging_or_launch_builds(
    tmp_path, monkeypatch, stamp
):
    monkeypatch.setattr(script, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="generated_at"):
        script.build_service(Path("missing-source.json"), generated_at=stamp)
    assert not list(tmp_path.iterdir())


def test_publication_records_provided_rule_hash_and_actual_feature_availability(
    tmp_path, monkeypatch
):
    workspace, source = prepare_release(tmp_path, monkeypatch)
    monkeypatch.setattr(script, "git_dirty", lambda path: path == workspace)
    rules = FIXTURES / "appraisal_rules_raw.json"
    result = script.build_service(
        source, fixture=True, appraisal_rules=rules, generated_at="2026-10-06T00:00:00Z"
    )
    output = workspace / ".build/service-assets"
    published = json.loads((output / script.SIM_PATH / "release.json").read_text())
    assert published["appraisal_source"] == {
        "kind": "provided-rule-snapshot",
        "rules_sha256": hashlib.sha256(rules.read_bytes()).hexdigest(),
    }
    assert published["source_dirty"] == {"parent": True, "checker": False}
    assert published["features"] == {
        "artian_series_skill_assignment": True,
        "artian_group_skill_assignment": True,
        "theoretical_appraisal_charms": True,
    }
    assert result["catalog_revision"] == published["catalog_revision"]
    assert (output / script.CHECKER_PATH / "index.html").is_file()
    for app_path in [script.SIM_PATH, script.CHECKER_PATH]:
        html = (output / app_path / "index.html").read_text(encoding="utf-8")
        assert f"https://mhwilds.trinitrotorol.com/{app_path}/" in html
        assert 'id="service-overview"' in html
        assert len(list((output / app_path / "assets").glob("service-info-*.css"))) == 1
    assert "style-src 'self'" in (output / "_headers").read_text()
    assert "unsafe-inline" not in (output / "_headers").read_text()
    pointer = json.loads((workspace / ".build/service-current.json").read_text())
    assert pointer["manifest"] == published


def test_both_origins_build_from_same_pinned_sources_and_catalog(tmp_path, monkeypatch):
    workspace, source = prepare_release(tmp_path, monkeypatch)
    builds = []
    monkeypatch.setattr(
        script.subprocess, "run", lambda *args, **kwargs: builds.append(kwargs)
    )
    script.build_service(source, fixture=True, generated_at="2026-10-06T00:00:00Z")
    assert [
        (call["env"]["VITE_BASE_PATH"], call["env"]["VITE_SIM_BASE_PATH"])
        for call in builds
    ] == [
        (f"/{script.LEGACY_SIM_PATH}/", f"/{script.LEGACY_SIM_PATH}/"),
        (f"/{script.LEGACY_CHECKER_PATH}/", f"/{script.LEGACY_SIM_PATH}/"),
        (f"/{script.SIM_PATH}/", f"/{script.SIM_PATH}/"),
        (f"/{script.CHECKER_PATH}/", f"/{script.SIM_PATH}/"),
    ]
    output = workspace / ".build/service-assets"
    for path in [
        "release.json",
        "catalog/checker-catalog.json",
        "browser-solver/manifest.json",
    ]:
        assert (output / script.SIM_PATH / path).read_bytes() == (
            output / script.LEGACY_SIM_PATH / path
        ).read_bytes()
    for old, current in [
        (script.LEGACY_SIM_PATH, script.SIM_PATH),
        (script.LEGACY_CHECKER_PATH, script.CHECKER_PATH),
    ]:
        html = (output / old / "index.html").read_text(encoding="utf-8")
        assert f"{script.ORIGIN}/{current}/" in html
        assert 'name="robots" content="noindex,follow"' in html
    assert "pub-6343181736493400" in (output / "ads.txt").read_text()
    assert (
        f"Sitemap: {script.ORIGIN}/sitemap.xml" in (output / "robots.txt").read_text()
    )
    sitemap = (output / "sitemap.xml").read_text()
    assert "game-guide" not in sitemap
    assert sitemap.count("<loc>") == 2


def test_failed_application_build_keeps_previous_assets_and_release_pointer(
    tmp_path, monkeypatch
):
    workspace, source = prepare_release(tmp_path, monkeypatch)
    output = workspace / ".build/service-assets"
    output.mkdir(parents=True)
    (output / "old.html").write_bytes(b"previous release")
    pointer = workspace / ".build/service-current.json"
    pointer.write_bytes(b"previous pointer")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "test build")

    monkeypatch.setattr(script.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        script.build_service(source, fixture=True, generated_at="2026-10-06T00:00:00Z")
    assert pointer.read_bytes() == b"previous pointer"
    assert (output / "old.html").read_bytes() == b"previous release"


def test_require_clean_rejects_before_staging(tmp_path, monkeypatch):
    workspace, source = prepare_release(tmp_path, monkeypatch)
    monkeypatch.setattr(script, "git_dirty", lambda path: True)
    with pytest.raises(ValueError, match="clean"):
        script.build_service(
            source, generated_at="2026-10-06T00:00:00Z", require_clean=True
        )
    assert not (workspace / ".build").exists()


def test_commit_changed_during_build_cannot_publish_under_wrong_sha(
    tmp_path, monkeypatch
):
    workspace, source = prepare_release(tmp_path, monkeypatch)
    revisions = iter(["a" * 40, "a" * 40, "b" * 40])
    monkeypatch.setattr(script, "git_sha", lambda path: next(revisions))
    with pytest.raises(ValueError, match="commits changed"):
        script.build_service(source, fixture=True, generated_at="2026-10-06T00:00:00Z")
    assert not (workspace / ".build/service-assets").exists()
    assert not (workspace / ".build/service-current.json").exists()
