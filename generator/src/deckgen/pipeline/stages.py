from __future__ import annotations

from pathlib import Path
from typing import Any

import itertools
from jsonschema import Draft202012Validator
from rich.console import Console
from tqdm import tqdm

from deckgen.config import resolve_config
from deckgen.schemas import (
    DEVELOPMENT_CARD_SCHEMA,
    DEVELOPMENT_CARDS_SCHEMA,
    STAGE_BLUEPRINT_SCHEMA,
    STAGE_SUMMARY_SCHEMA,
)
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.io import write_json, write_jsonl
from deckgen.utils.openai_client import OpenAIClient, format_text_input
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import (
    dummy_development_cards,
    dummy_stage_blueprint,
    dummy_stage_summary,
)

console = Console()


def generate_stage_cards(config: dict[str, Any], taxonomy: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    resolved = resolve_config(config)
    scenario = resolved.get("scenario", {})
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime.get("prompt_path")
    tags = taxonomy["tags"]
    stages = resolved.get("stages", {}).get("definitions", [])
    stage_counts = resolved["deck_sizes"]["developments_per_stage"]
    client = OpenAIClient()
    cache_dir = cache_dir_for(out_dir) if runtime.get("cache_requests", False) else None

    summaries: list[dict[str, Any]] = []
    all_cards: list[dict[str, Any]] = []
    prior_summary: dict[str, Any] | None = None
    prior_card_ids: list[str] = []

    for stage_index, count in enumerate(stage_counts):
        stage_def = stages[min(stage_index, len(stages) - 1)] if stages else {"id": stage_index}
        console.print(f"[cyan]Generating stage {stage_index} with {count} development cards.[/cyan]")

        if client.use_dummy:
            blueprint = dummy_stage_blueprint(stage=stage_def, tags=tags, target_count=count)
        else:
            blueprint_prompt = render_prompt(
                "stage_blueprint.jinja",
                prompt_path=prompt_path,
                scenario_injection=scenario.get("injection", ""),
                stage=stage_def,
                prior_summaries=summaries,
                tags=tags,
                mix_targets=resolved.get("mix_targets", {}),
                target_count=count,
            )
            blueprint_payload = _build_text_payload(
                blueprint_prompt,
                model_cfg,
                STAGE_BLUEPRINT_SCHEMA,
                name=f"stage{stage_index}_blueprint",
            )
            blueprint_response = client.responses(blueprint_payload)
            if cache_dir:
                client.save_payload(cache_dir, f"stage{stage_index}_blueprint", blueprint_payload, blueprint_response)
            blueprint = _parse_response_json(blueprint_response) or {}

        threads = blueprint.get("threads", [])
        special_counts = blueprint.get("special_counts", {})
        beats = _build_beats(threads, count, prior_card_ids, tags, special_counts)
        card_ids = [f"dev_s{stage_index}_{i:02d}" for i in range(count)]

        if client.use_dummy:
            response = dummy_development_cards(
                card_ids=card_ids,
                stage_index=stage_index,
                beats=beats,
                tags=tags,
            )
        else:
            cards_prompt = render_prompt(
                "development_cards.jinja",
                prompt_path=prompt_path,
                scenario_injection=scenario.get("injection", ""),
                stage=stage_def,
                prior_summary=prior_summary,
                tags=tags,
                beats=beats,
                card_ids=card_ids,
            )
            cards_payload = _build_text_payload(
                cards_prompt,
                model_cfg,
                DEVELOPMENT_CARDS_SCHEMA,
                name=f"stage{stage_index}_cards",
            )
            cards_response = client.responses(cards_payload)
            if cache_dir:
                client.save_payload(cache_dir, f"stage{stage_index}_cards", cards_payload, cards_response)
            response = _parse_response_json(cards_response) or {}

        stage_cards = _normalize_dev_cards(
            response.get("cards", []),
            count,
            stage_index,
            tags,
            beats,
        )
        for idx, card in enumerate(tqdm(stage_cards, desc=f"Stage {stage_index} art prompts")):
            card["id"] = card_ids[idx]
            card["stage"] = stage_index
            card["art_prompt"] = render_prompt(
                "image_prompt_development.jinja",
                prompt_path=prompt_path,
                card=card,
                scenario_injection=scenario.get("injection", ""),
                locale_visuals=scenario.get("locale_visuals", []),
            ).strip()
            Draft202012Validator(DEVELOPMENT_CARD_SCHEMA).validate(card)

        write_jsonl(out_dir / "cards" / f"developments.stage{stage_index}.jsonl", stage_cards)
        all_cards.extend(stage_cards)
        prior_card_ids = [card["id"] for card in stage_cards]

        if client.use_dummy:
            summary = dummy_stage_summary(stage_index=stage_index, cards=stage_cards)
        else:
            summary_prompt = render_prompt(
                "stage_summary.jinja",
                prompt_path=prompt_path,
                scenario_injection=scenario.get("injection", ""),
                stage=stage_def,
                cards=stage_cards,
                prior_summary=prior_summary,
            )
            summary_payload = _build_text_payload(
                summary_prompt,
                model_cfg,
                STAGE_SUMMARY_SCHEMA,
                name=f"stage{stage_index}_summary",
            )
            summary_response = client.responses(summary_payload)
            if cache_dir:
                client.save_payload(cache_dir, f"stage{stage_index}_summary", summary_payload, summary_response)
            summary = _parse_response_json(summary_response) or {"stage": stage_index, "facts": [], "changes_vs_prior": []}
        summaries.append(summary)
        prior_summary = summary

    write_json(out_dir / "meta" / "stage_summaries.json", summaries)
    return all_cards


def _build_text_payload(prompt: str, model_cfg: dict[str, Any], schema: dict[str, Any], name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_cfg.get("model"),
        "input": format_text_input(model_cfg.get("model"), prompt),
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
                    console.print("[yellow]Failed to parse development JSON response.[/yellow]")
                    return None
    return None


def _build_beats(
    threads: list[dict[str, Any]],
    target_count: int,
    prior_card_ids: list[str],
    tags: list[str],
    special_counts: dict[str, Any],
) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    for thread in threads:
        beat_plan = thread.get("beat_plan") or []
        repeat = max(1, thread.get("target_count", len(beat_plan) or 1))
        for beat in itertools.islice(itertools.cycle(beat_plan or ["New development"]), repeat):
            beats.append(
                {
                    "thread_id": thread.get("thread_id", "thread"),
                    "beat": beat,
                    "valence_target": thread.get("valence_target", "mixed"),
                }
            )

    if len(beats) < target_count:
        fallback = {"thread_id": "thread_fill", "beat": "Supplementary development", "valence_target": "mixed"}
        beats.extend([fallback] * (target_count - len(beats)))
    beats = beats[:target_count]

    directives = (
        ["supersedes"] * int(special_counts.get("supersedes", 0))
        + ["conditional"] * int(special_counts.get("conditional", 0))
        + ["powerup"] * int(special_counts.get("powerups", 0))
        + ["quantitative_indicator"] * int(special_counts.get("quantitative_indicators", 0))
    )
    for beat, directive in zip(beats, directives):
        beat["special_directive"] = directive
        beat["supersedes_candidates"] = prior_card_ids[:5]
    for idx, beat in enumerate(beats):
        beat["primary_tag"] = tags[idx % len(tags)]
    return beats


def _normalize_dev_cards(
    cards: list[dict[str, Any]],
    target_count: int,
    stage_index: int,
    tags: list[str],
    beats: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = list(cards)[:target_count]
    for idx in range(target_count - len(normalized)):
        tag = tags[idx % len(tags)]
        normalized.append(
            {
                "id": f"dev_s{stage_index}_{idx:02d}",
                "stage": stage_index,
                "title": f"Stage {stage_index} {tag.replace('_', ' ').title()} Shift",
                "short_description": f"Observed shift in {tag.replace('_', ' ')}.",
                "description": "Grounded development reflecting AI deployment trends and measurable economic impacts.",
                "valence": "mixed",
                "arrows_up": 2,
                "arrows_down": 1,
                "severity": 3,
                "tags": [tag],
                "thread_id": beats[idx % len(beats)]["thread_id"],
                "supersedes": None,
                "activation": {"type": "immediate", "required_policy_tags": []},
                "effects": [],
                "art_prompt": "",
                "suggested_visibility": "either",
            }
        )
    for idx, card in enumerate(normalized):
        card_tags = card.get("tags") or [tags[0]]
        card["tags"] = [tag for tag in card_tags if tag in tags] or [tags[0]]
        beat = beats[idx]
        directive = beat.get("special_directive")
        if not card.get("activation"):
            card["activation"] = {"type": "immediate", "required_policy_tags": []}
        if card.get("effects") is None:
            card["effects"] = []
        if directive == "conditional":
            card.setdefault("activation", {})["type"] = "conditional"
            if not card.get("activation", {}).get("required_policy_tags"):
                card["activation"]["required_policy_tags"] = [card["tags"][0]]
        if directive == "powerup" and not card.get("effects"):
            card["effects"] = [{"type": "DRAW_DEV_NOW", "params": {"count": 1, "stage_offset": 0}}]
        if directive == "supersedes" and not card.get("supersedes"):
            supersedes_candidates = beat.get("supersedes_candidates") or []
            card["supersedes"] = supersedes_candidates[0] if supersedes_candidates else None
        if directive == "quantitative_indicator" and card.get("short_description"):
            if not any(char.isdigit() for char in card["short_description"]):
                card["short_description"] = f"{card['short_description']} (+1.0%)"
    return normalized
