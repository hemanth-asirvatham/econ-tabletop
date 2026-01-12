from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rich.console import Console

from deckgen.config import load_config
from deckgen.pipeline.images import generate_images
from deckgen.pipeline.policies import generate_policies
from deckgen.pipeline.print_export import export_print
from deckgen.pipeline.render_cards import render_cards
from deckgen.pipeline.stages import generate_stage_cards
from deckgen.pipeline.taxonomy import generate_taxonomy
from deckgen.pipeline.validation import validate_deck
from deckgen.utils.io import write_json, write_yaml

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(prog="deckgen")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--config", required=True, type=Path)
    generate_parser.add_argument("--out", required=True, type=Path)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--deck", required=True, type=Path)

    images_parser = subparsers.add_parser("images")
    images_parser.add_argument("--deck", required=True, type=Path)

    print_parser = subparsers.add_parser("print")
    print_parser.add_argument("--deck", required=True, type=Path)

    all_parser = subparsers.add_parser("all")
    all_parser.add_argument("--config", required=True, type=Path)
    all_parser.add_argument("--out", required=True, type=Path)

    args = parser.parse_args()

    if args.command == "generate":
        run_generate(args.config, args.out)
    elif args.command == "render":
        run_render(args.deck)
    elif args.command == "images":
        run_images(args.deck)
    elif args.command == "print":
        run_print(args.deck)
    elif args.command == "all":
        run_generate(args.config, args.out)
        run_render(args.out)
        run_images(args.out)
        run_print(args.out)


def run_generate(config_path: Path, out_dir: Path) -> None:
    config = load_config(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(out_dir / "meta" / "config_resolved.yaml", config.data)

    taxonomy = generate_taxonomy(config.data, out_dir)
    policies = generate_policies(config.data, taxonomy, out_dir)
    developments = generate_stage_cards(config.data, taxonomy, out_dir)

    manifest = {
        "deck_id": out_dir.name,
        "scenario": config.data.get("scenario", {}),
        "gameplay_defaults": config.data.get("gameplay_defaults", {}),
        "stages": config.data.get("stages", {}),
    }
    write_json(out_dir / "manifest.json", manifest)
    validate_deck(policies, developments, out_dir)
    console.print(f"[green]Generated deck at {out_dir}[/green]")


def run_generate_from_config(config_data: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(out_dir / "meta" / "config_resolved.yaml", config_data)

    taxonomy = generate_taxonomy(config_data, out_dir)
    policies = generate_policies(config_data, taxonomy, out_dir)
    developments = generate_stage_cards(config_data, taxonomy, out_dir)

    manifest = {
        "deck_id": out_dir.name,
        "scenario": config_data.get("scenario", {}),
        "gameplay_defaults": config_data.get("gameplay_defaults", {}),
        "stages": config_data.get("stages", {}),
    }
    write_json(out_dir / "manifest.json", manifest)
    validate_deck(policies, developments, out_dir)
    console.print(f"[green]Generated deck at {out_dir}[/green]")


def run_render(deck_dir: Path) -> None:
    policies = _read_cards(deck_dir / "cards" / "policies.jsonl")
    developments = _read_cards_multi(deck_dir / "cards")
    render_cards(policies, developments, deck_dir)
    console.print("[green]Rendered card images.[/green]")


def run_images(deck_dir: Path) -> None:
    policies = _read_cards(deck_dir / "cards" / "policies.jsonl")
    developments = _read_cards_multi(deck_dir / "cards")
    generate_images({}, policies, developments, deck_dir)


def run_print(deck_dir: Path) -> None:
    export_print(deck_dir)
    console.print("[green]Print export complete.[/green]")


def _read_cards(path: Path) -> list[dict[str, str]]:
    cards = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                cards.append(json.loads(line))
    return cards


def _read_cards_multi(cards_dir: Path) -> list[dict[str, str]]:
    cards = []
    for file in cards_dir.glob("developments.stage*.jsonl"):
        cards.extend(_read_cards(file))
    return cards


if __name__ == "__main__":
    main()
