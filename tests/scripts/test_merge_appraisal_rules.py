from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import pytest

import scripts.merge_appraisal_rules as script_module
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.mhdb_charms import (
    build_skill_weapon_armor_charm_and_decoration_catalog_document,
)
from scripts.merge_appraisal_rules import main, merge_files

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIRECTORY = ROOT / "data" / "fixtures"
RULE_FIXTURE_PATH = FIXTURE_DIRECTORY / "appraisal_rules_raw.json"
SKILL_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_skills_raw.json"
WEAPON_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_weapons_raw.json"
ARMOR_SET_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_armor_sets_raw.json"
ARMOR_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_armor_raw.json"
CHARM_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_charms_raw.json"
DECORATION_FIXTURE_PATH = FIXTURE_DIRECTORY / "mhdb_decorations_raw.json"


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def base_catalog_document() -> dict[str, object]:
    return build_skill_weapon_armor_charm_and_decoration_catalog_document(
        skill_value=load_json(SKILL_FIXTURE_PATH),
        weapon_value=load_json(WEAPON_FIXTURE_PATH),
        armor_set_value=load_json(ARMOR_SET_FIXTURE_PATH),
        armor_value=load_json(ARMOR_FIXTURE_PATH),
        charm_value=load_json(CHARM_FIXTURE_PATH),
        decoration_value=load_json(DECORATION_FIXTURE_PATH),
    )


def prepare_inputs(tmp_path: Path) -> tuple[Path, Path, bytes, bytes]:
    catalog_input = tmp_path / "inputs" / "catalog.json"
    rule_input = tmp_path / "inputs" / "appraisal_rules.json"
    catalog_input.parent.mkdir(parents=True)
    catalog_content = (
        json.dumps(base_catalog_document(), ensure_ascii=False, indent=2) + "\n"
    ).encode()
    rule_content = RULE_FIXTURE_PATH.read_bytes()
    catalog_input.write_bytes(catalog_content)
    rule_input.write_bytes(rule_content)
    return catalog_input, rule_input, catalog_content, rule_content


def test_merge_files_writes_loadable_catalog_with_expected_counts(
    tmp_path: Path,
) -> None:
    catalog_input, rule_input, _, _ = prepare_inputs(tmp_path)
    output = tmp_path / "output" / "nested" / "catalog.json"

    merge_files(
        catalog_input_path=catalog_input,
        appraisal_rules_input_path=rule_input,
        output_path=output,
    )

    catalog = load_catalog(path=output)
    assert len(catalog.skills) == 4
    assert len(catalog.equipment) == 12
    assert len(catalog.decorations) == 3
    assert len(catalog.appraisal_charm_skill_groups) == 3
    assert len(catalog.appraisal_charm_patterns) == 10
    assert tmp_path.resolve() in output.resolve().parents
    assert ROOT.resolve() not in output.resolve().parents


def test_merge_files_writes_unicode_indentation_and_one_lf_newline(
    tmp_path: Path,
) -> None:
    catalog_input, rule_input, _, _ = prepare_inputs(tmp_path)
    output = tmp_path / "catalog.json"

    merge_files(
        catalog_input_path=catalog_input,
        appraisal_rules_input_path=rule_input,
        output_path=output,
    )

    content = output.read_bytes()
    text = content.decode("utf-8")
    assert "攻撃力強化（テスト）" in text
    assert "攻撃の護石Ⅰ（テスト）" in text
    assert "\\u653b" not in text
    assert '\n  "schema_version": 1,' in text
    assert '\n  "appraisal_charm_skill_groups": [' in text
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n")
    assert b"\r\n" not in content


def test_merge_files_does_not_modify_either_input(tmp_path: Path) -> None:
    catalog_input, rule_input, catalog_before, rules_before = prepare_inputs(tmp_path)

    merge_files(
        catalog_input_path=catalog_input,
        appraisal_rules_input_path=rule_input,
        output_path=tmp_path / "catalog.json",
    )

    assert catalog_input.read_bytes() == catalog_before
    assert rule_input.read_bytes() == rules_before


@pytest.mark.parametrize("collision", ["catalog", "rules"])
def test_merge_files_rejects_output_collision_with_each_input(
    collision: str,
    tmp_path: Path,
) -> None:
    catalog_input, rule_input, catalog_before, rules_before = prepare_inputs(tmp_path)
    output = catalog_input if collision == "catalog" else rule_input

    with pytest.raises(ValueError, match="input|output"):
        merge_files(
            catalog_input_path=catalog_input,
            appraisal_rules_input_path=rule_input,
            output_path=output.parent / "." / output.name,
        )

    assert catalog_input.read_bytes() == catalog_before
    assert rule_input.read_bytes() == rules_before


def test_main_merges_files_and_returns_zero(tmp_path: Path) -> None:
    catalog_input, rule_input, _, _ = prepare_inputs(tmp_path)
    output = tmp_path / "catalog.json"

    result = main([str(catalog_input), str(rule_input), str(output)])

    assert result == 0
    loaded = load_catalog(path=output)
    assert len(loaded.equipment) == 12
    assert len(loaded.appraisal_charm_skill_groups) == 3
    assert len(loaded.appraisal_charm_patterns) == 10


def test_merge_files_requires_keyword_arguments() -> None:
    signature = inspect.signature(merge_files)

    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )
    with pytest.raises(TypeError):
        merge_files(  # type: ignore[call-arg]
            Path("catalog.json"), Path("rules.json"), Path("output.json")
        )


def test_merge_files_output_is_deterministic(tmp_path: Path) -> None:
    catalog_input, rule_input, _, _ = prepare_inputs(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    merge_files(
        catalog_input_path=catalog_input,
        appraisal_rules_input_path=rule_input,
        output_path=first,
    )
    merge_files(
        catalog_input_path=catalog_input,
        appraisal_rules_input_path=rule_input,
        output_path=second,
    )

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8")) == json.loads(
        second.read_text(encoding="utf-8")
    )


def test_script_has_no_network_third_party_http_or_logging_imports() -> None:
    source = (ROOT / "scripts" / "merge_appraisal_rules.py").read_text(encoding="utf-8")
    lowered = source.lower()

    for forbidden in (
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "socket",
        "logging",
        "fetch(",
        "print(",
    ):
        assert forbidden not in lowered


def test_importing_script_performs_no_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("import must not read, write, or merge files")

    monkeypatch.setattr(Path, "read_text", fail_if_called)
    monkeypatch.setattr(Path, "open", fail_if_called)

    reloaded = importlib.reload(script_module)

    assert reloaded is script_module
    assert calls == []
