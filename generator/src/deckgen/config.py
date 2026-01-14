from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = {
    "scenario": {
        "name": "Baseline",
        "injection": "",
        "tone": "realistic, policy-relevant, grounded",
        "locale_visuals": [],
    },
    "stages": {
        "count": 5,
        "definitions": [
            {
                "id": 0,
                "name": "Stage 0",
                "time_horizon": "today / near-term",
                "capability_profile": "Frontier AI capabilities similar to present-day large models",
            },
            {
                "id": 1,
                "name": "Stage 1",
                "time_horizon": "2-5 years",
                "capability_profile": "Improved agentic tooling and narrower automation gains",
            },
            {
                "id": 2,
                "name": "Stage 2",
                "time_horizon": "5-10 years",
                "capability_profile": "Broader automation with significant macroeconomic impacts",
            },
            {
                "id": 3,
                "name": "Stage 3",
                "time_horizon": "10-15 years",
                "capability_profile": "Systemic AI integration across critical infrastructure and services",
            },
            {
                "id": 4,
                "name": "Stage 4",
                "time_horizon": "15+ years",
                "capability_profile": "Advanced AI driving economy-wide reorganization and governance shifts",
            },
        ],
    },
    "deck_sizes": {
        "policies_total": 56,
        "developments_per_stage": [30, 30, 30, 30, 30],
    },
    "mix_targets": {
        "positive_share": 0.7,
        "supersedes_share": 0.15,
        "conditional_share": 0.15,
        "powerup_share": 0.1,
        "quantitative_indicator_share": 0.15,
    },
    "gameplay_defaults": {
        "dev_faceup_start": 4,
        "dev_facedown_start": 2,
        "dev_faceup_per_round": 3,
        "dev_facedown_per_round": 1,
        "hand_size_start": 5,
        "policy_draw_per_round": 2,
        "max_policies_per_player_per_round": 3,
        "players_default": 4,
    },
    "models": {
        "text": {
            "model": "gpt-5.2",
            "reasoning_effort": "high",
            "max_output_tokens": 2000,
            "temperature": 0.7,
            "top_p": 0.9,
            "store": False,
        },
        "image": {
            "api": "images",
            "model": "gpt-image-1.5",
            "responses_model": "gpt-5.2",
            "size": "1536x1024",
            "quality": "high",
            "background": None,
            "reference_policy_image": None,
            "reference_development_image": None,
        },
    },
    "runtime": {
        "concurrency_text": 500,
        "concurrency_image": 400,
        "image_candidate_count": 8,
        "image_reference_candidate_multiplier": 5,
        "image_timeout_s": 300,
        "critique_timeout_s": 150,
        "resume": True,
        "cache_requests": True,
        "prompt_path": None,
    },
}


@dataclass
class ResolvedConfig:
    data: dict[str, Any]
    source_path: Path


def load_config(path: Path) -> ResolvedConfig:
    path = path.expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        user_cfg = yaml.safe_load(handle) or {}
    merged = _deep_merge(DEFAULT_CONFIG, user_cfg)
    return ResolvedConfig(data=merged, source_path=path)


def resolve_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve a config dict by applying overrides to defaults."""
    base = deepcopy(DEFAULT_CONFIG)
    if overrides:
        return _deep_merge(base, overrides)
    return base


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in base.keys() | override.keys():
        if key in base and key in override:
            if isinstance(base[key], dict) and isinstance(override[key], dict):
                result[key] = _deep_merge(base[key], override[key])
            else:
                result[key] = override[key]
        elif key in base:
            result[key] = base[key]
        else:
            result[key] = override[key]
    return result
