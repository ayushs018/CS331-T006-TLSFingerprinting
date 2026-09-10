#!/usr/bin/env python3
"""Capture one ClientHello and print both its raw bytes and an
annotated byte-by-byte breakdown of the TLS record — makes the layout
`ja3/parser.py` walks actually visible instead of abstract.

Usage:
    python3 scripts/dump_record.py --iface en0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capture.sniffer import capture
from ja3.parser import parse_client_hello
from ja3.ja3 import ja3_from_client_hello


def hex_dump(raw: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(raw), width):
        chunk = raw[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:04x}  {hex_part:<{width*3}}  {ascii_part}")
    return "\n".join(lines)


def annotate(raw: bytes) -> str:
    fields = parse_client_hello(raw)
    session_id_len = raw[43]
    off = 44 + session_id_len
    ciphers_len = (raw[off] << 8) | raw[off + 1]

    rows = [
        ("0",        "1",  "Content Type",       f"0x{raw[0]:02x} (Handshake)"),
        ("1-2",      "2",  "Record Version",     f"0x{raw[1]:02x}{raw[2]:02x}"),
        ("3-4",      "2",  "Record Length",      str((raw[3] << 8) | raw[4])),
        ("5",        "1",  "Handshake Type",     f"0x{raw[5]:02x} (ClientHello)"),
        ("6-8",      "3",  "Handshake Length",   str((raw[6] << 16) | (raw[7] << 8) | raw[8])),
        ("9-10",     "2",  "Client Version",     f"0x{raw[9]:02x}{raw[10]:02x} (TLS {fields['version']})"),
        ("11-42",    "32", "Random",             raw[11:43].hex()),
        ("43",       "1",  "Session ID Length",  str(session_id_len)),
        (f"{44}-{off-1}" if session_id_len else "-", str(session_id_len), "Session ID", raw[44:off].hex() or "(empty)"),
        (f"{off}-{off+1}", "2", "Cipher Suites Length", str(ciphers_len)),
        (f"{off+2}-{off+1+ciphers_len}", str(ciphers_len), "Cipher Suites", f"{len(fields['ciphers'])} suites"),
    ]

    out = ["Byte(s)".ljust(12) + "Len".ljust(5) + "Field".ljust(20) + "Value"]
    out.append("-" * 70)
    for byte_range, length, field, value in rows:
        out.append(f"{byte_range:<12}{length:<5}{field:<20}{value}")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iface", default=None)
    args = parser.parse_args()

    def on_client_hello(raw: bytes) -> None:
        print(f"\n{'='*70}\nCaptured ClientHello: {len(raw)} bytes\n{'='*70}\n")
        print("--- Raw hex dump ---\n")
        print(hex_dump(raw))
        print("\n--- Annotated TLS record layout ---\n")
        print(annotate(raw))
        result = ja3_from_client_hello(raw)
        if result:
            ja3_str, ja3_hash = result
            print(f"\n--- Derived JA3 ---\n\nJA3 string: {ja3_str}\nJA3 hash:   {ja3_hash}")
        raise SystemExit(0)

    print(f"Waiting for one ClientHello on {args.iface or 'default interface'}...")
    capture(args.iface, on_client_hello, lambda raw: None, count=0)


if __name__ == "__main__":
    main()
