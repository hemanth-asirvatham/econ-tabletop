from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from rich.console import Console

from deckgen.config import resolve_config
from deckgen.schemas import TAXONOMY_SCHEMA
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.io import write_json
from deckgen.utils.openai_client import OpenAIClient, format_text_input
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import dummy_taxonomy

console = Console()


DEFAULT_CATEGORIES = [
    "macro",
    "labor",
    "firm_dynamics",
    "inequality_welfare",
    "education",
    "geopolitics",
    "infra_energy",
    "trust_misinfo",
    "governance_capacity",
    "frontier_rd",
    "safety_security",
]

DEFAULT_TAGS = [
    "productivity_growth",
    "wage_dispersion",
    "job_displacement",
    "skills_mismatch",
    "automation_adoption",
    "ai_capital_investment",
    "data_governance",
    "critical_infrastructure",
    "energy_demand",
    "ai_safety_incidents",
    "cyber_escalation",
    "misinformation_spike",
    "regional_competitiveness",
    "public_trust",
    "government_capacity",
    "procurement_modernization",
    "frontier_research",
    "compute_supply",
    "innovation_spillovers",
    "export_competitiveness",
    "labor_mobility",
    "education_alignment",
    "ai_regulation",
    "social_safety_net",
    "market_concentration",
]


def generate_taxonomy(config: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    resolved = resolve_config(config)
    scenario = resolved.get("scenario", {})
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime.get("prompt_path")
    client = OpenAIClient()
    cache_dir = cache_dir_for(out_dir) if runtime.get("cache_requests", False) else None

    if client.use_dummy:
        taxonomy = dummy_taxonomy(resolved)
    else:
        prompt = render_prompt(
            "taxonomy.jinja",
            prompt_path=prompt_path,
            scenario_injection=scenario.get("injection", ""),
            scenario_tone=scenario.get("tone", ""),
        )
        payload: dict[str, Any] = {
            "model": model_cfg.get("model"),
            "input": format_text_input(model_cfg.get("model"), prompt),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "taxonomy", "schema": TAXONOMY_SCHEMA, "strict": True},
            },
        }
        if model_cfg.get("max_output_tokens") is not None:
            payload["max_output_tokens"] = model_cfg["max_output_tokens"]
        if model_cfg.get("temperature") is not None:
            payload["temperature"] = model_cfg["temperature"]
        if model_cfg.get("top_p") is not None:
            payload["top_p"] = model_cfg["top_p"]
        if model_cfg.get("reasoning_effort"):
            payload["reasoning"] = {"effort": model_cfg["reasoning_effort"]}
        payload["store"] = model_cfg.get("store", False)
        response = client.responses(payload)
        if cache_dir:
            client.save_payload(cache_dir, "taxonomy", payload, response)
        content = _extract_response_text(response)
        taxonomy = _safe_json_loads(content) or {}

    taxonomy = _normalize_taxonomy(taxonomy, resolved)
    Draft202012Validator(TAXONOMY_SCHEMA).validate(taxonomy)
    write_json(out_dir / "meta" / "taxonomy.json", taxonomy)
    write_json(out_dir / "meta" / "tags.json", {"tags": taxonomy["tags"]})
    return taxonomy


def _extract_response_text(response: dict[str, Any]) -> str:
    for output in response.get("output", []):
        for item in output.get("content", []):
            if item.get("json") and isinstance(item["json"], dict):
                import json

                return json.dumps(item["json"])
            if "text" in item:
                return item["text"]
            if item.get("type") == "output_text":
                return item.get("text", "")
            if item.get("type") == "output_json":
                return item.get("json", "")
    return ""


def _safe_json_loads(content: str) -> dict[str, Any] | None:
    import json

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        console.print("[yellow]Failed to parse taxonomy JSON. Falling back to defaults.[/yellow]")
        return None


def _normalize_taxonomy(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    categories = payload.get("categories") or DEFAULT_CATEGORIES
    tags = payload.get("tags") or DEFAULT_TAGS
    normalized_categories = []
    for category in categories:
        normalized = _normalize_category(category)
        if normalized not in normalized_categories:
            normalized_categories.append(normalized)
    for required in DEFAULT_CATEGORIES:
        if required not in normalized_categories:
            normalized_categories.append(required)
    normalized_tags = []
    for tag in tags:
        normalized = _normalize_tag(tag)
        if normalized not in normalized_tags:
            normalized_tags.append(normalized)
    roles = payload.get("roles") or config.get("scenario", {}).get("roles", [])
    return {
        "categories": normalized_categories,
        "tags": normalized_tags,
        "roles": roles,
    }


def _normalize_category(category: str) -> str:
    alias_map = {
        "firm dynamics": "firm_dynamics",
        "inequality/welfare": "inequality_welfare",
        "infra/energy": "infra_energy",
        "trust/misinfo": "trust_misinfo",
        "governance capacity": "governance_capacity",
        "frontier r&d": "frontier_rd",
        "safety/security": "safety_security",
    }
    cleaned = category.strip().lower()
    cleaned = alias_map.get(cleaned, cleaned)
    cleaned = cleaned.replace("&", "and")
    cleaned = cleaned.replace("/", "_").replace(" ", "_")
    return cleaned


def _normalize_tag(tag: str) -> str:
    cleaned = tag.strip().lower().replace("/", "_").replace(" ", "_")
    return cleaned
