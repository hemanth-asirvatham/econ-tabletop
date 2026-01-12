from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


def _default_prompt_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "prompts"


def render_prompt(template_name: str, prompt_path: str | Path | None = None, **kwargs: Any) -> str:
    prompt_dir = Path(prompt_path).expanduser().resolve() if prompt_path else _default_prompt_dir()
    env = Environment(loader=FileSystemLoader(str(prompt_dir)), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_name)
    return template.render(**kwargs).strip() + "\n"
