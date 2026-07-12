"""Fetch MHDB snapshots and write a normalized Catalog."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import cast
from urllib import error as urllib_error
from urllib import request as urllib_request

from mhwilds_skill_sim.catalog.decoder import decode_catalog
from mhwilds_skill_sim.catalog.mhdb_charms import (
    build_skill_weapon_armor_charm_and_decoration_catalog_document,
)

_MHDB_SOURCE_URL = "https://wilds.mhdb.io"
_SNAPSHOT_ENDPOINTS = (
    ("skills", "skills", "skills.json"),
    ("decorations", "decorations", "decorations.json"),
    ("armor_sets", "armor/sets", "armor_sets.json"),
    ("armor", "armor", "armor.json"),
    ("weapons", "weapons", "weapons.json"),
    ("charms", "charms", "charms.json"),
)
_BUNDLE_KEYS = (
    "version",
    "locale",
    "skills",
    "decorations",
    "armor_sets",
    "armor",
    "weapons",
    "charms",
)
_BUNDLE_KEY_SET = frozenset(_BUNDLE_KEYS)
_REQUEST_HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "identity",
    "User-Agent": "mhwilds-skill-sim/0.1",
}


class MhdbSnapshotFetchError(RuntimeError):
    """Raised when an MHDB response cannot be fetched or decoded."""


def fetch_json_url(
    *,
    url: str,
    timeout_seconds: float,
) -> object:
    validated_url = _validate_url(url)
    validated_timeout = _validate_timeout_seconds(timeout_seconds)
    request = urllib_request.Request(validated_url, headers=_REQUEST_HEADERS)

    try:
        with urllib_request.urlopen(
            request,
            timeout=validated_timeout,
        ) as response:
            body = response.read()
        return json.loads(body.decode("utf-8"))
    except (
        urllib_error.HTTPError,
        urllib_error.URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MhdbSnapshotFetchError(
            f"failed to fetch JSON from {validated_url}: {exc}"
        ) from exc


def fetch_mhdb_snapshot_bundle(
    *,
    locale: str = "ja",
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    validated_locale = _validate_locale(locale, field_name="locale")
    validated_timeout = _validate_timeout_seconds(timeout_seconds)
    version_url = f"{_MHDB_SOURCE_URL}/version"
    version_response = fetch_json_url(
        url=version_url,
        timeout_seconds=validated_timeout,
    )

    try:
        if type(version_response) is not dict:
            raise TypeError("version response must be object")
        if "version" not in version_response:
            raise ValueError("version response must contain version")
        version = _validate_version(
            version_response["version"],
            field_name="version",
        )
    except (TypeError, ValueError) as exc:
        raise MhdbSnapshotFetchError(
            f"invalid response from {version_url}: {exc}"
        ) from exc

    bundle: dict[str, object] = {
        "version": version,
        "locale": validated_locale,
    }
    for key, endpoint, _ in _SNAPSHOT_ENDPOINTS:
        endpoint_url = f"{_MHDB_SOURCE_URL}/{validated_locale}/{endpoint}"
        snapshot = fetch_json_url(
            url=endpoint_url,
            timeout_seconds=validated_timeout,
        )
        if type(snapshot) is not list:
            error = TypeError(f"{key} response must be list")
            raise MhdbSnapshotFetchError(
                f"invalid response from {endpoint_url}: {error}"
            ) from error
        bundle[key] = snapshot

    return bundle


def build_catalog_document_from_mhdb_snapshot_bundle(
    *,
    bundle: object,
) -> dict[str, object]:
    validated_bundle = _validate_bundle(bundle)
    document = build_skill_weapon_armor_charm_and_decoration_catalog_document(
        skill_value=validated_bundle["skills"],
        weapon_value=validated_bundle["weapons"],
        armor_set_value=validated_bundle["armor_sets"],
        armor_value=validated_bundle["armor"],
        charm_value=validated_bundle["charms"],
        decoration_value=validated_bundle["decorations"],
    )
    decode_catalog(value=document)
    return document


def write_mhdb_sync_outputs(
    *,
    bundle: object,
    raw_directory: Path,
    catalog_output_path: Path,
) -> None:
    if not isinstance(raw_directory, Path):
        raise TypeError("raw_directory must be Path")
    if not isinstance(catalog_output_path, Path):
        raise TypeError("catalog_output_path must be Path")
    if raw_directory.is_file():
        raise ValueError("raw_directory must not be a regular file")

    resolved_raw_directory = raw_directory.resolve()
    raw_targets = (
        resolved_raw_directory / "metadata.json",
        *(resolved_raw_directory / filename for _, _, filename in _SNAPSHOT_ENDPOINTS),
    )
    resolved_catalog_output = catalog_output_path.resolve()
    if resolved_catalog_output in raw_targets:
        raise ValueError(
            "catalog_output_path output must not collide with a raw_directory "
            "input filename"
        )

    document = build_catalog_document_from_mhdb_snapshot_bundle(bundle=bundle)
    validated_bundle = cast(dict[str, object], bundle)
    metadata = {
        "source": _MHDB_SOURCE_URL,
        "locale": validated_bundle["locale"],
        "version": validated_bundle["version"],
        "files": {key: filename for key, _, filename in _SNAPSHOT_ENDPOINTS},
    }
    raw_values = (
        metadata,
        *(validated_bundle[key] for key, _, _ in _SNAPSHOT_ENDPOINTS),
    )

    for target, value in zip(raw_targets, raw_values):
        _write_json_file(path=target, value=value)
    _write_json_file(path=resolved_catalog_output, value=document)


def _validate_url(value: object) -> str:
    if type(value) is not str:
        raise TypeError("url must be str")
    if value == "":
        raise ValueError("url must not be empty")
    if value.strip() == "":
        raise ValueError("url must not be blank")
    if value != value.strip():
        raise ValueError("url must not have leading or trailing whitespace")
    if not value.startswith("https://"):
        raise ValueError("url must begin with https://")
    return value


def _validate_timeout_seconds(value: object) -> int | float:
    if type(value) not in (int, float):
        raise TypeError("timeout_seconds must be int or float")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("timeout_seconds must be finite")
    if value <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    return value


def _validate_version(value: object, *, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")
    if value == "":
        raise ValueError(f"{field_name} must not be empty")
    if value.strip() == "":
        raise ValueError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have leading or trailing whitespace")
    return value


def _validate_locale(value: object, *, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")
    if len(value) != 2 or any(
        character < "a" or character > "z" for character in value
    ):
        raise ValueError(f"{field_name} must be exactly two lowercase ASCII letters")
    return value


def _validate_bundle(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError("bundle must be dict")

    missing_keys = [key for key in _BUNDLE_KEYS if key not in value]
    extra_keys = [key for key in value if key not in _BUNDLE_KEY_SET]
    if missing_keys or extra_keys:
        detail_parts: list[str] = []
        if missing_keys:
            detail_parts.append("missing keys: " + ", ".join(missing_keys))
        if extra_keys:
            ordered_extra_keys = sorted(
                extra_keys,
                key=lambda key: (type(key).__name__, repr(key)),
            )
            detail_parts.append(
                "unexpected keys: "
                + ", ".join(_format_key(key) for key in ordered_extra_keys)
            )
        raise ValueError("bundle has " + "; ".join(detail_parts))

    bundle = cast(dict[str, object], value)
    _validate_version(bundle["version"], field_name="bundle.version")
    _validate_locale(bundle["locale"], field_name="bundle.locale")
    for key, _, _ in _SNAPSHOT_ENDPOINTS:
        if type(bundle[key]) is not list:
            raise TypeError(f"bundle.{key} must be list")
    return bundle


def _format_key(value: object) -> str:
    return value if type(value) is str else repr(value)


def _write_json_file(*, path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(content)
