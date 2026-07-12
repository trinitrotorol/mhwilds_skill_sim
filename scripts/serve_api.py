"""Load a normalized Catalog and serve the FastAPI application."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import uvicorn

from mhwilds_skill_sim.api.app import create_app
from mhwilds_skill_sim.catalog.loader import load_catalog


def serve_catalog_api(
    *,
    catalog_path: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    if not isinstance(catalog_path, Path):
        raise TypeError("catalog_path must be Path")

    if type(host) is not str:
        raise TypeError("host must be str")
    if not host or not host.strip() or host != host.strip():
        raise ValueError("host must be non-blank without surrounding whitespace")

    if type(port) is not int:
        raise TypeError("port must be int")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    catalog = load_catalog(path=catalog_path)
    application = create_app(catalog=catalog)
    uvicorn.run(
        application,
        host=host,
        port=port,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load a normalized Catalog and serve the FastAPI application.",
    )
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    serve_catalog_api(
        catalog_path=args.catalog_json,
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
