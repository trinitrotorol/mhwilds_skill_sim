from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import mhwilds_skill_sim.solver.inventory as inventory_module

from mhwilds_skill_sim.api.app import create_app
from mhwilds_skill_sim.api.ranked_search_request import (
    decode_ranked_search_request_payload,
)
from mhwilds_skill_sim.api.search_service import (
    search_catalog_ranked_build_candidates_with_cp_sat_from_payload,
)
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.solver.inventory import InventoryCatalogMismatchError
from mhwilds_skill_sim.solver.inventory import validate_snapshot_contract


def snapshot():
    return {
        "schema_version": 1,
        "catalog_revision": "0" * 64,
        "decorations": [],
        "fixed_charms": [],
        "appraisal_charms": [],
    }


def test_optional_inventory_extension_preserves_legacy_requests():
    legacy = dict(requirements=[], preferences=[], max_results=20)
    assert decode_ranked_search_request_payload(payload=legacy).inventory is None
    decoded = decode_ranked_search_request_payload(
        payload={**legacy, "inventory": snapshot()},
    )
    assert decoded.inventory.catalog_revision == "0" * 64


@pytest.mark.parametrize("extra", ["profile_id", "label", "updated_at", "memo"])
def test_snapshot_rejects_private_unexpected_fields(extra):
    with pytest.raises(ValueError):
        decode_ranked_search_request_payload(
            payload={
                "requirements": [],
                "preferences": [],
                "max_results": 1,
                "inventory": {**snapshot(), extra: "private"},
            }
        )


def test_invalid_input_and_catalog_mismatch_have_distinct_safe_http_statuses():
    app = create_app(catalog_revision="0" * 64)
    for error, status, detail in (
        (ValueError("private payload text"), 422, "invalid search input"),
        (TypeError("private payload text"), 422, "invalid search input"),
        (
            InventoryCatalogMismatchError("private payload text"),
            409,
            "catalog revision mismatch",
        ),
    ):
        response = asyncio.run(app.exception_handlers[type(error)](None, error))
        assert response.status_code == status
        assert json.loads(response.body) == {"detail": detail}
        assert "private" not in response.body.decode()


def test_inventory_api_composes_pinned_schema_revision_and_owned_solver():
    catalog = load_catalog(
        path=Path(__file__).resolve().parents[2] / "data/fixtures/tiny_catalog.json",
    )
    inventory = {
        **snapshot(),
        "fixed_charms": [{"equipment_id": "fixture:charm:power", "quantity": 1}],
    }
    validate_snapshot_contract(inventory)
    with pytest.raises(ValueError, match="pinned checker schema"):
        validate_snapshot_contract(
            {**inventory, "profile_id": "must not leave browser"}
        )
    payload = dict(requirements=[], preferences=[], max_results=20, inventory=inventory)
    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        catalog_revision="0" * 64,
        payload=payload,
    )
    assert response["exhausted"] and not response["timed_out"]
    assert len(response["candidates"]) == 2
    assert all(
        candidate["equipment"][-1]["equipment_id"] == "fixture:charm:power"
        for candidate in response["candidates"]
    )
    with pytest.raises(InventoryCatalogMismatchError):
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
            catalog=catalog,
            catalog_revision="1" * 64,
            payload=payload,
        )


def test_installed_package_reads_trusted_pinned_contract_path(monkeypatch, tmp_path):
    contract = (
        Path(__file__).resolve().parents[2]
        / "subprojects/inventory-checker/contracts/search-inventory.v1.schema.json"
    )
    installed_contract = tmp_path / "contracts/search-inventory.v1.schema.json"
    installed_contract.parent.mkdir()
    installed_contract.write_bytes(contract.read_bytes())
    monkeypatch.setattr(
        inventory_module,
        "__file__",
        str(tmp_path / "site-packages/mhwilds_skill_sim/solver/inventory.py"),
    )
    monkeypatch.setenv("MHWILDS_INVENTORY_CONTRACT_PATH", str(installed_contract))
    validate_snapshot_contract(snapshot())
    with pytest.raises(ValueError, match="pinned checker schema"):
        validate_snapshot_contract({**snapshot(), "schema_version": 2})
    monkeypatch.setenv("MHWILDS_INVENTORY_CONTRACT_PATH", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="unavailable"):
        validate_snapshot_contract(snapshot())
