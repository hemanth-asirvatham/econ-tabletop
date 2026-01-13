from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from deckgen.config import resolve_config
from deckgen.schemas import SIMULATION_OUTLINE_SCHEMA
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.io import read_json, write_json
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
) -> dict[str, Any]:
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

    outline_path = out_dir / "meta" / "simulation_outline.json"
    outline_md_path = out_dir / "meta" / "simulation_outline.md"
    if reuse_existing and outline_path.exists():
        console.print(f"[green]Simulation outline already exists; loading from {outline_path}.[/green]")
        return read_json(outline_path)

    client = OpenAIClient()
    cache_dir = cache_dir_for(out_dir) if runtime.get("cache_requests", False) else None

    if client.use_dummy:
        outline = dummy_simulation_outline(
            stages=stages,
            categories=categories,
            tags=tags,
        )
    else:
        outline_prompt = render_prompt(
            "simulation_outline.jinja",
            prompt_path=prompt_path,
            scenario_injection=scenario.get("injection", ""),
            stages=stages,
            deck_sizes=deck_sizes,
            categories=categories,
            tags=tags,
            mix_targets=mix_targets,
        )
        outline_payload = _build_text_payload(
            outline_prompt,
            model_cfg,
            SIMULATION_OUTLINE_SCHEMA,
            name="simulation_outline",
        )
        outline_response = client.responses(outline_payload)
        if cache_dir:
            client.save_payload(cache_dir, "simulation_outline", outline_payload, outline_response)
        outline = _parse_response_json(outline_response) or {}

    write_json(outline_path, outline)
    if outline_md := outline.get("document_markdown"):
        outline_md_path.write_text(outline_md, encoding="utf-8")
    return outline


def _build_text_payload(prompt: str, model_cfg: dict[str, Any], schema: dict[str, Any], name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_cfg.get("model"),
        "input": format_text_input(model_cfg.get("model"), prompt),
        "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
        "store": model_cfg.get("store", False),
    }
    if model_cfg.get("reasoning_effort"):
        payload["reasoning"] = {"effort": model_cfg["reasoning_effort"]}
    return payload


def _parse_response_json(response: dict[str, Any]) -> dict[str, Any] | None:
    import json

    for output in response.get("output", []):
        for item in output.get("content", []):
            if item.get("json") and isinstance(item["json"], dict):
                return item["json"]
            text = item.get("text") or item.get("json") or ""
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    console.print("[yellow]Failed to parse simulation outline JSON response.[/yellow]")
                    return None
    return None
