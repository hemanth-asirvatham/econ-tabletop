POLICY_CARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "id",
        "title",
        "short_description",
        "description",
        "category",
        "cost",
        "timeline",
        "impact_score",
        "tags",
        "addresses_tags",
        "side_effect_tags",
        "prerequisites_policy_tags",
        "synergy_policy_tags",
        "role_restrictions",
        "art_prompt",
        "flavor_quote",
    ],
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "short_description": {"type": "string"},
        "description": {"type": "string"},
        "category": {"type": "string"},
        "cost": {
            "type": "object",
            "additionalProperties": False,
            "required": ["budget_level", "implementation_complexity", "notes"],
            "properties": {
                "budget_level": {"type": "integer", "minimum": 1, "maximum": 5},
                "implementation_complexity": {"type": "integer", "minimum": 1, "maximum": 5},
                "notes": {"type": "string"},
            },
        },
        "timeline": {
            "type": "object",
            "additionalProperties": False,
            "required": ["time_to_launch", "time_to_impact"],
            "properties": {
                "time_to_launch": {
                    "type": "string",
                    "enum": ["immediate", "weeks", "months", "1-2y", "3-5y"],
                },
                "time_to_impact": {
                    "type": "string",
                    "enum": ["immediate", "weeks", "months", "1-2y", "3-5y"],
                },
            },
        },
        "impact_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "tags": {"type": "array", "items": {"type": "string"}},
        "addresses_tags": {"type": "array", "items": {"type": "string"}},
        "side_effect_tags": {"type": "array", "items": {"type": "string"}},
        "prerequisites_policy_tags": {"type": "array", "items": {"type": "string"}},
        "synergy_policy_tags": {"type": "array", "items": {"type": "string"}},
        "role_restrictions": {"type": "array", "items": {"type": "string"}},
        "art_prompt": {"type": "string"},
        "flavor_quote": {"type": "string"},
    },
}

POLICY_CARDS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "array",
            "items": POLICY_CARD_SCHEMA,
            "minItems": 1,
        }
    },
}

EFFECT_PARAMS_DRAW_NOW = {
    "type": "object",
    "additionalProperties": False,
    "required": ["count", "stage_offset"],
    "properties": {
        "count": {"type": "integer", "minimum": 1},
        "stage_offset": {"type": "integer", "minimum": 0},
    },
}

EFFECT_PARAMS_DRAW_NEXT_STAGE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["count"],
    "properties": {
        "count": {"type": "integer", "minimum": 1},
    },
}

EFFECT_PARAMS_MODIFY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["delta"],
    "properties": {
        "delta": {"type": "integer"},
    },
}

EFFECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "params"],
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "DRAW_DEV_NOW",
                "DRAW_DEV_NEXT_STAGE_NOW",
                "MODIFY_DEV_DRAW_NEXT_ROUND",
                "MODIFY_POLICY_DRAW_NEXT_ROUND",
                "MODIFY_MAX_POLICIES_THIS_ROUND",
            ],
        },
        "params": {
            "type": "object",
            "additionalProperties": False,
            "required": ["count", "stage_offset", "delta"],
            "properties": {
                "count": {"type": ["integer", "null"], "minimum": 1},
                "stage_offset": {"type": ["integer", "null"], "minimum": 0},
                "delta": {"type": ["integer", "null"]},
            },
        },
    },
}

DEVELOPMENT_CARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "id",
        "stage",
        "title",
        "short_description",
        "description",
        "valence",
        "arrows_up",
        "arrows_down",
        "severity",
        "tags",
        "thread_id",
        "supersedes",
        "activation",
        "effects",
        "art_prompt",
        "suggested_visibility",
    ],
    "properties": {
        "id": {"type": "string"},
        "stage": {"type": "integer", "minimum": 0},
        "title": {"type": "string"},
        "short_description": {"type": "string"},
        "description": {"type": "string"},
        "valence": {"type": "string", "enum": ["positive", "negative", "mixed"]},
        "arrows_up": {"type": "integer", "minimum": 0, "maximum": 3},
        "arrows_down": {"type": "integer", "minimum": 0, "maximum": 3},
        "severity": {"type": "integer", "minimum": 1, "maximum": 5},
        "tags": {"type": "array", "items": {"type": "string"}},
        "thread_id": {"type": "string"},
        "supersedes": {"type": ["string", "null"]},
        "activation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["type", "required_policy_tags"],
            "properties": {
                "type": {"type": "string", "enum": ["immediate", "conditional"]},
                "required_policy_tags": {"type": "array", "items": {"type": "string"}},
            },
        },
        "effects": {"type": "array", "items": EFFECT_SCHEMA},
        "art_prompt": {"type": "string"},
        "suggested_visibility": {"type": "string", "enum": ["faceup", "facedown", "either"]},
    },
}

DEVELOPMENT_CARDS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "array",
            "items": DEVELOPMENT_CARD_SCHEMA,
            "minItems": 1,
        }
    },
}

TAXONOMY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["categories", "tags", "roles"],
    "properties": {
        "categories": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "roles": {"type": "array", "items": {"type": "string"}},
    },
}

POLICY_BLUEPRINT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["slots"],
    "properties": {
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["slot_id", "category", "theme", "required_tags", "anti_duplicate_notes"],
                "properties": {
                    "slot_id": {"type": "string"},
                    "category": {"type": "string"},
                    "theme": {"type": "string"},
                    "required_tags": {"type": "array", "items": {"type": "string"}},
                    "anti_duplicate_notes": {"type": "string"},
                },
            },
        }
    },
}

STAGE_BLUEPRINT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["threads", "special_counts"],
    "properties": {
        "threads": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["thread_id", "beat_plan", "target_count", "valence_target"],
                "properties": {
                    "thread_id": {"type": "string"},
                    "beat_plan": {"type": "array", "items": {"type": "string"}},
                    "target_count": {"type": "integer", "minimum": 1},
                    "valence_target": {"type": "string", "enum": ["positive", "negative", "mixed"]},
                },
            },
        },
        "special_counts": {
            "type": "object",
            "additionalProperties": False,
            "required": ["supersedes", "conditional", "powerups", "quantitative_indicators"],
            "properties": {
                "supersedes": {"type": "integer", "minimum": 0},
                "conditional": {"type": "integer", "minimum": 0},
                "powerups": {"type": "integer", "minimum": 0},
                "quantitative_indicators": {"type": "integer", "minimum": 0},
            },
        },
    },
}

STAGE_SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["stage", "facts", "changes_vs_prior"],
    "properties": {
        "stage": {"type": "integer", "minimum": 0},
        "facts": {"type": "array", "items": {"type": "string"}},
        "changes_vs_prior": {"type": "array", "items": {"type": "string"}},
    },
}
