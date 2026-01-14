from __future__ import annotations

from pathlib import Path
from typing import Any, Coroutine, Iterable
import asyncio
import base64
import concurrent.futures
import glob

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
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(generate_images_async(config, policies, developments, out_dir))
    else:
        console.print(
            "[yellow]Active event loop detected; running image generation asynchronously in a worker thread.[/yellow]"
        )
        _run_async_in_thread(generate_images_async(config, policies, developments, out_dir))


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
    api = image_cfg.get("api", "images")
    responses_model = image_cfg.get("responses_model") or model or "gpt-5.2"
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

    policy_ref_paths, dev_ref_paths = _prepare_reference_images(
        api=api,
        reference_policy=reference_policy,
        reference_dev=reference_dev,
        policy_dir=policy_dir,
        dev_dir=dev_dir,
        policies=policies,
        developments=developments,
        client=client,
        model=model,
        responses_model=responses_model,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    )

    policy_tasks = [
        {
            "card": card,
            "out_path": policy_dir / f"{card['id']}.png",
            "reference_images": policy_ref_paths,
            "client": client,
            "model": model,
            "responses_model": responses_model,
            "api": api,
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
            "reference_images": dev_ref_paths,
            "client": client,
            "model": model,
            "responses_model": responses_model,
            "api": api,
            "size": size,
            "background": background,
            "cache_dir": cache_dir,
            "resume": resume,
        }
        for card in developments
    ]

    all_tasks = policy_tasks + dev_tasks
    _run_batches(all_tasks, image_batch_size, concurrency, desc="Card images")


