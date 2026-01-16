from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncio
import itertools
from jsonschema import Draft202012Validator
from rich.console import Console

from deckgen.config import resolve_config
from deckgen.schemas import (
    DEVELOPMENT_CARD_SCHEMA,
    DEVELOPMENT_CARDS_SCHEMA,
    DEVELOPMENT_CARDS_RESPONSE_SCHEMA,
    STAGE_BLUEPRINT_SCHEMA,
    STAGE_SUMMARY_SCHEMA,
)
from deckgen.utils.io import read_jsonl, write_json, write_jsonl
from deckgen.utils.openai_client import OpenAIClient, format_text_input
from deckgen.utils.asyncio_utils import run_async
from deckgen.utils.parallel import gather_with_concurrency
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import (
    dummy_development_cards,
    dummy_stage_blueprint,
    dummy_stage_summary,
)

console = Console()


def generate_stage_cards(
    config: dict[str, Any],
    taxonomy: dict[str, Any],
    outline_text: str,
    image_outline_text: str,
    out_dir: Path,
    *,
    reuse_existing: bool = True,
) -> list[dict[str, Any]]:
    resolved = resolve_config(config)
    scenario = resolved.get("scenario", {})
    runtime = resolved.get("runtime", {})
    model_cfg = resolved.get("models", {}).get("text", {})
    development_model_override = runtime.get("development_model")
    development_model_cfg = dict(model_cfg)
    if development_model_override:
        development_model_cfg["model"] = development_model_override
    prompt_path = runtime.get("prompt_path")
    concurrency_text = runtime.get("concurrency_text", 8)
    tags = taxonomy["tags"]
    stages = resolved.get("stages", {}).get("definitions", [])
    stage_counts = resolved["deck_sizes"]["developments_per_stage"]
    additional_instructions = scenario.get("additional_instructions", scenario.get("injection", ""))
    client = OpenAIClient()

    all_cards: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    stages_to_generate: list[dict[str, Any]] = []
    stage_cards_by_index: dict[int, list[dict[str, Any]]] = {}

    for stage_index, count in enumerate(stage_counts):
        stage_def = stages[min(stage_index, len(stages) - 1)] if stages else {"id": stage_index}
        stage_path = out_dir / "cards" / f"developments.stage{stage_index}.jsonl"
        if reuse_existing and stage_path.exists():
            stage_cards = read_jsonl(stage_path)
            _ensure_card_types(stage_cards)
            if len(stage_cards) != count:
                console.print(
                    f"[yellow]Stage {stage_index} has {len(stage_cards)} cards on disk; "
                    f"expected {count}. Using existing cards.[/yellow]"
                )
            else:
                console.print(
                    f"[green]Stage {stage_index} cards already exist; loading from {stage_path}.[/green]"
                )
            stage_cards_by_index[stage_index] = stage_cards
            continue
        stages_to_generate.append({"index": stage_index, "count": count, "def": stage_def})

    async def _generate_stage(stage_spec: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
        stage_index = stage_spec["index"]
        count = stage_spec["count"]
        stage_def = stage_spec["def"]
        console.print(f"[cyan]Generating stage {stage_index} with {count} development cards.[/cyan]")
        if client.use_dummy:
            blueprint = dummy_stage_blueprint(stage=stage_def, tags=tags, target_count=count)
        else:
            blueprint_prompt = render_prompt(
                "stage_blueprint.jinja",
                prompt_path=prompt_path,
                additional_instructions=additional_instructions,
                stage=stage_def,
                tags=tags,
                mix_targets=resolved.get("mix_targets", {}),
                target_count=count,
                outline_text=outline_text,
            )
            blueprint_payload = _build_text_payload(
                blueprint_prompt,
                development_model_cfg,
                STAGE_BLUEPRINT_SCHEMA,
                name=f"stage{stage_index}_blueprint",
            )
            blueprint_response = await client.responses_async(blueprint_payload)
            blueprint = _parse_response_json(blueprint_response) or {}

        threads = blueprint.get("threads", [])
        special_counts = blueprint.get("special_counts", {})
        prior_card_ids = _prior_stage_card_ids(stage_index, stage_counts)
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
                additional_instructions=additional_instructions,
                stage=stage_def,
                tags=tags,
                beats=beats,
                card_ids=card_ids,
                outline_text=outline_text,
            )
            cards_payload = _build_text_payload(
                cards_prompt,
                development_model_cfg,
                DEVELOPMENT_CARDS_RESPONSE_SCHEMA,
                name=f"stage{stage_index}_cards",
            )
            cards_response = await client.responses_async(cards_payload)
            response = _parse_response_json(cards_response) or {}

        stage_cards = _normalize_dev_cards(
            response.get("cards", []),
            count,
            stage_index,
            tags,
            beats,
        )
        for idx, card in enumerate(stage_cards):
            card["id"] = card_ids[idx]
            card["stage"] = stage_index
            card.setdefault("art_prompt", "")
        return stage_index, stage_cards

    if stages_to_generate:
        console.print("[cyan]Generating development cards in parallel across stages.[/cyan]")
        results = run_async(
            gather_with_concurrency(
                concurrency_text,
                [lambda spec=spec: _generate_stage(spec) for spec in stages_to_generate],
                progress_desc="Stage card generation",
            )
        )
        for stage_index, stage_cards in results:
            stage_cards_by_index[stage_index] = stage_cards

    cards_needing_prompts: list[dict[str, Any]] = []
    for stage_index, count in enumerate(stage_counts):
        stage_cards = stage_cards_by_index.get(stage_index, [])
        if not stage_cards:
            continue
        for card in stage_cards:
            cards_needing_prompts.append(card)

    if cards_needing_prompts:
        console.print("[cyan]Generating development art prompts in parallel.[/cyan]")

        def _render_prompt(card: dict[str, Any]) -> dict[str, Any]:
            card["art_prompt"] = render_prompt(
                "image_prompt_development.jinja",
                prompt_path=prompt_path,
                card=card,
                additional_instructions=additional_instructions,
                locale_visuals=scenario.get("locale_visuals", []),
                image_outline_text=image_outline_text or "",
            ).strip()
            return card

        run_async(
            gather_with_concurrency(
                concurrency_text,
                [lambda card=card: asyncio.to_thread(_render_prompt, card) for card in cards_needing_prompts],
            )
        )

    console.print("[cyan]Generating stage summaries in parallel.[/cyan]")

    async def _summary_task(stage_index: int, stage_cards: list[dict[str, Any]]) -> dict[str, Any]:
        stage_def = stages[min(stage_index, len(stages) - 1)] if stages else {"id": stage_index}
        return await _generate_stage_summary_async(
            stage_index=stage_index,
            stage_def=stage_def,
            stage_cards=stage_cards,
            scenario=scenario,
            prompt_path=prompt_path,
            model_cfg=model_cfg,
            client=client,
            outline_text=outline_text,
        )

    summary_results = run_async(
        gather_with_concurrency(
            concurrency_text,
            [
                lambda stage_index=stage_index, stage_cards=stage_cards: _summary_task(
                    stage_index, stage_cards
                )
                for stage_index, stage_cards in stage_cards_by_index.items()
            ],
            progress_desc="Stage summaries",
        )
    )
    summaries.extend(summary_results)

    for stage_index, stage_cards in stage_cards_by_index.items():
        _ensure_card_types(stage_cards)
        for card in stage_cards:
            Draft202012Validator(DEVELOPMENT_CARD_SCHEMA).validate(card)
        write_jsonl(out_dir / "cards" / f"developments.stage{stage_index}.jsonl", stage_cards)
        all_cards.extend(stage_cards)

    write_json(out_dir / "meta" / "stage_summaries.json", summaries)
    return all_cards


