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
        "count": 3,
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
        ],
    },
    "deck_sizes": {
        "policies_total": 18,
        "developments_per_stage": [16, 18, 20],
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
            "model": "gpt-4.1-mini",
            "reasoning_effort": "high",
            "max_output_tokens": 2000,
            "store": False,
        },
        "image": {
            "model": "gpt-image-1.5",
            "size": "1536x1024",
            "background": "transparent",
        },
    },
    "runtime": {
        "concurrency_text": 8,
        "concurrency_image": 4,
        "image_batch_size": 150,
        "resume": True,
        "cache_requests": True,
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
