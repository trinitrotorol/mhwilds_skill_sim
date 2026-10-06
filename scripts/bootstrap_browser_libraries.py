"""Fetch pinned Ubuntu archives over HTTPS and extract browser libraries locally.

No package manager, installer, maintainer script or system-directory write runs.
Only use this optional helper on an Ubuntu24.04 x86_64 browser test host.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import io
import json
import os
import platform
import tarfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE = 16 * 1024 * 1024
MAX_TAR = 64 * 1024 * 1024
LIBRARY_PREFIX = PurePosixPath("usr/lib/x86_64-linux-gnu")
SOURCES = (
    (
        "https://archive.ubuntu.com/ubuntu/pool/main/n/nspr/libnspr4_4.35-1.1build1_amd64.deb",
        "e579e72d091f6c7a13f5a756c31065b15aae5b81840d61b069355aa2283c07b4",
    ),
    (
        "https://archive.ubuntu.com/ubuntu/pool/main/n/nss/libnss3_3.98-1build1_amd64.deb",
        "88247fe0db5cd4c273b7dd026d9ded4ff9ba828b62437d12a2f1c2abc29468d2",
    ),
    (
        "https://archive.ubuntu.com/ubuntu/pool/main/a/alsa-lib/libasound2t64_1.2.11-1build2_amd64.deb",
        "c2f0caa30869876791ba349bef4907d5cfec47b8cfd1ae9889a05dce0feb7c39",
    ),
)


def checked_archive(body: bytes, expected_hash: str) -> bytes:
    if len(body) > MAX_ARCHIVE or hashlib.sha256(body).hexdigest() != expected_hash:
        raise ValueError("Archive SHA-256 or size does not match the pinned source")
    return body


def fetch_archive(url: str, expected_hash: str, cache: Path) -> bytes:
    path = cache / PurePosixPath(urlparse(url).path).name
    if path.is_file():
        return checked_archive(path.read_bytes(), expected_hash)
    request = Request(
        url,
        headers={
            "User-Agent": "mhwilds-service-browser-bootstrap/1",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=30) as response:
        final = urlparse(response.url)
        if (
            response.status != 200
            or final.scheme != "https"
            or final.netloc != "archive.ubuntu.com"
        ):
            raise ValueError(
                "Browser dependency response is not from the pinned HTTPS origin"
            )
        body = checked_archive(response.read(MAX_ARCHIVE + 1), expected_hash)
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def data_member(body: bytes) -> tuple[str, bytes]:
    """Parse the small ar container; never invoke ar, dpkg or package scripts."""
    if len(body) > MAX_ARCHIVE or not body.startswith(b"!<arch>\n"):
        raise ValueError("Invalid archive magic")
    offset = 8
    found = []
    while offset < len(body):
        header = body[offset : offset + 60]
        if len(header) != 60 or header[58:] != b"`\n":
            raise ValueError("Invalid ar member header")
        name = header[:16].strip().decode("ascii").removesuffix("/")
        size_text = header[48:58].strip()
        if not size_text.isdigit():
            raise ValueError("Invalid ar member size")
        size = int(size_text)
        start = offset + 60
        if start + size > len(body):
            raise ValueError("Truncated ar member")
        if name in ("data.tar.zst", "data.tar"):
            found.append((name, body[start : start + size]))
        offset = start + size + size % 2
    if offset != len(body) or len(found) != 1:
        raise ValueError("Archive must contain one complete data tar member")
    return found[0]


def decompress_zstd(body: bytes) -> bytes:
    # Ubuntu already provides libzstd for its base utilities. Load it read-only;
    # ctypes avoids installing a package or launching an external unpacker.
    library = ctypes.util.find_library("zstd")
    if library is None:
        raise RuntimeError("Existing libzstd is required; do not install OS packages")
    zstd = ctypes.CDLL(library)
    zstd.ZSTD_decompressBound.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    zstd.ZSTD_decompressBound.restype = ctypes.c_ulonglong
    zstd.ZSTD_decompress.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    zstd.ZSTD_decompress.restype = ctypes.c_size_t
    zstd.ZSTD_isError.argtypes = [ctypes.c_size_t]
    zstd.ZSTD_isError.restype = ctypes.c_uint
    source = ctypes.create_string_buffer(body)
    bound = zstd.ZSTD_decompressBound(source, len(body))
    if bound <= 0 or bound > MAX_TAR:
        raise ValueError("Zstd content exceeds the bounded extraction size")
    target = ctypes.create_string_buffer(bound)
    size = zstd.ZSTD_decompress(target, bound, source, len(body))
    if zstd.ZSTD_isError(size):
        raise ValueError("Invalid zstd data")
    return target.raw[:size]


def library_members(body: bytes) -> tuple[dict[str, bytes], dict[str, str]]:
    name, payload = data_member(body)
    if name.endswith(".zst"):
        payload = decompress_zstd(payload)
    if len(payload) > MAX_TAR:
        raise ValueError("Tar data exceeds the bounded extraction size")
    files: dict[str, bytes] = {}
    links: dict[str, str] = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe archive member path")
            if member.isdir() or not path.is_relative_to(LIBRARY_PREFIX):
                continue
            relative = path.relative_to(LIBRARY_PREFIX)
            if len(relative.parts) != 1 or ".so" not in relative.name:
                continue
            filename = relative.name
            if filename in files or filename in links:
                raise ValueError("Duplicate library path")
            if member.isfile():
                total += member.size
                if member.size < 0 or total > MAX_TAR:
                    raise ValueError("Library data exceeds the extraction size limit")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Missing library data")
                files[filename] = stream.read()
            elif member.issym():
                link = PurePosixPath(member.linkname)
                if (
                    link.is_absolute()
                    or len(link.parts) != 1
                    or link.name in (".", "..")
                ):
                    raise ValueError("Unsafe library symlink")
                links[filename] = link.name
            else:
                raise ValueError("Unsupported library entry type")
    if not files or any(target not in files for target in links.values()):
        raise ValueError("Libraries or in-archive symlink targets are missing")
    return files, links


def write_libraries(
    files: dict[str, bytes], links: dict[str, str], destination: Path
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        path = destination / name
        if path.is_symlink():
            raise ValueError("Refusing to overwrite a library symlink")
        path.write_bytes(body)
        path.chmod(0o644)
    for name, target in links.items():
        path = destination / name
        if path.is_symlink() and os.readlink(path) == target:
            continue
        if path.exists() or path.is_symlink():
            raise ValueError("Conflicting existing library symlink")
        path.symlink_to(target)


def main() -> None:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("This optional dependency set is for Ubuntu24.04 x86_64")
    cache = ROOT / ".cache/browser-runtime-archives"
    destination = ROOT / ".venv/browser-libs/usr/lib/x86_64-linux-gnu"
    for path in (cache, destination):
        if path.resolve() != path or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Dependency paths must remain inside this repository")
    prepared = [
        (url, digest, library_members(fetch_archive(url, digest, cache)))
        for url, digest in SOURCES
    ]
    for _url, _digest, (files, links) in prepared:
        write_libraries(files, links, destination)
    report = {
        "sources": [
            {"url": url, "sha256": digest, "libraries": sorted({*files, *links})}
            for url, digest, (files, links) in prepared
        ],
        "destination": str(destination.relative_to(ROOT)),
        "system_changes": False,
    }
    (cache / "manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "libraries": sum(
                    len(files) + len(links) for _, _, (files, links) in prepared
                ),
                "destination": report["destination"],
                "system_changes": False,
            }
        )
    )


if __name__ == "__main__":
    main()
