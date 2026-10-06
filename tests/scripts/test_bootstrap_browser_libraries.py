"""Pinned browser prerequisite archives cannot write outside their local cache."""

import hashlib
import io
import tarfile

import pytest

from scripts.bootstrap_browser_libraries import (
    checked_archive,
    data_member,
    library_members,
    write_libraries,
)


def archive(entries):
    target = io.BytesIO()
    with tarfile.open(fileobj=target, mode="w") as stream:
        for name, kind, value in entries:
            member = tarfile.TarInfo(name)
            if kind == "file":
                member.size = len(value)
                stream.addfile(member, io.BytesIO(value))
            else:
                member.type = tarfile.SYMTYPE if kind == "link" else tarfile.LNKTYPE
                member.linkname = value
                stream.addfile(member)
    body = target.getvalue()
    header = (
        f"{'data.tar/':<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(body):<10}`\n".encode()
    )
    return b"!<arch>\n" + header + body + (b"\n" if len(body) % 2 else b"")


def test_extracts_only_shared_libraries_and_safe_in_archive_links(tmp_path):
    body = archive(
        [
            ("./usr/lib/x86_64-linux-gnu/libexample.so.1.0", "file", b"library"),
            ("./usr/lib/x86_64-linux-gnu/libexample.so.1", "link", "libexample.so.1.0"),
            ("./usr/bin/installer", "file", b"never execute"),
            ("./postinst", "file", b"never execute"),
        ]
    )
    assert checked_archive(body, hashlib.sha256(body).hexdigest()) == body
    files, links = library_members(body)
    assert files == {"libexample.so.1.0": b"library"}
    assert links == {"libexample.so.1": "libexample.so.1.0"}
    destination = tmp_path / "libraries"
    write_libraries(files, links, destination)
    assert (destination / "libexample.so.1").read_bytes() == b"library"
    assert len(list(destination.iterdir())) == 2


@pytest.mark.parametrize(
    "entry",
    [
        ("/usr/lib/x86_64-linux-gnu/libbad.so", "file", b"bad"),
        ("usr/lib/x86_64-linux-gnu/../../escape", "file", b"bad"),
        ("usr/lib/x86_64-linux-gnu/libbad.so", "link", "/etc/passwd"),
        ("usr/lib/x86_64-linux-gnu/libbad.so", "link", "../escape"),
        ("usr/lib/x86_64-linux-gnu/libbad.so", "hardlink", "libother.so"),
    ],
)
def test_rejects_unsafe_paths_and_link_types_before_any_write(entry):
    with pytest.raises(ValueError):
        library_members(archive([entry]))


def test_rejects_wrong_hash_truncated_container_and_duplicate_members():
    entry = ("usr/lib/x86_64-linux-gnu/libexample.so", "file", b"library")
    body = archive([entry])
    with pytest.raises(ValueError, match="SHA"):
        checked_archive(body, "0" * 64)
    with pytest.raises(ValueError):
        data_member(body[:-5])
    with pytest.raises(ValueError, match="Duplicate"):
        library_members(archive([entry, entry]))


def test_existing_library_symlink_cannot_redirect_a_write(tmp_path):
    outside = tmp_path / "keep.txt"
    outside.write_bytes(b"keep")
    destination = tmp_path / "libraries"
    destination.mkdir()
    (destination / "libexample.so").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        write_libraries({"libexample.so": b"overwrite"}, {}, destination)
    assert outside.read_bytes() == b"keep"
