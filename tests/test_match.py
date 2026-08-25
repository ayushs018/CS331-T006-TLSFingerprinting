"""Unit tests for the similarity-matching fallback.

Expected values computed independently before being hardcoded here.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ja3.match import closest_match, field_similarity, jaccard_similarity


def test_jaccard_similarity_basic_cases():
    assert jaccard_similarity([1, 2, 3], [2, 3, 4]) == 0.5
    assert jaccard_similarity([1, 2], [1, 2]) == 1.0
    assert jaccard_similarity([1, 2], [3, 4]) == 0.0
    assert jaccard_similarity([], []) == 1.0


def test_field_similarity_weighted_score():
    fields_a = {"version": 771, "ciphers": [1, 2, 3, 4], "extensions": [10, 20],
                "curves": [29, 23], "point_formats": [0]}
    fields_b = {"version": 771, "ciphers": [1, 2, 3, 5], "extensions": [10, 20],
                "curves": [29, 23], "point_formats": [0]}

    assert round(field_similarity(fields_a, fields_b), 4) == 0.82


def test_field_similarity_zero_on_version_mismatch():
    fields_a = {"version": 771, "ciphers": [1, 2], "extensions": [], "curves": [], "point_formats": []}
    fields_b = {"version": 772, "ciphers": [1, 2], "extensions": [], "curves": [], "point_formats": []}
    assert field_similarity(fields_a, fields_b) == 0.0


def test_closest_match_finds_best_above_threshold():
    unknown = {"version": 771, "ciphers": [1, 2, 3, 4], "extensions": [10, 20],
               "curves": [29, 23], "point_formats": [0]}
    known = {
        "hashA": {"label": "close-client", "fields": {
            "version": 771, "ciphers": [1, 2, 3, 5], "extensions": [10, 20],
            "curves": [29, 23], "point_formats": [0],
        }},
        "hashB": {"label": "far-client", "fields": {
            "version": 771, "ciphers": [99, 98, 97], "extensions": [1],
            "curves": [1], "point_formats": [1],
        }},
    }

    label, score = closest_match(unknown, known, threshold=0.7)
    assert label == "close-client"
    assert round(score, 4) == 0.82


def test_closest_match_returns_none_below_threshold():
    unknown = {"version": 771, "ciphers": [1, 2, 3, 4], "extensions": [10, 20],
               "curves": [29, 23], "point_formats": [0]}
    known = {
        "hashB": {"label": "far-client", "fields": {
            "version": 771, "ciphers": [99, 98, 97], "extensions": [1],
            "curves": [1], "point_formats": [1],
        }},
    }

    assert closest_match(unknown, known, threshold=0.7) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
