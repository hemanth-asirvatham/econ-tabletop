from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from deckgen.cli import run_generate, run_generate_from_config, run_images, run_print, run_render
from deckgen.config import resolve_config


@dataclass
class UISession:
    deck_server: subprocess.Popen
    ui_server: subprocess.Popen
    deck_url: str
    ui_url: str | None

    def stop(self) -> None:
        """Terminate running UI processes."""
        for process in (self.ui_server, self.deck_server):
            if process.poll() is None:
                process.terminate()
        for process in (self.ui_server, self.deck_server):
            if process.poll() is None:
                process.wait(timeout=10)

    def __enter__(self) -> "UISession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


def find_repo_root(start: Path | None = None) -> Path | None:
    """Search upward for a repo root containing both generator/ and ui/."""
    start_path = (start or Path.cwd()).resolve()
    for parent in [start_path, *start_path.parents]:
        if (parent / "generator").is_dir() and (parent / "ui").is_dir():
            return parent
    return None


def get_example_config(name: str = "baseline") -> Path:
    """Return an example config path (baseline/uae) if available."""
    repo_root = find_repo_root()
    if repo_root:
        candidate = repo_root / "generator" / "examples" / "configs" / f"{name}.yaml"
        if candidate.exists():
            return candidate

    data_root = files("econ_tabletop.data.configs")
    packaged = data_root.joinpath(f"{name}.yaml")
    if packaged.is_file():
        return Path(packaged)

    raise FileNotFoundError(f"Could not locate example config '{name}'.")


def generate_deck(config_path: Path | str, out_dir: Path | str) -> None:
    """Generate deck JSON and manifests."""
    config_path = _resolve_path(config_path)
    out_dir = _resolve_path(out_dir)
    print(f"Generating deck using {config_path} -> {out_dir}")
    run_generate(config_path, out_dir)


def render_deck(deck_dir: Path | str) -> None:
    """Render deck card PNGs."""
    deck_dir = _resolve_path(deck_dir)
    print(f"Rendering cards for deck at {deck_dir}")
    run_render(deck_dir)


def generate_images(deck_dir: Path | str) -> None:
    """Generate new art for a deck."""
    deck_dir = _resolve_path(deck_dir)
    print(f"Generating art for deck at {deck_dir}")
    run_images(deck_dir)


def print_deck(deck_dir: Path | str) -> None:
    """Export printable PDFs for a deck."""
    deck_dir = _resolve_path(deck_dir)
    print(f"Exporting printable PDFs for deck at {deck_dir}")
    run_print(deck_dir)


def run_all(config_path: Path | str, out_dir: Path | str) -> None:
    """Run full deck pipeline (generate -> render -> images -> print)."""
    generate_deck(config_path, out_dir)
    render_deck(out_dir)
    generate_images(out_dir)
    print_deck(out_dir)


def run_pipeline(
    config_path: Path | str,
    out_dir: Path | str,
    *,
    render: bool = True,
    images: bool = True,
    print_pdf: bool = True,
) -> None:
    """Run the deck pipeline with configurable steps.

    Args:
        config_path: Path to the YAML configuration file.
        out_dir: Output directory for the generated deck.
        render: When True, renders placeholder card PNGs after generation.
        images: When True, runs the (placeholder) image generation step.
        print_pdf: When True, exports printable PDFs for the deck.
    """
    generate_deck(config_path, out_dir)
    if render:
        render_deck(out_dir)
    if images:
        generate_images(out_dir)
    if print_pdf:
        print_deck(out_dir)


