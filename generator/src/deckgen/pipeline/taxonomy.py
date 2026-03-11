from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from rich.console import Console

from deckgen.config import resolve_config
from deckgen.schemas import TAXONOMY_SCHEMA
from deckgen.utils.io import write_json
from deckgen.utils.openai_client import OpenAIClient, format_text_input
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import dummy_taxonomy

console = Console()


DEFAULT_CATEGORIES = [
    "Workforce",
    "Households",
    "Public Services",
    "Innovation",
    "Industry",
    "Energy",
    "Infrastructure",
    "Markets",
    "Security",
    "Governance",
]

DEFAULT_TAGS = [
    "productivity_growth",
    "wage_pressure",
    "job_reallocation",
    "unemployment_spike",
    "skills_transition",
    "small_business_adoption",
    "healthcare_access",
    "classroom_support",
    "housing_affordability",
    "construction_speed",
    "freight_efficiency",
    "local_service_quality",
    "caregiving_support",
    "data_governance",
    "energy_demand",
    "energy_prices",
    "grid_reliability",
    "compute_access",
    "research_breakthroughs",
    "robotics_rollout",
    "public_sector_capacity",
    "critical_infrastructure",
    "cyber_risk",
    "misinformation_pressure",
    "public_trust",
    "market_concentration",
    "tax_base_pressure",
    "income_support",
    "trade_realignment",
    "export_controls",
    "strategic_deterrence",
    "permitting_speed",
]


def generate_taxonomy(config: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    resolved = resolve_config(config)
    scenario = resolved.get("scenario", {})
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime.get("prompt_path")
    client = OpenAIClient()
    additional_instructions = scenario.get("additional_instructions", scenario.get("injection", ""))

    if client.use_dummy:
        taxonomy = dummy_taxonomy(resolved)
    else:
        prompt = render_prompt(
            "taxonomy.jinja",
            prompt_path=prompt_path,
            additional_instructions=additional_instructions,
            scenario_tone=scenario.get("tone", ""),
        )
        payload: dict[str, Any] = {
            "model": model_cfg.get("model"),
            "input": format_text_input(model_cfg.get("model"), prompt),
            "text": {
                "format": {"type": "json_schema", "name": "taxonomy", "schema": TAXONOMY_SCHEMA, "strict": True}
            },
        }
        if model_cfg.get("reasoning_effort"):
            payload["reasoning"] = {"effort": model_cfg["reasoning_effort"]}
        payload["store"] = model_cfg.get("store", False)
        response = client.responses(payload)
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
    normalized_categories = [category for category in normalized_categories if category in DEFAULT_CATEGORIES]
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
        "energy systems": "Energy",
        "power and energy": "Energy",
        "research and development": "Innovation",
        "research development": "Innovation",
        "r and d": "Innovation",
        "rnd": "Innovation",
        "industry": "Industry",
        "industry and commerce": "Industry",
        "commerce": "Industry",
        "business": "Industry",
        "ai safety": "Governance",
        "ai alignment": "Governance",
        "macroeconomics": "Markets",
        "macro economy": "Markets",
        "macro policy": "Markets",
        "financial markets": "Markets",
        "finance": "Markets",
        "defense and security": "Security",
        "national security": "Security",
        "foreign policy": "Governance",
        "diplomacy": "Governance",
        "public infrastructure": "Infrastructure",
        "critical infrastructure": "Infrastructure",
        "labor": "Workforce",
        "employment": "Workforce",
        "workers": "Workforce",
        "consumer": "Households",
        "families": "Households",
        "social policy": "Households",
        "public sector": "Public Services",
        "government services": "Public Services",
        "education": "Public Services",
        "healthcare": "Public Services",
        "culture": "Households",
        "statecraft": "Governance",
        "regulation": "Governance",
    }

    def _category_key(value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = cleaned.replace("&", "and")
        cleaned = cleaned.replace("/", " ")
        cleaned = cleaned.replace("_", " ")
        return " ".join(cleaned.split())

    canonical_map = {_category_key(item): item for item in DEFAULT_CATEGORIES}
    key = _category_key(category)
    if key in alias_map:
        return alias_map[key]
    return canonical_map.get(key, category.strip())


def _normalize_tag(tag: str) -> str:
    cleaned = tag.strip().lower().replace("/", "_").replace(" ", "_")
    return cleaned
