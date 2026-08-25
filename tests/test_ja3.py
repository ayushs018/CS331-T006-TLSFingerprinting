"""Unit tests for JA3/JA3S string formatting, hashing, and byte parsing.

Expected MD5 values below were computed independently with Python's
hashlib against the exact JA3/JA3S strings documented in each test,
so they double as a spec-conformance check, not just a regression test.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ja3.ja3 import (
    ja3_from_client_hello,
    ja3_string_from_fields,
    ja3s_string_from_fields,
    hash_string,
)
from ja3.parser import parse_client_hello

GREASE_A = 0x0A0A  # 2570
GREASE_F = 0xFAFA  # 64250


def test_ja3_string_strips_grease_and_formats_correctly():
    ja3_str = ja3_string_from_fields(
        version=771,
        ciphers=[GREASE_A, 4865, 4866, 4867],
        extensions=[0, 23, 65281, 10, 11, 35, 16, 5, 13, 18, 51, 45, 43, 27, 21, GREASE_F],
        curves=[GREASE_A, 29, 23, 24],
        point_formats=[0],
    )
    assert ja3_str == (
        "771,4865-4866-4867,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-21,29-23-24,0"
    )
    assert hash_string(ja3_str) == "44fe69c4f06ceb97bc9e86726e8a4fd2"


def test_ja3s_string_strips_grease_and_formats_correctly():
    ja3s_str = ja3s_string_from_fields(
        version=771, cipher=4865, extensions=[GREASE_A, 0, 23, 65281]
    )
    assert ja3s_str == "771,4865,0-23-65281"
    assert hash_string(ja3s_str) == "0e521c374f675b150f4c40dfbb14ea44"


def test_ja3_matches_official_salesforce_readme_vector():
    """External validation: reproduces the exact hash published in the
    original JA3 spec's own README (github.com/salesforce/ja3), not a
    value we computed ourselves. This is the "validated against
    published reference JA3 hashes" checkpoint.
    """
    ja3_str = ja3_string_from_fields(
        version=769,
        ciphers=[47, 53, 5, 10, 49161, 49162, 49171, 49172, 50, 56, 19, 4],
        extensions=[0, 10, 11],
        curves=[23, 24, 25],
        point_formats=[0],
    )
    assert ja3_str == "769,47-53-5-10-49161-49162-49171-49172-50-56-19-4,0-10-11,23-24-25,0"
    assert hash_string(ja3_str) == "ada70206e40642a3e4461f35503241d5"


def test_ja3_matches_official_readme_vector_with_no_extensions():
    """Same source as above; also exercises the documented edge case
    where a ClientHello has no extensions at all (trailing empty fields).
    """
    ja3_str = ja3_string_from_fields(
        version=769,
        ciphers=[4, 5, 10, 9, 100, 98, 3, 6, 19, 18, 99],
        extensions=[],
        curves=[],
        point_formats=[],
    )
    assert ja3_str == "769,4-5-10-9-100-98-3-6-19-18-99,,,"
    assert hash_string(ja3_str) == "de350869b8c85de67a350c8d186f11e6"


def _build_client_hello() -> bytes:
    """Hand-pack a minimal but wire-accurate ClientHello for parser testing."""
    session_id = b""
    ciphers = [GREASE_A, 4865, 4866, 4867]
    cipher_bytes = b"".join(struct.pack(">H", c) for c in ciphers)
    comp_methods = b"\x00"

    curves = [GREASE_A, 29, 23, 24]
    curve_bytes = b"".join(struct.pack(">H", c) for c in curves)
    ext_supported_groups = struct.pack(">HH", 10, 2 + len(curve_bytes)) + struct.pack(
        ">H", len(curve_bytes)
    ) + curve_bytes

    point_formats = bytes([0])
    ext_point_formats = struct.pack(">HH", 11, 1 + len(point_formats)) + bytes(
        [len(point_formats)]
    ) + point_formats

    ext_server_name = struct.pack(">HH", 0, 0)
    ext_reneg_info = struct.pack(">HH", 65281, 1) + b"\x00"

    extensions = ext_server_name + ext_supported_groups + ext_point_formats + ext_reneg_info

    body = (
        struct.pack(">H", 771)  # client_version
        + b"\x00" * 32  # random
        + bytes([len(session_id)]) + session_id
        + struct.pack(">H", len(cipher_bytes)) + cipher_bytes
        + bytes([len(comp_methods)]) + comp_methods
        + struct.pack(">H", len(extensions)) + extensions
    )

    handshake = bytes([0x01]) + struct.pack(">I", len(body))[1:] + body  # type + 3-byte length
    record = bytes([0x16]) + struct.pack(">H", 0x0301) + struct.pack(">H", len(handshake)) + handshake
    return record


def test_parse_client_hello_extracts_all_ja3_fields():
    raw = _build_client_hello()
    fields = parse_client_hello(raw)

    assert fields["version"] == 771
    assert fields["ciphers"] == [GREASE_A, 4865, 4866, 4867]
    assert fields["extensions"] == [0, 10, 11, 65281]
    assert fields["curves"] == [GREASE_A, 29, 23, 24]
    assert fields["point_formats"] == [0]


def test_ja3_from_client_hello_end_to_end():
    raw = _build_client_hello()
    ja3_str, ja3_hash = ja3_from_client_hello(raw)

    assert ja3_str == "771,4865-4866-4867,0-10-11-65281,29-23-24,0"
    assert ja3_hash == "d73947874064f656f77dbc6485bfcc99"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
