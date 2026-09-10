#!/usr/bin/env python3
"""Sniff live TLS traffic and identify clients by JA3 fingerprint lookup.

Usage:
    sudo python3 scripts/live_identify.py --iface en0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capture.sniffer import capture
from db.store import FingerprintStore
from ja3.ja3 import ja3_from_client_hello, ja3s_from_server_hello
from ja3.match import closest_match
from ja3.parser import parse_client_hello


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iface", default=None, help="capture interface")
    parser.add_argument("--similarity-threshold", type=float, default=0.7,
                         help="minimum score for a fuzzy match to be reported (0-1)")
    args = parser.parse_args()

    store = FingerprintStore()
    known = store.all_with_fields()  # snapshot at startup, used for the fuzzy fallback

    def on_client_hello(raw: bytes) -> None:
        result = ja3_from_client_hello(raw)
        if result is None:
            return
        _, ja3_hash = result

        exact_label = store.lookup(ja3_hash)
        if exact_label is not None:
            print(f"[ClientHello] JA3={ja3_hash} -> {exact_label}")
            return

        fields = parse_client_hello(raw)
        fuzzy = closest_match(fields, known, threshold=args.similarity_threshold)
        if fuzzy is not None:
            label, score = fuzzy
            print(f"[ClientHello] JA3={ja3_hash} -> ~{label} (no exact match, {score:.0%} similar)")
        else:
            print(f"[ClientHello] JA3={ja3_hash} -> unknown")

    def on_server_hello(raw: bytes) -> None:
        result = ja3s_from_server_hello(raw)
        if result is None:
            return
        _, ja3s_hash = result
        print(f"[ServerHello] JA3S={ja3s_hash}")

    print(f"Listening on {args.iface or 'default interface'}... Ctrl+C to stop.")
    capture(args.iface, on_client_hello, on_server_hello)


if __name__ == "__main__":
    main()
