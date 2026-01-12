from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from deckgen.cli import run_generate, run_images, run_print, run_render


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
    config_path = Path(config_path)
    out_dir = Path(out_dir)
    print(f"Generating deck using {config_path} -> {out_dir}")
    run_generate(config_path, out_dir)


def render_deck(deck_dir: Path | str) -> None:
    """Render deck card PNGs."""
    deck_dir = Path(deck_dir)
    print(f"Rendering cards for deck at {deck_dir}")
    run_render(deck_dir)


def generate_images(deck_dir: Path | str) -> None:
    """Generate new art for a deck."""
    deck_dir = Path(deck_dir)
    print(f"Generating art for deck at {deck_dir}")
    run_images(deck_dir)


def print_deck(deck_dir: Path | str) -> None:
    """Export printable PDFs for a deck."""
    deck_dir = Path(deck_dir)
    print(f"Exporting printable PDFs for deck at {deck_dir}")
    run_print(deck_dir)


def run_all(config_path: Path | str, out_dir: Path | str) -> None:
    """Run full deck pipeline (generate -> render -> images -> print)."""
    generate_deck(config_path, out_dir)
    render_deck(out_dir)
    generate_images(out_dir)
    print_deck(out_dir)


def start_deck_server(
    deck_dir: Path | str,
    ui_dir: Path | str | None = None,
    port: int = 8787,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Start the deck API server and return the Popen handle."""
    deck_dir = Path(deck_dir).resolve()
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
        resolved = Path(ui_dir).resolve()
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
