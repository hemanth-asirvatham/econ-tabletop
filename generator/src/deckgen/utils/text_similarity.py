from __future__ import annotations

import difflib


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()
