"""Approximate matching, used when a captured fingerprint's exact hash
has never been seen before.

Exact JA3 hash matching is fragile: the same real client can produce a
different hash across sessions (session resumption, OS-level TLS stack
behavior, library updates — see README's curl findings). Rather than
just reporting "unknown" the moment one cipher shifts, compare the
*underlying field sets* of an unknown capture against every known
client's stored fields, and surface the closest match with a
similarity score — the operator decides whether to trust it, instead
of the system silently failing to recognize a client it actually knows.
"""
from __future__ import annotations

from typing import Optional


def jaccard_similarity(a: list[int], b: list[int]) -> float:
    """|intersection| / |union| of two value sets. 1.0 = identical sets, 0.0 = disjoint."""
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)


def field_similarity(fields_a: dict, fields_b: dict) -> float:
    """Weighted similarity across all 4 JA3 field lists (version must match exactly).

    Ciphers and extensions carry the most identifying signal (largest,
    most implementation-specific lists), so they're weighted higher
    than curves/point_formats, which are short and often shared across
    many clients.
    """
    if fields_a.get("version") != fields_b.get("version"):
        return 0.0

    weights = {"ciphers": 0.45, "extensions": 0.35, "curves": 0.15, "point_formats": 0.05}
    score = 0.0
    for field, weight in weights.items():
        score += weight * jaccard_similarity(fields_a.get(field, []), fields_b.get(field, []))
    return score


def closest_match(
    fields: dict,
    known: dict[str, dict],
    threshold: float = 0.7,
) -> Optional[tuple[str, float]]:
    """known: {hash: {"label": str, "fields": dict}}, as returned by
    FingerprintStore.all_with_fields(). Returns (label, score) for the
    best match at or above threshold, or None if nothing is close enough.
    """
    best_label: Optional[str] = None
    best_score = 0.0
    for entry in known.values():
        if entry["fields"] is None:
            continue
        score = field_similarity(fields, entry["fields"])
        if score > best_score:
            best_score = score
            best_label = entry["label"]

    if best_label is not None and best_score >= threshold:
        return best_label, best_score
    return None
