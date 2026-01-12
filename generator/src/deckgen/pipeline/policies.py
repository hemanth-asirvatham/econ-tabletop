from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from rich.console import Console
from tqdm import tqdm

from deckgen.config import resolve_config
from deckgen.schemas import POLICY_BLUEPRINT_SCHEMA, POLICY_CARD_SCHEMA, POLICY_CARDS_SCHEMA
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.io import write_jsonl
from deckgen.utils.openai_client import OpenAIClient
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import dummy_policy_blueprint, dummy_policy_cards

console = Console()


def generate_policies(config: dict[str, Any], taxonomy: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    resolved = resolve_config(config)
    scenario = resolved.get("scenario", {})
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime.get("prompt_path")
    total = resolved["deck_sizes"]["policies_total"]
    tags = taxonomy["tags"]
    categories = taxonomy["categories"]
    client = OpenAIClient()
    cache_dir = cache_dir_for(out_dir) if runtime.get("cache_requests", False) else None

    if client.use_dummy:
        blueprint = dummy_policy_blueprint(count=total, categories=categories, tags=tags)
        slots = blueprint["slots"]
        card_ids = [f"policy_{i:03d}" for i in range(total)]
        response = dummy_policy_cards(card_ids=card_ids, slots=slots, tags=tags)
        cards = response["cards"]
    else:
        blueprint_prompt = render_prompt(
            "policy_blueprint.jinja",
            prompt_path=prompt_path,
            scenario_injection=scenario.get("injection", ""),
            scenario_tone=scenario.get("tone", ""),
            target_count=total,
            categories=categories,
            tags=tags,
        )
        blueprint_payload = _build_text_payload(
            blueprint_prompt,
            model_cfg,
            POLICY_BLUEPRINT_SCHEMA,
            name="policy_blueprint",
        )
        blueprint_response = client.responses(blueprint_payload)
        if cache_dir:
            client.save_payload(cache_dir, "policy_blueprint", blueprint_payload, blueprint_response)
        blueprint = _parse_response_json(blueprint_response) or {}
        slots = _normalize_slots(blueprint.get("slots", []), total, categories, tags)

        card_ids = [f"policy_{i:03d}" for i in range(total)]
        cards_prompt = render_prompt(
            "policy_cards.jinja",
            prompt_path=prompt_path,
            scenario_injection=scenario.get("injection", ""),
            scenario_tone=scenario.get("tone", ""),
            categories=categories,
            tags=tags,
            slots=slots,
            card_ids=card_ids,
        )
        cards_payload = _build_text_payload(
            cards_prompt,
            model_cfg,
            POLICY_CARDS_SCHEMA,
            name="policy_cards",
        )
        cards_response = client.responses(cards_payload)
        if cache_dir:
            client.save_payload(cache_dir, "policy_cards", cards_payload, cards_response)
        response = _parse_response_json(cards_response) or {}
        cards = response.get("cards", [])

    cards = _normalize_policy_cards(cards, total, tags, categories)
    for index, card in enumerate(tqdm(cards, desc="Building policy art prompts")):
        card["id"] = f"policy_{index:03d}"
        card["art_prompt"] = render_prompt(
            "image_prompt_policy.jinja",
            prompt_path=prompt_path,
            card=card,
            scenario_injection=scenario.get("injection", ""),
            locale_visuals=scenario.get("locale_visuals", []),
        ).strip()
        Draft202012Validator(POLICY_CARD_SCHEMA).validate(card)

    write_jsonl(out_dir / "cards" / "policies.jsonl", cards)
    return cards


def _build_text_payload(prompt: str, model_cfg: dict[str, Any], schema: dict[str, Any], name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_cfg.get("model"),
        "input": prompt,
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        "store": model_cfg.get("store", False),
    }
    if model_cfg.get("max_output_tokens") is not None:
        payload["max_output_tokens"] = model_cfg["max_output_tokens"]
    if model_cfg.get("temperature") is not None:
        payload["temperature"] = model_cfg["temperature"]
    if model_cfg.get("top_p") is not None:
        payload["top_p"] = model_cfg["top_p"]
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
                    console.print("[yellow]Failed to parse policy JSON response.[/yellow]")
                    return None
    return None


def _normalize_slots(
    slots: list[dict[str, Any]], total: int, categories: list[str], tags: list[str]
) -> list[dict[str, Any]]:
    normalized = list(slots)
    for idx in range(total - len(normalized)):
        tag = tags[idx % len(tags)]
        category = categories[idx % len(categories)]
        normalized.append(
            {
                "slot_id": f"policy_slot_extra_{idx:03d}",
                "category": category,
                "theme": f"{category} policy lever for {tag.replace('_', ' ')}",
                "required_tags": [tag],
                "anti_duplicate_notes": "Provide a distinct intervention and stakeholder mix.",
            }
        )
    return normalized[:total]


def _normalize_policy_cards(
    cards: list[dict[str, Any]], total: int, tags: list[str], categories: list[str]
) -> list[dict[str, Any]]:
    normalized = list(cards)[:total]
    for idx in range(total - len(normalized)):
        tag = tags[idx % len(tags)]
        category = categories[idx % len(categories)]
        normalized.append(
            {
                "id": f"policy_{idx:03d}",
                "title": f"{tag.replace('_', ' ').title()} Initiative",
                "short_description": f"Targeted action on {tag.replace('_', ' ')}.",
                "description": "A grounded policy initiative aligned with the scenario context.",
                "category": category,
                "cost": {"budget_level": 3, "implementation_complexity": 3, "notes": "Balanced fiscal impact."},
                "timeline": {"time_to_launch": "months", "time_to_impact": "1-2y"},
                "impact_score": 3,
                "tags": [tag],
                "addresses_tags": [tag],
                "side_effect_tags": [],
                "prerequisites_policy_tags": [],
                "synergy_policy_tags": [],
                "role_restrictions": [],
                "art_prompt": "",
                "flavor_quote": "“Policy is how we steer technology toward shared prosperity.”",
            }
        )
    for card in normalized:
        if card.get("category") not in categories:
            card["category"] = categories[0]
        card_tags = card.get("tags") or [tags[0]]
        card["tags"] = [tag for tag in card_tags if tag in tags] or [tags[0]]
        if not card.get("addresses_tags"):
            card["addresses_tags"] = list(card["tags"])
    return normalized
