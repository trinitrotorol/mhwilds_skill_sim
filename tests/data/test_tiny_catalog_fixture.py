import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"

EXPECTED_PARTS = {"weapon", "head", "chest", "arms", "waist", "legs", "charm"}
EXPECTED_SKILL_IDS = {
    "skill:attack-boost",
    "skill:critical-eye",
    "skill:weakness-exploit",
}
EXPECTED_METADATA_SKILL_IDS = {
    *EXPECTED_SKILL_IDS,
    "skill:fixture-weapon-technique",
    "skill:fixture-series-bonus",
    "skill:fixture-group-bonus",
}
EQUIPMENT_KEYS = {"equipment_id", "part", "skills", "slots"}
DECORATION_KEYS = {"decoration_id", "required_slot", "skills"}
SKILL_CONTRIBUTION_KEYS = {"skill_id", "level"}
SKILL_DEFINITION_KEYS = {"skill_id", "kind", "ranks"}
SKILL_RANK_KEYS = {"level", "required_pieces"}
SLOT_KEYS = {"kind", "level"}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def equipment_by_id(data: dict, equipment_id: str) -> dict:
    for equipment in data["equipment"]:
        if equipment["equipment_id"] == equipment_id:
            return equipment
    raise AssertionError(f"missing equipment: {equipment_id}")


def decoration_by_id(data: dict, decoration_id: str) -> dict:
    for decoration in data["decorations"]:
        if decoration["decoration_id"] == decoration_id:
            return decoration
    raise AssertionError(f"missing decoration: {decoration_id}")


def all_skill_entries(data: dict) -> list[dict]:
    entries = []
    for equipment in data["equipment"]:
        entries.extend(equipment["skills"])
    for decoration in data["decorations"]:
        entries.extend(decoration["skills"])
    return entries


def all_slot_entries(data: dict) -> list[dict]:
    entries = []
    for equipment in data["equipment"]:
        entries.extend(equipment["slots"])
    for decoration in data["decorations"]:
        entries.append(decoration["required_slot"])
    return entries


def test_fixture_loads_as_utf8_json() -> None:
    assert isinstance(load_fixture(), dict)


def test_top_level_keys_and_schema_version() -> None:
    data = load_fixture()

    assert list(data) == ["schema_version", "skills", "equipment", "decorations"]
    assert type(data["schema_version"]) is int
    assert data["schema_version"] == 1


def test_catalog_counts() -> None:
    data = load_fixture()

    assert len(data["skills"]) == 6
    assert len(data["equipment"]) == 9
    assert len(data["decorations"]) == 5


def test_skill_metadata_ids_are_unique_and_match_contract() -> None:
    data = load_fixture()
    skill_ids = [skill["skill_id"] for skill in data["skills"]]

    assert len(skill_ids) == len(set(skill_ids))
    assert set(skill_ids) == EXPECTED_METADATA_SKILL_IDS


def test_skill_metadata_covers_all_kinds() -> None:
    data = load_fixture()

    assert {skill["kind"] for skill in data["skills"]} == {
        "armor",
        "weapon",
        "set",
        "group",
    }


def test_equipment_ids_are_unique() -> None:
    data = load_fixture()
    equipment_ids = [equipment["equipment_id"] for equipment in data["equipment"]]

    assert len(equipment_ids) == len(set(equipment_ids))


def test_decoration_ids_are_unique() -> None:
    data = load_fixture()
    decoration_ids = [decoration["decoration_id"] for decoration in data["decorations"]]

    assert len(decoration_ids) == len(set(decoration_ids))


def test_equipment_includes_all_parts() -> None:
    data = load_fixture()

    assert {equipment["part"] for equipment in data["equipment"]} == EXPECTED_PARTS


def test_head_and_charm_have_two_candidates_each() -> None:
    data = load_fixture()

    assert sum(1 for equipment in data["equipment"] if equipment["part"] == "head") == 2
    assert (
        sum(1 for equipment in data["equipment"] if equipment["part"] == "charm") == 2
    )


def test_used_skill_ids_are_exact_contract_set() -> None:
    data = load_fixture()

    assert {
        skill["skill_id"] for skill in all_skill_entries(data)
    } == EXPECTED_SKILL_IDS


