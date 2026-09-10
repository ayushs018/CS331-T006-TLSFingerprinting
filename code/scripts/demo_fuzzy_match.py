#!/usr/bin/env python3
"""Proves the fuzzy-match fallback works, using the OTHER real curl
fingerprint captured earlier in this project's history (13 cipher
suites, no ALPN) — a genuinely different JA3 hash than the one
currently stored, reconstructed from that earlier real capture's
JA3 string, not fabricated.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.store import FingerprintStore
from ja3.ja3 import hash_string
from ja3.match import closest_match

# The real string captured earlier: "curl" -> b76d503360ae441d410a85a7f8d648ab
OLD_CURL_JA3_STRING = (
    "771,4865-4866-4867-49196-49195-52393-49200-49199-52392-49162-49161-49172-49171,"
    "0-23-65281-10-11-16-5-13-18-51-45-43-27-21,29-23-24-25,0"
)


def fields_from_ja3_string(s: str) -> dict:
    version, ciphers, extensions, curves, points = s.split(",")
    return {
        "version": int(version),
        "ciphers": [int(x) for x in ciphers.split("-")],
        "extensions": [int(x) for x in extensions.split("-")],
        "curves": [int(x) for x in curves.split("-")],
        "point_formats": [int(x) for x in points.split("-")],
    }


def main() -> None:
    old_curl_hash = hash_string(OLD_CURL_JA3_STRING)
    old_curl_fields = fields_from_ja3_string(OLD_CURL_JA3_STRING)

    print(f"Simulated 'new' capture: the OLD real curl variant")
    print(f"  JA3 hash: {old_curl_hash}")
    print(f"  ciphers:  {len(old_curl_fields['ciphers'])} suites")

    store = FingerprintStore()
    known = store.all_with_fields()

    exact = store.lookup(old_curl_hash)
    print(f"\nExact-match lookup: {exact!r}")

    result = closest_match(old_curl_fields, known, threshold=0.5)
    if result:
        label, score = result
        print(f"Fuzzy-match fallback: -> {label} ({score:.1%} similar)")
    else:
        print("Fuzzy-match fallback: no match above threshold")

    print("\n--- similarity against every known client, for context ---")
    from ja3.match import field_similarity
    for h, entry in known.items():
        if entry["fields"] is None:
            continue
        s = field_similarity(old_curl_fields, entry["fields"])
        print(f"  {entry['label']:<28} {s:.1%}")


if __name__ == "__main__":
    main()