def deck_builder(
    deck_dir: Path | str,
    *,
    model_text: str | None = None,
    model_image: str | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    store: bool | None = None,
    image_size: str | None = None,
    image_background: str | None = None,
    reference_policy_image: str | None = None,
    reference_development_image: str | None = None,
    concurrency_text: int | None = None,
    concurrency_image: int | None = None,
    image_batch_size: int | None = None,
    resume: bool = True,
    cache_requests: bool | None = None,
    prompt_path: str | None = None,
    scenario_name: str | None = None,
    scenario_injection: str | None = None,
    scenario_tone: str | None = None,
    locale_visuals: list[str] | None = None,
    deck_sizes: dict[str, Any] | None = None,
    mix_targets: dict[str, Any] | None = None,
    gameplay_defaults: dict[str, Any] | None = None,
    stages: dict[str, Any] | None = None,
    render: bool = True,
    images: bool = True,
    print_pdf: bool = True,
    reuse_existing: bool | None = None,
) -> Path:
    """Generate a deck with direct parameters (no config file required).

    Args:
        deck_dir: Output directory where deck artifacts are written.
        model_text: Text model identifier.
        model_image: Image model identifier.
        reasoning_effort: Reasoning effort setting for text model.
        max_output_tokens: Max output tokens for text model.
        temperature: Sampling temperature for text model.
        top_p: Top-p sampling for text model.
        store: Whether to store text responses.
        image_size: Image generation size.
        image_background: Image background setting.
        reference_policy_image: Path to a reference policy card image.
        reference_development_image: Path to a reference development card image.
        concurrency_text: Text generation concurrency.
        concurrency_image: Image generation concurrency.
        image_batch_size: Batch size for image generation.
        resume: Whether to resume/cache requests and reuse data.
        cache_requests: Whether to store OpenAI request/response cache.
        prompt_path: Optional override path for prompt templates.
        scenario_name: Scenario label used in manifests.
        scenario_injection: Additional prompt instruction injected into prompts.
        scenario_tone: Style/tone guidance.
        locale_visuals: Locale/region visual motifs for art prompts.
        deck_sizes: Override deck sizes.
        mix_targets: Override deck mix targets.
        gameplay_defaults: Override gameplay defaults surfaced to the UI.
        stages: Override stage definitions.
        render: When True, renders card PNGs after generation.
        images: When True, runs the image generation step.
        print_pdf: When True, exports printable PDFs for the deck.
        reuse_existing: When True, skip generation if deck artifacts already exist.
    """
    deck_path = _resolve_path(deck_dir)
    reuse_existing = resume if reuse_existing is None else reuse_existing
    config = _build_config(
        model_text=model_text,
        model_image=model_image,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        top_p=top_p,
        store=store,
        image_size=image_size,
        image_background=image_background,
        reference_policy_image=reference_policy_image,
        reference_development_image=reference_development_image,
        concurrency_text=concurrency_text,
        concurrency_image=concurrency_image,
        image_batch_size=image_batch_size,
        resume=resume,
        cache_requests=cache_requests,
        prompt_path=prompt_path,
        scenario_name=scenario_name,
        scenario_injection=scenario_injection,
        scenario_tone=scenario_tone,
        locale_visuals=locale_visuals,
        deck_sizes=deck_sizes,
        mix_targets=mix_targets,
        gameplay_defaults=gameplay_defaults,
        stages=stages,
    )

    if reuse_existing and _deck_has_cards(deck_path):
        print(f"Deck already exists at {deck_path}; reusing existing cards.")
    else:
        run_generate_from_config(config, deck_path)

    if render:
        run_render(deck_path)
    if images:
        run_images(deck_path)
    if print_pdf:
        run_print(deck_path)
    return deck_path


def run_simulation(
    deck_dir: Path | str,
    *,
    ui_dir: Path | str | None = None,
    deck_port: int = 8787,
    vite_port: int | None = None,
    npm_install: bool = False,
    env: dict[str, str] | None = None,
) -> UISession:
    """Launch the local UI simulation with a deck directory."""
    return launch_ui(
        deck_dir=deck_dir,
        ui_dir=ui_dir,
        deck_port=deck_port,
        vite_port=vite_port,
        npm_install=npm_install,
        env=env,
    )


