"""JA3 / JA3S fingerprint computation per the JA3 spec.

Spec: https://github.com/salesforce/ja3
JA3  = MD5("TLSVersion,Ciphers,Extensions,Curves,PointFormats")
JA3S = MD5("TLSVersion,Cipher,Extensions")

GREASE values (RFC 8701) are excluded from cipher/extension/curve lists
before hashing, since they're randomized per-connection noise, not a
real signal of client identity.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, List, Optional, Tuple

from .parser import parse_client_hello, parse_server_hello

# The 16 reserved GREASE values from RFC 8701: 0x0A0A, 0x1A1A, ..., 0xFAFA
GREASE_VALUES = {((h << 4) | 0xA) * 0x101 for h in range(16)}


def _strip_grease(values: Iterable[int]) -> List[int]:
    return [v for v in values if v not in GREASE_VALUES]


def _join(values: Iterable[int]) -> str:
    return "-".join(str(v) for v in values)


def ja3_string_from_fields(
    version: int,
    ciphers: Iterable[int],
    extensions: Iterable[int],
    curves: Iterable[int],
    point_formats: Iterable[int],
) -> str:
    return ",".join(
        [
            str(version),
            _join(_strip_grease(ciphers)),
            _join(_strip_grease(extensions)),
            _join(_strip_grease(curves)),
            _join(point_formats),
        ]
    )


def ja3s_string_from_fields(version: int, cipher: int, extensions: Iterable[int]) -> str:
    return ",".join(
        [
            str(version),
            str(cipher),
            _join(_strip_grease(extensions)),
        ]
    )


def hash_string(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def ja3_from_client_hello(raw: bytes) -> Optional[Tuple[str, str]]:
    fields = parse_client_hello(raw)
    if fields is None:
        return None
    ja3_str = ja3_string_from_fields(
        fields["version"],
        fields["ciphers"],
        fields["extensions"],
        fields["curves"],
        fields["point_formats"],
    )
    return ja3_str, hash_string(ja3_str)


def ja3s_from_server_hello(raw: bytes) -> Optional[Tuple[str, str]]:
    fields = parse_server_hello(raw)
    if fields is None:
        return None
    ja3s_str = ja3s_string_from_fields(fields["version"], fields["cipher"], fields["extensions"])
    return ja3s_str, hash_string(ja3s_str)
