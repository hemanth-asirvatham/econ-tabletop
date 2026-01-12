from __future__ import annotations

from typing import Any


def dummy_taxonomy(config: dict[str, Any]) -> dict[str, Any]:
    from deckgen.pipeline.taxonomy import DEFAULT_CATEGORIES, DEFAULT_TAGS

    return {
        "categories": DEFAULT_CATEGORIES,
        "tags": DEFAULT_TAGS,
        "roles": config.get("scenario", {}).get("roles", []),
    }


def dummy_policy_blueprint(
    *,
    count: int,
    categories: list[str],
    tags: list[str],
) -> dict[str, Any]:
    slots = []
    for idx in range(count):
        category = categories[idx % len(categories)]
        tag = tags[idx % len(tags)]
        slots.append(
            {
                "slot_id": f"policy_slot_{idx:03d}",
                "category": category,
                "theme": f"{category} initiative for {tag.replace('_', ' ')}",
                "required_tags": [tag],
                "anti_duplicate_notes": "Provide a distinct implementation lever.",
            }
        )
    return {"slots": slots}


def dummy_policy_cards(
    *,
    card_ids: list[str],
    slots: list[dict[str, Any]],
    tags: list[str],
) -> dict[str, Any]:
    cards = []
    for idx, card_id in enumerate(card_ids):
        slot = slots[idx % len(slots)]
        tag = (slot.get("required_tags") or [tags[idx % len(tags)]])[0]
        cards.append(
            {
                "id": card_id,
                "title": f"{slot['theme'].title()}",
                "short_description": f"Targeted policy action on {tag.replace('_', ' ')}.",
                "description": "A pragmatic policy package aligned with the scenario to steer AI adoption outcomes.",
                "category": slot["category"],
                "cost": {
                    "budget_level": 3,
                    "implementation_complexity": 3,
                    "notes": "Balanced fiscal impact with shared responsibility.",
                },
                "timeline": {"time_to_launch": "months", "time_to_impact": "1-2y"},
                "impact_score": 3,
                "tags": [tag],
                "addresses_tags": [tag],
                "side_effect_tags": [],
                "prerequisites_policy_tags": [],
                "synergy_policy_tags": [],
                "role_restrictions": [],
                "art_prompt": "",
                "flavor_quote": "\"Steady policy keeps innovation aligned with public good.\"",
            }
        )
    return {"cards": cards}


def dummy_stage_blueprint(
    *,
    stage: dict[str, Any],
    tags: list[str],
    target_count: int,
) -> dict[str, Any]:
    thread_count = max(1, min(4, target_count))
    threads = []
    for idx in range(thread_count):
        tag = tags[idx % len(tags)]
        threads.append(
            {
                "thread_id": f"thread_{stage['id']}_{idx}",
                "beat_plan": [
                    f"Early movement in {tag.replace('_', ' ')}",
                    f"Acceleration in {tag.replace('_', ' ')} adoption",
                ],
                "target_count": max(1, target_count // thread_count),
                "valence_target": "mixed",
            }
        )
    return {
        "threads": threads,
        "special_counts": {
            "supersedes": max(1, int(target_count * 0.15)),
            "conditional": max(1, int(target_count * 0.15)),
            "powerups": max(1, int(target_count * 0.1)),
            "quantitative_indicators": max(1, int(target_count * 0.15)),
        },
    }


def dummy_development_cards(
    *,
    card_ids: list[str],
    stage_index: int,
    beats: list[dict[str, Any]],
    tags: list[str],
) -> dict[str, Any]:
    cards = []
    for idx, card_id in enumerate(card_ids):
        beat = beats[idx % len(beats)]
        tag = beat.get("primary_tag") or tags[idx % len(tags)]
        cards.append(
            {
                "id": card_id,
                "stage": stage_index,
                "title": f"Stage {stage_index} {tag.replace('_', ' ').title()} Shift",
                "short_description": beat.get("beat") or f"Observed shift in {tag.replace('_', ' ')}.",
                "description": "Grounded development reflecting AI deployment trends and economic impacts.",
                "valence": "mixed",
                "arrows_up": 2,
                "arrows_down": 1,
                "severity": 3,
                "tags": [tag],
                "thread_id": beat.get("thread_id") or f"thread_{stage_index}",
                "supersedes": None,
                "activation": {"type": "immediate", "required_policy_tags": []},
                "effects": [],
                "art_prompt": "",
                "suggested_visibility": "faceup" if idx % 2 == 0 else "facedown",
            }
        )
    return {"cards": cards}


def dummy_stage_summary(
    *,
    stage_index: int,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    facts = [f"{card['title']}" for card in cards[:10]]
    return {
        "stage": stage_index,
        "facts": facts,
        "changes_vs_prior": ["Developments build on prior stage dynamics."],
    }
