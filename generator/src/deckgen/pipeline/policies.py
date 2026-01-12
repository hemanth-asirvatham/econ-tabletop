from __future__ import annotations

from pathlib import Path
from typing import Any

from deckgen.utils.io import write_jsonl


def generate_policies(config: dict[str, Any], taxonomy: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    total = config["deck_sizes"]["policies_total"]
    tags = taxonomy["tags"]
    categories = taxonomy["categories"]
    cards: list[dict[str, Any]] = []
    for i in range(total):
        tag = tags[i % len(tags)]
        category = categories[i % len(categories)]
        readable_tag = tag.replace("_", " ").title()
        card = {
            "id": f"policy_{i:03d}",
            "title": f"{readable_tag} Initiative",
            "short_description": f"Targeted action on {readable_tag.lower()}.",
            "description": (
                "A grounded, policy-relevant initiative that addresses immediate AI economy risks and opportunities. "
                "It coordinates public agencies and private stakeholders to implement measurable interventions."
            ),
            "category": category,
            "cost": {
                "budget_level": 2 + (i % 3),
                "implementation_complexity": 2 + (i % 3),
                "notes": "Balanced fiscal impact with shared responsibility.",
            },
            "timeline": {
                "time_to_launch": "months",
                "time_to_impact": "1-2y",
            },
            "impact_score": 2 + (i % 3),
            "tags": [tag],
            "addresses_tags": [tag],
            "side_effect_tags": [],
            "prerequisites_policy_tags": [],
            "synergy_policy_tags": [],
            "role_restrictions": [],
            "art_prompt": f"Horizontal illustration of policymakers collaborating on {readable_tag.lower()}, clear space top-left, no readable text.",
            "flavor_quote": "“Policy is how we steer technology toward shared prosperity.”",
        }
        cards.append(card)
    write_jsonl(out_dir / "cards" / "policies.jsonl", cards)
    return cards
