from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

console = Console()


class OpenAIClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url
        self.client = httpx.Client(timeout=120)

    def responses(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            console.print("[yellow]OPENAI_API_KEY not set. Returning dummy response.[/yellow]")
            return {"output": [{"content": [{"type": "output_text", "text": json.dumps({})}]}]}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = self.client.post(f"{self.base_url}/responses", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def images_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            console.print("[yellow]OPENAI_API_KEY not set. Returning dummy image response.[/yellow]")
            return {"data": [{"b64_json": ""}]}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = self.client.post(f"{self.base_url}/images/generations", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def save_payload(self, cache_dir: Path, name: str, payload: dict[str, Any], response: dict[str, Any]) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{name}.request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        (cache_dir / f"{name}.response.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
