"""Catalog decode errors."""

from __future__ import annotations


class CatalogDecodeError(ValueError):
    path: str
    detail: str

    def __init__(self, *, path: str, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"{path}: {detail}")
