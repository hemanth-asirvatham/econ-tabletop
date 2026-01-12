from __future__ import annotations

from pathlib import Path
from typing import Any
import base64

from rich.console import Console

from deckgen.config import resolve_config
from deckgen.utils.openai_client import OpenAIClient

console = Console()


_DUMMY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/xcAAwMCAOqf2m0AAAAASUVORK5CYII="
)


def generate_images(
    config: dict[str, Any],
    policies: list[dict[str, Any]],
    developments: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    resolved = resolve_config(config)
    image_cfg = resolved.get("models", {}).get("image", {})
    runtime_cfg = resolved.get("runtime", {})
    model = image_cfg.get("model")
    size = image_cfg.get("size")
    background = image_cfg.get("background")
    cache_requests = runtime_cfg.get("cache_requests", False)

    console.print(f"[cyan]Generating {len(policies)} policy images and {len(developments)} development images.[/cyan]")
    policy_dir = out_dir / "images" / "policy"
    dev_dir = out_dir / "images" / "development"
    thumbs_dir = out_dir / "render" / "thumbs"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    cache_dir = out_dir / "cache" if cache_requests else None
    client = OpenAIClient()

    for card in policies:
        _generate_card_image(
            card=card,
            out_path=policy_dir / f"{card['id']}.png",
            client=client,
            model=model,
            size=size,
            background=background,
            cache_dir=cache_dir,
        )
    for card in developments:
        _generate_card_image(
            card=card,
            out_path=dev_dir / f"{card['id']}.png",
            client=client,
            model=model,
            size=size,
            background=background,
            cache_dir=cache_dir,
        )


def _generate_card_image(
    *,
    card: dict[str, Any],
    out_path: Path,
    client: OpenAIClient,
    model: str | None,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
) -> None:
    prompt = card.get("art_prompt") or f"Horizontal illustration for {card.get('title', 'card')}."
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
    }
    if size is not None:
        payload["size"] = size
    if background is not None:
        payload["background"] = background
    response = client.images_generate(payload)
    if cache_dir:
        client.save_payload(cache_dir, f"image_{card['id']}", payload, response)

    data = (response.get("data") or [{}])[0].get("b64_json") or _DUMMY_PNG_BASE64
    out_path.write_bytes(base64.b64decode(data))
