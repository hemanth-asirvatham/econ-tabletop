from __future__ import annotations

from pathlib import Path
from typing import Any

from deckgen.utils.io import write_json


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
    taxonomy = {
        "categories": DEFAULT_CATEGORIES,
        "tags": DEFAULT_TAGS,
        "roles": config.get("scenario", {}).get("roles", []),
    }
    write_json(out_dir / "meta" / "taxonomy.json", taxonomy)
    write_json(out_dir / "meta" / "tags.json", {"tags": DEFAULT_TAGS})
    return taxonomy
