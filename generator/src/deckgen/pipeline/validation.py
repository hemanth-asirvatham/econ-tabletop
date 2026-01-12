from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from deckgen.schemas import DEVELOPMENT_CARD_SCHEMA, POLICY_CARD_SCHEMA
from deckgen.utils.io import write_json
from deckgen.utils.text_similarity import similarity


def validate_deck(policies: list[dict[str, Any]], developments: list[dict[str, Any]], out_dir: Path) -> None:
    policy_validator = Draft202012Validator(POLICY_CARD_SCHEMA)
    development_validator = Draft202012Validator(DEVELOPMENT_CARD_SCHEMA)

    errors: list[str] = []
    warnings: list[str] = []
    for policy in policies:
        for err in policy_validator.iter_errors(policy):
            errors.append(f"Policy {policy.get('id')}: {err.message}")

    for dev in developments:
        for err in development_validator.iter_errors(dev):
            errors.append(f"Development {dev.get('id')}: {err.message}")

    duplicate_titles = _find_duplicate_titles([p["title"] for p in policies] + [d["title"] for d in developments])
    for title in duplicate_titles:
        warnings.append(f"Potential duplicate title: {title}")

    report = {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    write_json(out_dir / "validation" / "report.json", report)
    if errors:
        raise ValueError("Validation failed. See validation/report.json for details.")


def _find_duplicate_titles(titles: list[str]) -> list[str]:
    duplicates: list[str] = []
    for i, title in enumerate(titles):
        for j in range(i + 1, len(titles)):
            if similarity(title, titles[j]) > 0.92:
                duplicates.append(title)
                break
    return duplicates
