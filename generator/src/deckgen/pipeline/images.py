from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import asyncio
import base64
import concurrent.futures

from rich.console import Console
from tqdm import tqdm

from deckgen.config import resolve_config
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.openai_client import OpenAIClient

console = Console()


_DUMMY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/xcAAwMCAOqf2m0AAAAASUVORK5CYII="
)


def generate_images(
    config: dict[str, Any],
    policies: list[dict[str, Any]],
    developments: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(generate_images_async(config, policies, developments, out_dir))
    else:
        console.print("[yellow]Active event loop detected; running image generation synchronously.[/yellow]")
        _generate_images_sync(config, policies, developments, out_dir)


def _generate_images_sync(
    config: dict[str, Any],
    policies: list[dict[str, Any]],
    developments: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    resolved = resolve_config(config)
    image_cfg = resolved.get("models", {}).get("image", {})
    runtime_cfg = resolved.get("runtime", {})
    model = image_cfg.get("model")
    size = image_cfg.get("size")
    background = image_cfg.get("background")
    reference_policy = image_cfg.get("reference_policy_image")
    reference_dev = image_cfg.get("reference_development_image")
    resume = runtime_cfg.get("resume", True)
    cache_requests = runtime_cfg.get("cache_requests", False)
    image_batch_size = runtime_cfg.get("image_batch_size", 150)
    concurrency = runtime_cfg.get("concurrency_image", 4)

    console.print(f"[cyan]Generating {len(policies)} policy images and {len(developments)} development images.[/cyan]")
    policy_dir = out_dir / "images" / "policy"
    dev_dir = out_dir / "images" / "development"
    thumbs_dir = out_dir / "render" / "thumbs"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    cache_dir = cache_dir_for(out_dir) if cache_requests else None
    client = OpenAIClient()

    policy_ref_path = _resolve_reference_image(
        reference_policy,
        policy_dir,
        policies,
        client,
        model,
        size,
        background,
        cache_dir,
        resume,
    )
    dev_ref_path = _resolve_reference_image(
        reference_dev,
        dev_dir,
        developments,
        client,
        model,
        size,
        background,
        cache_dir,
        resume,
    )

    policy_tasks = [
        {
            "card": card,
            "out_path": policy_dir / f"{card['id']}.png",
            "reference_image": policy_ref_path,
            "client": client,
            "model": model,
            "size": size,
            "background": background,
            "cache_dir": cache_dir,
            "resume": resume,
        }
        for card in policies
    ]
    dev_tasks = [
        {
            "card": card,
            "out_path": dev_dir / f"{card['id']}.png",
            "reference_image": dev_ref_path,
            "client": client,
            "model": model,
            "size": size,
            "background": background,
            "cache_dir": cache_dir,
            "resume": resume,
        }
        for card in developments
    ]

    all_tasks = policy_tasks + dev_tasks
    _run_batches(all_tasks, image_batch_size, concurrency, desc="Card images")


async def generate_images_async(
    config: dict[str, Any],
    policies: list[dict[str, Any]],
    developments: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    resolved = resolve_config(config)
    image_cfg = resolved.get("models", {}).get("image", {})
    runtime_cfg = resolved.get("runtime", {})
    model = image_cfg.get("model")
    size = image_cfg.get("size")
    background = image_cfg.get("background")
    reference_policy = image_cfg.get("reference_policy_image")
    reference_dev = image_cfg.get("reference_development_image")
    resume = runtime_cfg.get("resume", True)
    cache_requests = runtime_cfg.get("cache_requests", False)
    image_batch_size = runtime_cfg.get("image_batch_size", 150)
    concurrency = runtime_cfg.get("concurrency_image", 4)

    console.print(f"[cyan]Generating {len(policies)} policy images and {len(developments)} development images.[/cyan]")
    policy_dir = out_dir / "images" / "policy"
    dev_dir = out_dir / "images" / "development"
    thumbs_dir = out_dir / "render" / "thumbs"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    cache_dir = cache_dir_for(out_dir) if cache_requests else None
    client = OpenAIClient()

    policy_ref_path = _resolve_reference_image(
        reference_policy,
        policy_dir,
        policies,
        client,
        model,
        size,
        background,
        cache_dir,
        resume,
    )
    dev_ref_path = _resolve_reference_image(
        reference_dev,
        dev_dir,
        developments,
        client,
        model,
        size,
        background,
        cache_dir,
        resume,
    )

    policy_tasks = [
        {
            "card": card,
            "out_path": policy_dir / f"{card['id']}.png",
            "reference_image": policy_ref_path,
            "client": client,
            "model": model,
            "size": size,
            "background": background,
            "cache_dir": cache_dir,
            "resume": resume,
        }
        for card in policies
    ]
    dev_tasks = [
        {
            "card": card,
            "out_path": dev_dir / f"{card['id']}.png",
            "reference_image": dev_ref_path,
            "client": client,
            "model": model,
            "size": size,
            "background": background,
            "cache_dir": cache_dir,
            "resume": resume,
        }
        for card in developments
    ]

    all_tasks = policy_tasks + dev_tasks
    await _run_batches_async(all_tasks, image_batch_size, concurrency, desc="Card images")


def _generate_card_image(
    *,
    card: dict[str, Any],
    out_path: Path,
    reference_image: Path | None,
    client: OpenAIClient,
    model: str | None,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
) -> None:
    if resume and out_path.exists():
        return
    prompt = card.get("art_prompt") or f"Horizontal illustration for {card.get('title', 'card')}."
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
    }
    if size is not None:
        payload["size"] = size
    if background is not None:
        payload["background"] = background
    if reference_image:
        response = client.images_edit(payload, [reference_image])
    else:
        response = client.images_generate(payload)
    if cache_dir:
        client.save_payload(cache_dir, f"image_{card['id']}", payload, response)

    data = (response.get("data") or [{}])[0].get("b64_json") or _DUMMY_PNG_BASE64
    out_path.write_bytes(base64.b64decode(data))


def _resolve_reference_image(
    reference_path: str | None,
    out_dir: Path,
    cards: list[dict[str, Any]],
    client: OpenAIClient,
    model: str | None,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
) -> Path | None:
    if reference_path:
        ref = Path(reference_path).expanduser().resolve()
        if ref.exists():
            return ref
        console.print(f"[yellow]Reference image not found at {ref}. Generating a fresh reference.[/yellow]")
    if not cards:
        return None
    reference_card = cards[0]
    reference_out = out_dir / f"{reference_card['id']}_reference.png"
    _generate_card_image(
        card=reference_card,
        out_path=reference_out,
        reference_image=None,
        client=client,
        model=model,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    )
    return reference_out


def _run_batches(
    tasks: list[dict[str, Any]],
    batch_size: int,
    concurrency: int,
    *,
    desc: str,
) -> None:
    if not tasks:
        return
    total_batches = (len(tasks) + batch_size - 1) // batch_size
    for batch_index, batch in enumerate(_chunked(tasks, batch_size)):
        console.print(f"[cyan]{desc}: batch {batch_index + 1}/{total_batches}[/cyan]")
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_generate_card_image, **task) for task in batch]
            for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc=desc):
                pass


async def _run_batches_async(
    tasks: list[dict[str, Any]],
    batch_size: int,
    concurrency: int,
    *,
    desc: str,
) -> None:
    if not tasks:
        return
    total_batches = (len(tasks) + batch_size - 1) // batch_size
    for batch_index, batch in enumerate(_chunked(tasks, batch_size)):
        console.print(f"[cyan]{desc}: batch {batch_index + 1}/{total_batches}[/cyan]")
        semaphore = asyncio.Semaphore(concurrency)

        async def _run_task(task: dict[str, Any]) -> None:
            async with semaphore:
                await asyncio.to_thread(_generate_card_image, **task)

        coros = [_run_task(task) for task in batch]
        for coro in tqdm(asyncio.as_completed(coros), total=len(coros), desc=desc):
            await coro


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
