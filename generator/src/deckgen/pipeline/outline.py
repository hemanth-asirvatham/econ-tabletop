from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from deckgen.config import resolve_config
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.openai_client import OpenAIClient, format_text_input
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import dummy_simulation_outline

console = Console()


def generate_simulation_outline(
    config: dict[str, Any],
    taxonomy: dict[str, Any],
    out_dir: Path,
    *,
    reuse_existing: bool = True,
) -> str:
    resolved = resolve_config(config)
    scenario = resolved.get("scenario", {})
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime.get("prompt_path")
    deck_sizes = resolved.get("deck_sizes", {})
    stages = resolved.get("stages", {}).get("definitions", [])
    mix_targets = resolved.get("mix_targets", {})
    categories = taxonomy.get("categories", [])
    tags = taxonomy.get("tags", [])
    additional_instructions = scenario.get("additional_instructions", scenario.get("injection", ""))

    outline_txt_path = out_dir / "meta" / "simulation_outline.txt"
    outline_md_path = out_dir / "meta" / "simulation_outline.md"
    if reuse_existing and outline_txt_path.exists():
        console.print(f"[green]Simulation outline already exists; loading from {outline_txt_path}.[/green]")
        return outline_txt_path.read_text(encoding="utf-8")

    console.print("[cyan]Starting simulation outline generation.[/cyan]")
    client = OpenAIClient()
    cache_dir = cache_dir_for(out_dir) if runtime.get("cache_requests", False) else None

    outline_prompt = render_prompt(
        "simulation_outline.jinja",
        prompt_path=prompt_path,
        additional_instructions=additional_instructions,
        stages=stages,
        deck_sizes=deck_sizes,
        categories=categories,
        tags=tags,
        mix_targets=mix_targets,
    )
    outline_model_override = runtime.get("outline_model")
    outline_model_cfg = dict(model_cfg)
    if outline_model_override:
        outline_model_cfg["model"] = outline_model_override
    outline_text = ""
    if client.use_dummy:
        outline_text = dummy_simulation_outline(
            stages=stages,
            categories=categories,
            tags=tags,
        )
    else:
        outline_payload = _build_text_payload(outline_prompt, outline_model_cfg)
        outline_response = client.responses(outline_payload)
        if cache_dir:
            client.save_payload(cache_dir, "simulation_outline", outline_payload, outline_response)
        outline_text = _parse_response_text(outline_response) or ""

    if not outline_text:
        console.print("[yellow]Simulation outline response was empty; falling back to dummy outline.[/yellow]")
        outline_text = dummy_simulation_outline(stages=stages, categories=categories, tags=tags)

    outline_txt_path.parent.mkdir(parents=True, exist_ok=True)
    outline_txt_path.write_text(outline_text, encoding="utf-8")
    outline_md_path.write_text(outline_text, encoding="utf-8")
    console.print("[green]Simulation outline generation complete.[/green]")
    return outline_text


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
