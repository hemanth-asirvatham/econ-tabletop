from __future__ import annotations

from pathlib import Path
from typing import Any

from deckgen.utils.io import write_json, write_jsonl


def generate_stage_cards(config: dict[str, Any], taxonomy: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    all_cards: list[dict[str, Any]] = []
    tags = taxonomy["tags"]
    for stage_index, count in enumerate(config["deck_sizes"]["developments_per_stage"]):
        stage_cards: list[dict[str, Any]] = []
        for i in range(count):
            tag = tags[(stage_index * 7 + i) % len(tags)]
            valence = "positive" if i % 3 != 0 else "negative"
            severity = 2 + (i % 3)
            arrows_up = 2 if valence == "positive" else 0
            arrows_down = 2 if valence == "negative" else 0
            thread_id = f"thread_{i % 5}"
            supersedes = None
            if i >= 5 and i % 5 == 0:
                supersedes = f"dev_s{stage_index}_00"
            activation = {"type": "immediate", "required_policy_tags": []}
            if i % 7 == 0:
                activation = {"type": "conditional", "required_policy_tags": [tag]}
            effects = []
            if i % 9 == 0:
                effects = [{"type": "DRAW_DEV_NOW", "params": {"count": 1, "stage_offset": 0}}]
            readable_tag = tag.replace("_", " ").title()
            card = {
                "id": f"dev_s{stage_index}_{i:02d}",
                "stage": stage_index,
                "title": f"Stage {stage_index} {readable_tag} Shift",
                "short_description": f"Observed shift in {readable_tag.lower()}.",
                "description": (
                    "A grounded development reflecting current AI deployment trends and measurable economic impacts. "
                    "The effects remain plausible for the stage horizon and provide concrete policy levers."
                ),
                "valence": valence,
                "arrows_up": arrows_up,
                "arrows_down": arrows_down,
                "severity": severity,
                "tags": [tag],
                "thread_id": thread_id,
                "supersedes": supersedes,
                "activation": activation,
                "effects": effects,
                "art_prompt": f"Horizontal illustration showing {readable_tag.lower()} dynamics, clear space top-left, no readable text.",
                "suggested_visibility": "faceup" if i % 2 == 0 else "facedown",
            }
            stage_cards.append(card)
        write_jsonl(out_dir / "cards" / f"developments.stage{stage_index}.jsonl", stage_cards)
        summary = {
            "stage": stage_index,
            "facts": [
                f"Stage {stage_index} shows continued movement in {stage_cards[0]['tags'][0]}.",
                "Policymakers respond to AI adoption with targeted interventions.",
            ],
            "changes_vs_prior": [
                f"Stage {stage_index} introduces new pressures in {stage_cards[-1]['tags'][0]}."
            ],
        }
        summaries.append(summary)
        all_cards.extend(stage_cards)
    write_json(out_dir / "meta" / "stage_summaries.json", summaries)
    return all_cards
