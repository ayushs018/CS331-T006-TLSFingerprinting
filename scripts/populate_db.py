#!/usr/bin/env python3
"""Capture one ClientHello and store its JA3 hash under a client label.

Usage:
    sudo python3 scripts/populate_db.py --iface en0 --name "curl 8.4"

Then, in another terminal, generate the traffic to be fingerprinted, e.g.:
    curl -s https://example.com >/dev/null
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capture.sniffer import capture
from db.store import FingerprintStore
from ja3.ja3 import ja3_from_client_hello
from ja3.parser import parse_client_hello


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iface", default=None, help="capture interface")
    parser.add_argument("--name", required=True, help="label for this client")
    args = parser.parse_args()

    store = FingerprintStore()

    def on_client_hello(raw: bytes) -> None:
        result = ja3_from_client_hello(raw)
        if result is None:
            return
        ja3_str, ja3_hash = result
        fields = parse_client_hello(raw)
        print(f"Captured ClientHello -> JA3={ja3_hash}\n  {ja3_str}")
        store.add(ja3_hash, args.name, fields=fields)
        print(f"Stored as '{args.name}' (with fields, for similarity fallback matching)")
        raise SystemExit(0)

    print(
        f"Waiting for one ClientHello on {args.iface or 'default interface'}... "
        "generate traffic with your target client now."
    )
    capture(args.iface, on_client_hello, lambda raw: None, count=0)


if __name__ == "__main__":
    main()
