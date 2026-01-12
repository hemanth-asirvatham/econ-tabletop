from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def generate_images(config: dict[str, Any], policies: list[dict[str, Any]], developments: list[dict[str, Any]], out_dir: Path) -> None:
    console.print("[cyan]Image generation placeholder.[/cyan]")
    console.print(f"Would generate {len(policies)} policy images and {len(developments)} development images.")
    (out_dir / "render" / "thumbs").mkdir(parents=True, exist_ok=True)
