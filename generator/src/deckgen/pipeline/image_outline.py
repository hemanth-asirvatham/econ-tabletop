from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from deckgen.config import resolve_config
from deckgen.utils.openai_client import OpenAIClient, format_text_input
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import dummy_image_outline

console = Console()


def generate_image_outline(
    config: dict[str, Any],
    outline_text: str,
    out_dir: Path,
    *,
    reuse_existing: bool = True,
) -> str:
    resolved = resolve_config(config)
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime.get("prompt_path")

    image_outline_path = out_dir / "meta" / "image_outline.txt"
    if reuse_existing and image_outline_path.exists():
        console.print(f"[green]Image outline already exists; loading from {image_outline_path}.[/green]")
        return image_outline_path.read_text(encoding="utf-8")

    console.print("[cyan]Generating concise image-format outline.[/cyan]")
    client = OpenAIClient()

    outline_prompt = render_prompt(
        "image_outline.jinja",
        prompt_path=prompt_path,
        outline_text=outline_text,
    )

    image_outline = ""
    if client.use_dummy:
        image_outline = dummy_image_outline()
    else:
        payload = _build_text_payload(outline_prompt, model_cfg)
        response = client.responses(payload)
        image_outline = _parse_response_text(response) or ""

    if not image_outline:
        console.print("[yellow]Image outline response was empty; falling back to dummy outline.[/yellow]")
        image_outline = dummy_image_outline()

    image_outline_path.parent.mkdir(parents=True, exist_ok=True)
    image_outline_path.write_text(image_outline, encoding="utf-8")
    console.print("[green]Image outline generation complete.[/green]")
    return image_outline


def _build_text_payload(prompt: str, model_cfg: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_cfg.get("model"),
        "input": format_text_input(model_cfg.get("model"), prompt),
        "store": model_cfg.get("store", False),
    }
    if model_cfg.get("reasoning_effort"):
        payload["reasoning"] = {"effort": model_cfg["reasoning_effort"]}
    return payload


def _parse_response_text(response: dict[str, Any]) -> str | None:
    for output in response.get("output", []):
        for item in output.get("content", []):
            text = item.get("text")
            if text:
                return text
    return None
