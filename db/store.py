"""Redis/Valkey-backed reference database of known JA3 fingerprints.

Stores two things per known hash: the label (exact-match lookup, fast,
what live_identify.py tries first) and the underlying field lists
(ciphers/extensions/curves/point_formats) that produced that hash —
needed for the similarity fallback in ja3/match.py, since exact-hash
matching alone breaks the moment a client's handshake shifts even
slightly (see README's fingerprint-instability findings).
"""
from __future__ import annotations

import json
from typing import Dict, Optional

import redis

KEY_PREFIX = "ja3:"
FIELDS_PREFIX = "ja3fields:"


class FingerprintStore:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self._r = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def add(self, ja3_hash: str, client_name: str, fields: Optional[dict] = None) -> None:
        self._r.set(KEY_PREFIX + ja3_hash, client_name)
        if fields is not None:
            self._r.set(FIELDS_PREFIX + ja3_hash, json.dumps(fields))

    def lookup(self, ja3_hash: str) -> Optional[str]:
        return self._r.get(KEY_PREFIX + ja3_hash)

    def all(self) -> Dict[str, str]:
        keys = self._r.keys(KEY_PREFIX + "*")
        return {k[len(KEY_PREFIX):]: self._r.get(k) for k in keys}

    def all_with_fields(self) -> Dict[str, dict]:
        """hash -> {"label": str, "fields": dict | None}, for every known hash."""
        result: Dict[str, dict] = {}
        for h, label in self.all().items():
            raw_fields = self._r.get(FIELDS_PREFIX + h)
            result[h] = {
                "label": label,
                "fields": json.loads(raw_fields) if raw_fields else None,
            }
        return result
