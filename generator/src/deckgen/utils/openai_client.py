from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

console = Console()


def format_text_input(model: str | None, prompt: str) -> str | list[dict[str, str]]:
    if model and (model.startswith("gpt-5") or model.startswith("o")):
        return [{"role": "user", "content": prompt}]
    return prompt


def supports_temperature(model: str | None) -> bool:
    if not model:
        return True
    return not (model.startswith("gpt-5") or model.startswith("o"))


class OpenAIClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        *,
        dummy: bool | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = os.environ.get("OPENAI_BASE_URL", base_url)
        self.organization = (
            os.environ.get("OPENAI_ORG") or os.environ.get("OPENAI_ORGANIZATION") or ""
        ).strip()
        self.project = os.environ.get("OPENAI_PROJECT", "").strip()
        env_dummy = os.environ.get("ECON_TABLETOP_DUMMY_OPENAI", "").strip().lower() in {"1", "true", "yes"}
        self.use_dummy = env_dummy if dummy is None else dummy
        self.client = httpx.Client(timeout=120)

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        if self.project:
            headers["OpenAI-Project"] = self.project
        return headers

    def responses(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.use_dummy or not self.api_key:
            if self.use_dummy:
                console.print("[yellow]ECON_TABLETOP_DUMMY_OPENAI enabled. Returning dummy response.[/yellow]")
            else:
                console.print("[yellow]OPENAI_API_KEY not set. Returning dummy response.[/yellow]")
            return {"output": [{"content": [{"type": "output_text", "text": json.dumps({})}]}]}
        resp = self.client.post(f"{self.base_url}/responses", headers=self._headers(), json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            console.print(
                "[red]OpenAI responses request failed.[/red]"
                f" Status: {resp.status_code}. Body: {resp.text}"
            )
            raise
        return resp.json()

    def images_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.use_dummy or not self.api_key:
            if self.use_dummy:
                console.print("[yellow]ECON_TABLETOP_DUMMY_OPENAI enabled. Returning dummy image response.[/yellow]")
            else:
                console.print("[yellow]OPENAI_API_KEY not set. Returning dummy image response.[/yellow]")
            return {"data": [{"b64_json": ""}]}
        resp = self.client.post(f"{self.base_url}/images/generations", headers=self._headers(), json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            console.print(
                "[red]OpenAI image request failed.[/red]"
                f" Status: {resp.status_code}. Body: {resp.text}"
            )
            console.print(
                "[yellow]Check that your API key has image access and that the model name is available in "
                "your project/organization.[/yellow]"
            )
            raise
        return resp.json()

    def images_edit(self, payload: dict[str, Any], image_paths: list[Path]) -> dict[str, Any]:
        if self.use_dummy or not self.api_key:
            if self.use_dummy:
                console.print("[yellow]ECON_TABLETOP_DUMMY_OPENAI enabled. Returning dummy image response.[/yellow]")
            else:
                console.print("[yellow]OPENAI_API_KEY not set. Returning dummy image response.[/yellow]")
            return {"data": [{"b64_json": ""}]}
        if not image_paths:
            raise ValueError("images_edit requires at least one reference image path.")
        image_path = image_paths[0]
        files = {"image": (image_path.name, image_path.read_bytes(), "image/png")}
        resp = self.client.post(
            f"{self.base_url}/images/edits",
            headers={k: v for k, v in self._headers().items() if k != "Content-Type"},
            data={k: v for k, v in payload.items() if v is not None},
            files=files,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            console.print(
                "[red]OpenAI image edit request failed.[/red]"
                f" Status: {resp.status_code}. Body: {resp.text}"
            )
            console.print(
                "[yellow]Check that your API key has image access and that the model name is available in "
                "your project/organization.[/yellow]"
            )
            raise
        return resp.json()

    def save_payload(self, cache_dir: Path, name: str, payload: dict[str, Any], response: dict[str, Any]) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{name}.request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        (cache_dir / f"{name}.response.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
