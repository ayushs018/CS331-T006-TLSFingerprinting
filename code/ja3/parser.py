"""Raw TLS handshake byte parsing for JA3/JA3S field extraction.

Only extracts the fields JA3 needs. Assumes the full handshake message
is present in the given bytes (see capture/sniffer.py for the
single-TCP-segment limitation).
"""
from __future__ import annotations

from typing import Optional

CONTENT_TYPE_HANDSHAKE = 0x16
HANDSHAKE_TYPE_CLIENT_HELLO = 0x01
HANDSHAKE_TYPE_SERVER_HELLO = 0x02

EXT_SUPPORTED_GROUPS = 10  # aka "elliptic_curves"
EXT_EC_POINT_FORMATS = 11


def _u16(b: bytes, off: int) -> int:
    return (b[off] << 8) | b[off + 1]


def parse_client_hello(raw: bytes) -> Optional[dict]:
    try:
        if raw[0] != CONTENT_TYPE_HANDSHAKE or raw[5] != HANDSHAKE_TYPE_CLIENT_HELLO:
            return None

        version = _u16(raw, 9)
        off = 11 + 32  # skip 2-byte version + 32-byte random

        session_id_len = raw[off]
        off += 1 + session_id_len

        ciphers_len = _u16(raw, off)
        off += 2
        ciphers = [_u16(raw, off + i) for i in range(0, ciphers_len, 2)]
        off += ciphers_len

        comp_len = raw[off]
        off += 1 + comp_len

        extensions: list[int] = []
        curves: list[int] = []
        point_formats: list[int] = []

        if off < len(raw):
            ext_total_len = _u16(raw, off)
            off += 2
            end = off + ext_total_len
            while off < end:
                ext_type = _u16(raw, off)
                ext_len = _u16(raw, off + 2)
                ext_data_off = off + 4
                extensions.append(ext_type)

                if ext_type == EXT_SUPPORTED_GROUPS:
                    list_len = _u16(raw, ext_data_off)
                    curves = [
                        _u16(raw, ext_data_off + 2 + i) for i in range(0, list_len, 2)
                    ]
                elif ext_type == EXT_EC_POINT_FORMATS:
                    list_len = raw[ext_data_off]
                    point_formats = list(
                        raw[ext_data_off + 1 : ext_data_off + 1 + list_len]
                    )

                off = ext_data_off + ext_len

        return {
            "version": version,
            "ciphers": ciphers,
            "extensions": extensions,
            "curves": curves,
            "point_formats": point_formats,
        }
    except (IndexError, ValueError):
        return None


def parse_server_hello(raw: bytes) -> Optional[dict]:
    try:
        if raw[0] != CONTENT_TYPE_HANDSHAKE or raw[5] != HANDSHAKE_TYPE_SERVER_HELLO:
            return None

        version = _u16(raw, 9)
        off = 11 + 32

        session_id_len = raw[off]
        off += 1 + session_id_len

        cipher = _u16(raw, off)
        off += 2
        off += 1  # compression method

        extensions: list[int] = []
        if off < len(raw):
            ext_total_len = _u16(raw, off)
            off += 2
            end = off + ext_total_len
            while off < end:
                ext_type = _u16(raw, off)
                ext_len = _u16(raw, off + 2)
                extensions.append(ext_type)
                off += 4 + ext_len

        return {"version": version, "cipher": cipher, "extensions": extensions}
    except (IndexError, ValueError):
        return None