def start_deck_server(
    deck_dir: Path | str,
    ui_dir: Path | str | None = None,
    port: int = 8787,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Start the deck API server and return the Popen handle."""
    deck_dir = _resolve_path(deck_dir)
    resolved_ui_dir = _resolve_ui_dir(ui_dir)
    environment = _merge_env(env)
    environment["PORT"] = str(port)

    command = [
        "node",
        "--loader",
        "ts-node/esm",
        "server/index.ts",
        "--deck",
        str(deck_dir),
    ]
    print(f"Starting deck server on port {port} using {deck_dir}")
    return subprocess.Popen(command, cwd=resolved_ui_dir, env=environment)


def launch_ui(
    deck_dir: Path | str,
    ui_dir: Path | str | None = None,
    deck_port: int = 8787,
    vite_port: int | None = None,
    npm_install: bool = False,
    env: dict[str, str] | None = None,
) -> UISession:
    """Launch deck server + Vite dev server for the GUI."""
    resolved_ui_dir = _resolve_ui_dir(ui_dir)
    environment = _merge_env(env)

    if npm_install:
        print("Running npm install...")
        subprocess.run(["npm", "install"], cwd=resolved_ui_dir, check=True)

    deck_server = start_deck_server(deck_dir, resolved_ui_dir, port=deck_port, env=environment)

    ui_command = ["npm", "run", "dev"]
    if vite_port is not None:
        ui_command += ["--", "--host", "0.0.0.0", "--port", str(vite_port)]

    print("Starting Vite UI server...")
    ui_server = subprocess.Popen(ui_command, cwd=resolved_ui_dir, env=environment)

    deck_url = f"http://localhost:{deck_port}"
    ui_url = f"http://localhost:{vite_port}" if vite_port is not None else None
    print(f"Deck API: {deck_url}")
    if ui_url:
        print(f"Vite UI: {ui_url}")
    return UISession(deck_server=deck_server, ui_server=ui_server, deck_url=deck_url, ui_url=ui_url)


def _resolve_ui_dir(ui_dir: Path | str | None) -> Path:
    if ui_dir is not None:
        resolved = _resolve_path(ui_dir)
    else:
        repo_root = find_repo_root()
        if repo_root is None:
            raise FileNotFoundError(
                "Could not locate the ui/ directory. Pass ui_dir explicitly or run from a repo checkout."
            )
        resolved = repo_root / "ui"

    if not resolved.exists():
        raise FileNotFoundError(f"UI directory not found at {resolved}")
    return resolved


def _merge_env(env: dict[str, str] | None) -> dict[str, str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return merged


def _resolve_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _build_config(
    *,
    model_text: str | None = None,
    model_image: str | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    store: bool | None = None,
    image_size: str | None = None,
    image_background: str | None = None,
    reference_policy_image: str | None = None,
    reference_development_image: str | None = None,
    concurrency_text: int | None = None,
    concurrency_image: int | None = None,
    image_batch_size: int | None = None,
    resume: bool | None = None,
    cache_requests: bool | None = None,
    prompt_path: str | None = None,
    scenario_name: str | None = None,
    scenario_injection: str | None = None,
    scenario_tone: str | None = None,
    locale_visuals: list[str] | None = None,
    deck_sizes: dict[str, Any] | None = None,
    mix_targets: dict[str, Any] | None = None,
    gameplay_defaults: dict[str, Any] | None = None,
    stages: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    scenario: dict[str, Any] = {}
    if scenario_name is not None:
        scenario["name"] = scenario_name
    if scenario_injection is not None:
        scenario["injection"] = scenario_injection
    if scenario_tone is not None:
        scenario["tone"] = scenario_tone
    if locale_visuals is not None:
        scenario["locale_visuals"] = locale_visuals
    if scenario:
        overrides["scenario"] = scenario

    models: dict[str, Any] = {}
    text_model: dict[str, Any] = {}
    if model_text is not None:
        text_model["model"] = model_text
    if reasoning_effort is not None:
        text_model["reasoning_effort"] = reasoning_effort
    if max_output_tokens is not None:
        text_model["max_output_tokens"] = max_output_tokens
    if temperature is not None:
        text_model["temperature"] = temperature
    if top_p is not None:
        text_model["top_p"] = top_p
    if store is not None:
        text_model["store"] = store
    if text_model:
        models["text"] = text_model

    image_model: dict[str, Any] = {}
    if model_image is not None:
        image_model["model"] = model_image
    if image_size is not None:
        image_model["size"] = image_size
    if image_background is not None:
        image_model["background"] = image_background
    if reference_policy_image is not None:
        image_model["reference_policy_image"] = reference_policy_image
    if reference_development_image is not None:
        image_model["reference_development_image"] = reference_development_image
    if image_model:
        models["image"] = image_model
    if models:
        overrides["models"] = models

    runtime: dict[str, Any] = {}
    if concurrency_text is not None:
        runtime["concurrency_text"] = concurrency_text
    if concurrency_image is not None:
        runtime["concurrency_image"] = concurrency_image
    if image_batch_size is not None:
        runtime["image_batch_size"] = image_batch_size
    if resume is not None:
        runtime["resume"] = resume
    if cache_requests is not None:
        runtime["cache_requests"] = cache_requests
    if prompt_path is not None:
        runtime["prompt_path"] = prompt_path
    if runtime:
        overrides["runtime"] = runtime

    if deck_sizes is not None:
        overrides["deck_sizes"] = deck_sizes
    if mix_targets is not None:
        overrides["mix_targets"] = mix_targets
    if gameplay_defaults is not None:
        overrides["gameplay_defaults"] = gameplay_defaults
    if stages is not None:
        overrides["stages"] = stages

    return resolve_config(overrides)


def _deck_has_cards(deck_dir: Path) -> bool:
    return (deck_dir / "cards" / "policies.jsonl").exists()
