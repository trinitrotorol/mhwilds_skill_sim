"""Catalog JSON file loading."""

from __future__ import annotations

import json
from pathlib import Path

from mhwilds_skill_sim.catalog.decoder import decode_catalog
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.catalog.model import Catalog


def load_catalog(
    *,
    path: str | Path,
) -> Catalog:
    if type(path) is str:
        catalog_path = Path(path)
    elif isinstance(path, Path):
        catalog_path = path
    else:
        raise TypeError("path must be str or Path")

    try:
        content = catalog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogDecodeError(
            path=str(catalog_path),
            detail=f"cannot read catalog JSON file: {exc}",
        ) from exc

    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CatalogDecodeError(
            path=str(catalog_path),
            detail=f"invalid JSON: {exc.msg}",
        ) from exc

    return decode_catalog(value=value, path="$")
