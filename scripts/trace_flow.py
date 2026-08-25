#!/usr/bin/env python3
"""Capture one ClientHello and print every intermediate step of the
JA3 pipeline explicitly: raw bytes -> parsed fields -> GREASE-stripped
lists -> JA3 string -> MD5 hash -> Redis lookup -> final label.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capture.sniffer import capture
from db.store import FingerprintStore
from ja3.ja3 import _strip_grease, ja3_string_from_fields, hash_string
from ja3.parser import parse_client_hello


def on_client_hello(raw: bytes) -> None:
    print("STEP 1 — raw bytes captured off the wire")
    print(f"  {len(raw)} bytes total")
    print(f"  first 16 bytes (hex): {raw[:16].hex(' ')}")

    print("\nSTEP 2 — parser.py walks the TLS record byte layout")
    fields = parse_client_hello(raw)
    print(f"  version        = {fields['version']}   (from bytes 9-10)")
    print(f"  ciphers        = {fields['ciphers']}")
    print(f"  extensions     = {fields['extensions']}")
    print(f"  curves         = {fields['curves']}")
    print(f"  point_formats  = {fields['point_formats']}")

    print("\nSTEP 3 — strip GREASE values (RFC 8701 junk values) before hashing")
    print(f"  ciphers    before: {fields['ciphers']}")
    print(f"  ciphers    after:  {_strip_grease(fields['ciphers'])}")
    print(f"  extensions before: {fields['extensions']}")
    print(f"  extensions after:  {_strip_grease(fields['extensions'])}")

    print("\nSTEP 4 — join into the JA3 string (version,ciphers,ext,curves,points)")
    ja3_str = ja3_string_from_fields(
        fields["version"], fields["ciphers"], fields["extensions"],
        fields["curves"], fields["point_formats"],
    )
    print(f"  {ja3_str}")

    print("\nSTEP 5 — MD5 hash of that exact string")
    ja3_hash = hash_string(ja3_str)
    print(f"  hashlib.md5(b'{ja3_str[:40]}...').hexdigest()")
    print(f"  = {ja3_hash}")

    print("\nSTEP 6 — look up that hash in Redis (db/store.py)")
    store = FingerprintStore()
    label = store.lookup(ja3_hash)
    print(f"  redis GET ja3:{ja3_hash}")
    print(f"  -> {label!r}")

    print(f"\nFINAL LINE PRINTED: [ClientHello] JA3={ja3_hash} -> {label or 'unknown'}")
    raise SystemExit(0)


if __name__ == "__main__":
    print("Waiting for one ClientHello on en0 (run curl in another terminal)...\n")
    capture("en0", on_client_hello, lambda raw: None, count=0)