def _run_async_in_thread(coro: Coroutine[Any, Any, None]) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        future.result()


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
    api = image_cfg.get("api", "images")
    responses_model = image_cfg.get("responses_model") or model or "gpt-5.2"
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

    policy_ref_paths, dev_ref_paths = _prepare_reference_images(
        api=api,
        reference_policy=reference_policy,
        reference_dev=reference_dev,
        policy_dir=policy_dir,
        dev_dir=dev_dir,
        policies=policies,
        developments=developments,
        client=client,
        model=model,
        responses_model=responses_model,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    )

    policy_tasks = [
        {
            "card": card,
            "out_path": policy_dir / f"{card['id']}.png",
            "reference_images": policy_ref_paths,
            "client": client,
            "model": model,
            "responses_model": responses_model,
            "api": api,
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
            "reference_images": dev_ref_paths,
            "client": client,
            "model": model,
            "responses_model": responses_model,
            "api": api,
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
    reference_images: list[Path] | None,
    client: OpenAIClient,
    model: str | None,
    responses_model: str | None,
    api: str,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
) -> None:
    if resume and out_path.exists() and out_path.stat().st_size > 0:
        return
    prompt = card.get("art_prompt") or f"Horizontal illustration for {card.get('title', 'card')}."
    payload: dict[str, Any] = {"model": model, "prompt": prompt}
    if size is not None:
        payload["size"] = size
    if background is not None:
        payload["background"] = background
    response: dict[str, Any] | None = None
    payload_for_cache = payload
    try:
        if api == "responses":
            payload_for_cache = client.build_image_responses_payload(
                prompt=prompt,
                model=responses_model,
                size=size,
                background=background,
                reference_images=reference_images,
            )
            response = client.responses(payload_for_cache)
        elif reference_images:
            try:
                response = client.images_edit(payload, reference_images)
            except Exception as exc:  # noqa: BLE001 - fallback for edit failures
                console.print(
                    f"[yellow]Image edit failed for {card.get('id', 'card')}; "
                    f"falling back to generation. Reason: {exc}[/yellow]"
                )
                response = client.images_generate(payload)
        else:
            response = client.images_generate(payload)
    except Exception as exc:  # noqa: BLE001 - guard against per-card failures
        console.print(
            f"[red]Image generation failed for {card.get('id', 'card')}. "
            f"Saving placeholder. Reason: {exc}[/red]"
        )
        out_path.write_bytes(base64.b64decode(_DUMMY_PNG_BASE64))
        return

    if response is None:
        out_path.write_bytes(base64.b64decode(_DUMMY_PNG_BASE64))
        return

    if cache_dir:
        client.save_payload(cache_dir, f"image_{card['id']}", payload_for_cache, response)

    data = client.extract_image_b64(response) or _DUMMY_PNG_BASE64
    try:
        out_path.write_bytes(base64.b64decode(data))
    except Exception as exc:  # noqa: BLE001 - guard against corrupt payloads
        console.print(
            f"[yellow]Invalid image data for {card.get('id', 'card')}. "
            f"Saving placeholder. Reason: {exc}[/yellow]"
        )
        out_path.write_bytes(base64.b64decode(_DUMMY_PNG_BASE64))


def _prepare_reference_images(
    *,
    api: str,
    reference_policy: str | None,
    reference_dev: str | None,
    policy_dir: Path,
    dev_dir: Path,
    policies: list[dict[str, Any]],
    developments: list[dict[str, Any]],
    client: OpenAIClient,
    model: str | None,
    responses_model: str | None,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
) -> tuple[list[Path] | None, list[Path] | None]:
    policy_ref_paths = _resolve_reference_images(
        reference_policy,
        policy_dir,
        policies,
        client,
        model,
        responses_model,
        api,
        size,
        background,
        cache_dir,
        resume,
    )
    dev_ref_paths = _resolve_reference_images(
        reference_dev,
        dev_dir,
        developments,
        client,
        model,
        responses_model,
        api,
        size,
        background,
        cache_dir,
        resume,
    )
    return policy_ref_paths, dev_ref_paths


def _resolve_reference_images(
    reference_path: str | None,
    out_dir: Path,
    cards: list[dict[str, Any]],
    client: OpenAIClient,
    model: str | None,
    responses_model: str | None,
    api: str,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
) -> list[Path] | None:
    if reference_path:
        reference_paths = _gather_reference_paths(reference_path)
        if reference_paths:
            return reference_paths
        console.print(
            "[yellow]Reference image(s) not found or empty. Generating a fresh reference.[/yellow]"
        )
    if not cards:
        return None
    reference_card = cards[0]
    reference_out = out_dir / f"{reference_card['id']}_reference.png"
    _generate_card_image(
        card=reference_card,
        out_path=reference_out,
        reference_images=None,
        client=client,
        model=model,
        responses_model=responses_model,
        api=api,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    )
    return [reference_out]


def _gather_reference_paths(reference_path: str) -> list[Path]:
    paths: list[Path] = []
    parts = [part.strip() for part in reference_path.split(",") if part.strip()]
    if not parts:
        return paths
    for part in parts:
        expanded = Path(part).expanduser()
        if any(char in part for char in ["*", "?", "["]):
            matches = sorted(Path(match) for match in glob.glob(str(expanded)))
            paths.extend([match for match in matches if match.is_file()])
            continue
        if expanded.exists():
            if expanded.is_dir():
                paths.extend(_list_image_files(expanded))
            else:
                paths.append(expanded)
            continue
        console.print(f"[yellow]Reference image not found at {expanded}.[/yellow]")
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _list_image_files(directory: Path) -> list[Path]:
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    files = [
        path
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in allowed
    ]
    if not files:
        console.print(f"[yellow]No reference images found in directory {directory}.[/yellow]")
    return files


def _run_batches(
    tasks: list[dict[str, Any]],
    batch_size: int,
    concurrency: int,
    *,
    desc: str,
) -> None:
    if not tasks:
        return
    resolved_batch_size = _resolve_batch_size(tasks, batch_size)
    total_batches = (len(tasks) + resolved_batch_size - 1) // resolved_batch_size
    for batch_index, batch in enumerate(_chunked(tasks, resolved_batch_size)):
        console.print(f"[cyan]{desc}: batch {batch_index + 1}/{total_batches}[/cyan]")
        max_workers = _resolve_concurrency(len(batch), concurrency)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
    resolved_batch_size = _resolve_batch_size(tasks, batch_size)
    total_batches = (len(tasks) + resolved_batch_size - 1) // resolved_batch_size
    for batch_index, batch in enumerate(_chunked(tasks, resolved_batch_size)):
        console.print(f"[cyan]{desc}: batch {batch_index + 1}/{total_batches}[/cyan]")
        semaphore = asyncio.Semaphore(_resolve_concurrency(len(batch), concurrency))

        async def _run_task(task: dict[str, Any]) -> None:
            async with semaphore:
                await asyncio.to_thread(_generate_card_image, **task)

        coros = [_run_task(task) for task in batch]
        for coro in tqdm(asyncio.as_completed(coros), total=len(coros), desc=desc):
            await coro


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _resolve_batch_size(tasks: list[dict[str, Any]], batch_size: int) -> int:
    if batch_size <= 0:
        return len(tasks)
    return max(1, batch_size)


def _resolve_concurrency(task_count: int, concurrency: int) -> int:
    if concurrency <= 0:
        return task_count
    return max(1, min(concurrency, task_count))
