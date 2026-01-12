from __future__ import annotations

from pathlib import Path


def cache_dir_for(deck_dir: Path) -> Path:
    return deck_dir / "cache"