def test_equipment_keys_match_contract() -> None:
    data = load_fixture()

    for equipment in data["equipment"]:
        assert set(equipment) == EQUIPMENT_KEYS


def test_decoration_keys_match_contract() -> None:
    data = load_fixture()

    for decoration in data["decorations"]:
        assert set(decoration) == DECORATION_KEYS


def test_skill_keys_match_contract() -> None:
    data = load_fixture()

    for skill in all_skill_entries(data):
        assert set(skill) == SKILL_CONTRIBUTION_KEYS


def test_skill_metadata_keys_match_contract() -> None:
    data = load_fixture()

    for skill in data["skills"]:
        assert set(skill) == SKILL_DEFINITION_KEYS
        for rank in skill["ranks"]:
            assert set(rank) == SKILL_RANK_KEYS


def test_skill_metadata_rank_values_match_kind_contract() -> None:
    data = load_fixture()

    for skill in data["skills"]:
        assert skill["ranks"]
        for rank in skill["ranks"]:
            assert type(rank["level"]) is int
            assert rank["level"] > 0

            required_pieces = rank["required_pieces"]
            assert required_pieces is None or type(required_pieces) is int
            if required_pieces is not None:
                assert required_pieces > 0

            if skill["kind"] in {"armor", "weapon"}:
                assert required_pieces is None
            else:
                assert skill["kind"] in {"set", "group"}
                assert type(required_pieces) is int
                assert required_pieces > 0


def test_every_referenced_skill_id_has_metadata() -> None:
    data = load_fixture()
    metadata_ids = {skill["skill_id"] for skill in data["skills"]}

    assert {skill["skill_id"] for skill in all_skill_entries(data)} <= metadata_ids


def test_slot_keys_match_contract() -> None:
    data = load_fixture()

    for slot in all_slot_entries(data):
        assert set(slot) == SLOT_KEYS


def test_socket_braces_keeps_duplicate_armor_level_one_slots() -> None:
    data = load_fixture()
    socket_braces = equipment_by_id(data, "fixture:arms:socket-braces")

    assert socket_braces["slots"] == [
        {"kind": "armor", "level": 1},
        {"kind": "armor", "level": 1},
    ]


def test_armor_combination_keeps_skill_order() -> None:
    data = load_fixture()
    combination = decoration_by_id(data, "fixture:decoration:armor-combination-2")

    assert [skill["skill_id"] for skill in combination["skills"]] == [
        "skill:attack-boost",
        "skill:critical-eye",
    ]


def test_equipment_and_decoration_kind_contracts() -> None:
    data = load_fixture()

    for equipment in data["equipment"]:
        expected_kind = "weapon" if equipment["part"] == "weapon" else "armor"
        for slot in equipment["slots"]:
            assert slot["kind"] == expected_kind

    for decoration in data["decorations"]:
        decoration_id = decoration["decoration_id"]
        required_slot_kind = decoration["required_slot"]["kind"]
        if decoration_id.startswith("fixture:decoration:weapon-"):
            assert required_slot_kind == "weapon"
        elif decoration_id.startswith("fixture:decoration:armor-"):
            assert required_slot_kind == "armor"
        else:
            raise AssertionError(f"unknown decoration kind prefix: {decoration_id}")


def test_equipment_allows_empty_skills_and_slots_but_decorations_do_not() -> None:
    data = load_fixture()

    assert equipment_by_id(data, "fixture:arms:socket-braces")["skills"] == []
    assert equipment_by_id(data, "fixture:waist:precision-coil")["slots"] == []
    assert equipment_by_id(data, "fixture:charm:power")["slots"] == []
    assert equipment_by_id(data, "fixture:charm:precision")["slots"] == []
    for decoration in data["decorations"]:
        assert decoration["skills"]


def test_all_levels_are_strict_positive_ints_and_not_bool() -> None:
    data = load_fixture()

    levels = [skill["level"] for skill in all_skill_entries(data)]
    levels.extend(slot["level"] for slot in all_slot_entries(data))
    for level in levels:
        assert type(level) is int
        assert level > 0