def _generate_stage_summary(
    *,
    stage_index: int,
    stage_def: dict[str, Any],
    stage_cards: list[dict[str, Any]],
    scenario: dict[str, Any],
    prompt_path: str | None,
    model_cfg: dict[str, Any],
    client: OpenAIClient,
    outline_text: str,
) -> dict[str, Any]:
    if client.use_dummy:
        return dummy_stage_summary(stage_index=stage_index, cards=stage_cards)
    summary_prompt = render_prompt(
        "stage_summary.jinja",
        prompt_path=prompt_path,
        additional_instructions=scenario.get("additional_instructions", scenario.get("injection", "")),
        stage=stage_def,
        cards=stage_cards,
        outline_text=outline_text,
    )
    summary_payload = _build_text_payload(
        summary_prompt,
        model_cfg,
        STAGE_SUMMARY_SCHEMA,
        name=f"stage{stage_index}_summary",
    )
    summary_response = client.responses(summary_payload)
    return _parse_response_json(summary_response) or {"stage": stage_index, "facts": [], "changes_vs_prior": []}


async def _generate_stage_summary_async(
    *,
    stage_index: int,
    stage_def: dict[str, Any],
    stage_cards: list[dict[str, Any]],
    scenario: dict[str, Any],
    prompt_path: str | None,
    model_cfg: dict[str, Any],
    client: OpenAIClient,
    outline_text: str,
) -> dict[str, Any]:
    if client.use_dummy:
        return dummy_stage_summary(stage_index=stage_index, cards=stage_cards)
    summary_prompt = render_prompt(
        "stage_summary.jinja",
        prompt_path=prompt_path,
        additional_instructions=scenario.get("additional_instructions", scenario.get("injection", "")),
        stage=stage_def,
        cards=stage_cards,
        outline_text=outline_text,
    )
    summary_payload = _build_text_payload(
        summary_prompt,
        model_cfg,
        STAGE_SUMMARY_SCHEMA,
        name=f"stage{stage_index}_summary",
    )
    summary_response = await client.responses_async(summary_payload)
    return _parse_response_json(summary_response) or {"stage": stage_index, "facts": [], "changes_vs_prior": []}


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
                "valence": "positive",
                "impact_score": 1,
                "arrows_up": 1,
                "arrows_down": 0,
                "severity": 3,
                "card_type": "standard",
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
        if not card.get("card_type"):
            card["card_type"] = "power" if card.get("effects") else "standard"
        if card.get("card_type") == "power" and not card.get("effects"):
            card["effects"] = [{"type": "DRAW_DEV_NOW", "params": {"count": 1, "stage_offset": 0}}]
        _normalize_valence_icons(card)
    return normalized


def _ensure_card_types(cards: list[dict[str, Any]]) -> None:
    for card in cards:
        if not card.get("card_type"):
            card["card_type"] = "power" if card.get("effects") else "standard"
        if card.get("card_type") == "power" and not card.get("effects"):
            card["effects"] = [{"type": "DRAW_DEV_NOW", "params": {"count": 1, "stage_offset": 0}}]


def _normalize_valence_icons(card: dict[str, Any]) -> None:
    impact_score = _normalize_impact_score(card.get("impact_score"))
    if impact_score is not None:
        if impact_score > 0:
            arrows_up = abs(impact_score)
            arrows_down = 0
            valence = "positive"
        elif impact_score < 0:
            arrows_up = 0
            arrows_down = abs(impact_score)
            valence = "negative"
        else:
            arrows_up = 0
            arrows_down = 0
            valence = "mixed"
    else:
        arrows_up = _normalize_arrow_count(card.get("arrows_up", 0))
        arrows_down = _normalize_arrow_count(card.get("arrows_down", 0))
        valence = str(card.get("valence") or "mixed").lower()

        if valence == "positive":
            arrows_down = 0
            if arrows_up == 0:
                arrows_up = 1
        elif valence == "negative":
            arrows_up = 0
            if arrows_down == 0:
                arrows_down = 1
        else:
            arrows_up = 0
            arrows_down = 0

        if arrows_up > 0:
            valence = "positive"
        elif arrows_down > 0:
            valence = "negative"
        else:
            valence = "mixed"
        impact_score = _impact_score_from_arrows(arrows_up, arrows_down)

    card["valence"] = valence
    card["impact_score"] = impact_score
    card["arrows_up"] = _normalize_arrow_count(arrows_up)
    card["arrows_down"] = _normalize_arrow_count(arrows_down)


def _normalize_arrow_count(value: Any) -> int:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        return 0
    if count <= 0:
        return 0
    return min(5, count)


def _normalize_impact_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(-5, min(5, score))


def _impact_score_from_arrows(arrows_up: int, arrows_down: int) -> int:
    if arrows_up > 0 and arrows_down == 0:
        return max(1, min(5, arrows_up))
    if arrows_down > 0 and arrows_up == 0:
        return -max(1, min(5, arrows_down))
    return 0


def _prior_stage_card_ids(stage_index: int, stage_counts: list[int]) -> list[str]:
    if stage_index <= 0 or not stage_counts:
        return []
    prior_index = stage_index - 1
    prior_count = stage_counts[prior_index] if prior_index < len(stage_counts) else stage_counts[-1]
    return [f"dev_s{prior_index}_{i:02d}" for i in range(prior_count)]
