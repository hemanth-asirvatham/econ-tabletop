from __future__ import annotations

from pathlib import Path
from typing import Any, Coroutine, Iterable
import asyncio
import base64
import concurrent.futures
import glob
import json
import random
import shutil
import time

from rich.console import Console
from tqdm import tqdm

from deckgen.config import resolve_config
from deckgen.schemas import IMAGE_CRITIQUE_SCHEMA
from deckgen.utils.asyncio_utils import run_async
from deckgen.utils.cache import cache_dir_for
from deckgen.utils.openai_client import OpenAIClient
from deckgen.utils.parallel import gather_with_concurrency
from deckgen.utils.prompts import render_prompt
from deckgen.utils.utility_functions import dummy_image_critique

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
    text_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime_cfg.get("prompt_path")
    model = image_cfg.get("model")
    size = image_cfg.get("size")
    background = image_cfg.get("background")
    api = image_cfg.get("api", "images")
    responses_model = image_cfg.get("responses_model") or model or "gpt-5.2"
    critique_model = text_cfg.get("model") or responses_model or "gpt-5.2"
    reference_policy = image_cfg.get("reference_policy_image")
    reference_dev = image_cfg.get("reference_development_image")
    resume = runtime_cfg.get("resume", True)
    cache_requests = runtime_cfg.get("cache_requests", False)
    image_batch_size = runtime_cfg.get("image_batch_size", 150)
    concurrency = runtime_cfg.get("concurrency_image", 4)
    candidate_count = runtime_cfg.get("image_candidate_count", 25)
    reference_multiplier = runtime_cfg.get("image_reference_candidate_multiplier", 3)
    critique_concurrency = runtime_cfg.get("concurrency_text", 4)
    image_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("image_timeout_s"))
    critique_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("critique_timeout_s"))

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
        critique_model=critique_model,
        critique_reasoning_effort=text_cfg.get("reasoning_effort"),
        critique_store=text_cfg.get("store", False),
        candidate_count=candidate_count,
        reference_multiplier=reference_multiplier,
        critique_concurrency=critique_concurrency,
        prompt_path=prompt_path,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
        regen_concurrency=concurrency,
        image_timeout_s=image_timeout_s,
        critique_timeout_s=critique_timeout_s,
    )

    candidate_tasks = _build_candidate_tasks(
        cards=policies,
        card_type="policy",
        out_dir=policy_dir,
        candidate_count=candidate_count,
        reference_images=policy_ref_paths,
        client=client,
        model=model,
        responses_model=responses_model,
        api=api,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    ) + _build_candidate_tasks(
        cards=developments,
        card_type="development",
        out_dir=dev_dir,
        candidate_count=candidate_count,
        reference_images=dev_ref_paths,
        client=client,
        model=model,
        responses_model=responses_model,
        api=api,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    )

    _run_batches(
        candidate_tasks,
        image_batch_size,
        concurrency,
        desc="Card image candidates",
        timeout_s=image_timeout_s,
    )
    _finalize_best_candidates(
        tasks=candidate_tasks,
        client=client,
        prompt_path=prompt_path,
        model=critique_model,
        reasoning_effort=text_cfg.get("reasoning_effort"),
        store=text_cfg.get("store", False),
        cache_dir=cache_dir,
        concurrency=critique_concurrency,
        desc="Card image critiques",
        timeout_s=critique_timeout_s,
    )


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
    text_cfg = resolved.get("models", {}).get("text", {})
    prompt_path = runtime_cfg.get("prompt_path")
    model = image_cfg.get("model")
    size = image_cfg.get("size")
    background = image_cfg.get("background")
    api = image_cfg.get("api", "images")
    responses_model = image_cfg.get("responses_model") or model or "gpt-5.2"
    critique_model = text_cfg.get("model") or responses_model or "gpt-5.2"
    reference_policy = image_cfg.get("reference_policy_image")
    reference_dev = image_cfg.get("reference_development_image")
    resume = runtime_cfg.get("resume", True)
    cache_requests = runtime_cfg.get("cache_requests", False)
    image_batch_size = runtime_cfg.get("image_batch_size", 150)
    concurrency = runtime_cfg.get("concurrency_image", 4)
    candidate_count = runtime_cfg.get("image_candidate_count", 25)
    reference_multiplier = runtime_cfg.get("image_reference_candidate_multiplier", 3)
    critique_concurrency = runtime_cfg.get("concurrency_text", 4)
    image_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("image_timeout_s"))
    critique_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("critique_timeout_s"))

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
        critique_model=critique_model,
        critique_reasoning_effort=text_cfg.get("reasoning_effort"),
        critique_store=text_cfg.get("store", False),
        candidate_count=candidate_count,
        reference_multiplier=reference_multiplier,
        critique_concurrency=critique_concurrency,
        prompt_path=prompt_path,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
        regen_concurrency=concurrency,
        image_timeout_s=image_timeout_s,
        critique_timeout_s=critique_timeout_s,
    )

    candidate_tasks = _build_candidate_tasks(
        cards=policies,
        card_type="policy",
        out_dir=policy_dir,
        candidate_count=candidate_count,
        reference_images=policy_ref_paths,
        client=client,
        model=model,
        responses_model=responses_model,
        api=api,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    ) + _build_candidate_tasks(
        cards=developments,
        card_type="development",
        out_dir=dev_dir,
        candidate_count=candidate_count,
        reference_images=dev_ref_paths,
        client=client,
        model=model,
        responses_model=responses_model,
        api=api,
        size=size,
        background=background,
        cache_dir=cache_dir,
        resume=resume,
    )

    await _run_batches_async(
        candidate_tasks,
        image_batch_size,
        concurrency,
        desc="Card image candidates",
        timeout_s=image_timeout_s,
    )
    await _finalize_best_candidates_async(
        tasks=candidate_tasks,
        client=client,
        prompt_path=prompt_path,
        model=critique_model,
        reasoning_effort=text_cfg.get("reasoning_effort"),
        store=text_cfg.get("store", False),
        cache_dir=cache_dir,
        concurrency=critique_concurrency,
        desc="Card image critiques",
        timeout_s=critique_timeout_s,
    )


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


def _build_candidate_tasks(
    *,
    cards: list[dict[str, Any]],
    card_type: str,
    out_dir: Path,
    candidate_count: int,
    reference_images: list[Path] | None,
    client: OpenAIClient,
    model: str | None,
    responses_model: str | None,
    api: str,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
    final_suffix: str = "",
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if not cards or candidate_count <= 0:
        return tasks
    candidate_dir = out_dir / "candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    for card in cards:
        final_out_path = out_dir / f"{card['id']}{final_suffix}.png"
        for idx in range(candidate_count):
            candidate_path = candidate_dir / f"{card['id']}{final_suffix}_cand_{idx:02d}.png"
            tasks.append(
                {
                    "card": card,
                    "out_path": candidate_path,
                    "final_out_path": final_out_path,
                    "card_type": card_type,
                    "reference_images": reference_images,
                    "client": client,
                    "model": model,
                    "responses_model": responses_model,
                    "api": api,
                    "size": size,
                    "background": background,
                    "cache_dir": cache_dir,
                    "resume": resume,
                }
            )
    return tasks


def _finalize_best_candidates(
    *,
    tasks: list[dict[str, Any]],
    client: OpenAIClient,
    prompt_path: str | None,
    model: str | None,
    reasoning_effort: str | None,
    store: bool,
    cache_dir: Path | None,
    concurrency: int,
    desc: str,
    timeout_s: float | None = None,
) -> None:
    if not tasks:
        return
    run_async(
        _finalize_best_candidates_async(
            tasks=tasks,
            client=client,
            prompt_path=prompt_path,
            model=model,
            reasoning_effort=reasoning_effort,
            store=store,
            cache_dir=cache_dir,
            concurrency=concurrency,
            desc=desc,
            timeout_s=timeout_s,
        )
    )


async def _finalize_best_candidates_async(
    *,
    tasks: list[dict[str, Any]],
    client: OpenAIClient,
    prompt_path: str | None,
    model: str | None,
    reasoning_effort: str | None,
    store: bool,
    cache_dir: Path | None,
    concurrency: int,
    desc: str,
    timeout_s: float | None = None,
) -> None:
    if not tasks:
        return
    console.print(f"[cyan]{desc}: scoring {len(tasks)} candidates[/cyan]")
    scores = await _score_candidates_async(
        tasks=tasks,
        client=client,
        prompt_path=prompt_path,
        model=model,
        reasoning_effort=reasoning_effort,
        store=store,
        cache_dir=cache_dir,
        concurrency=concurrency,
        timeout_s=timeout_s,
    )
    _select_best_candidates(tasks, scores)


async def _score_candidates_async(
    *,
    tasks: list[dict[str, Any]],
    client: OpenAIClient,
    prompt_path: str | None,
    model: str | None,
    reasoning_effort: str | None,
    store: bool,
    cache_dir: Path | None,
    concurrency: int,
    timeout_s: float | None = None,
) -> list[int]:
    resolved_concurrency = _resolve_concurrency(len(tasks), concurrency)
    return await gather_with_concurrency(
        resolved_concurrency,
        [
            lambda task=task: _critique_image_task(
                task=task,
                client=client,
                prompt_path=prompt_path,
                model=model,
                reasoning_effort=reasoning_effort,
                store=store,
                cache_dir=cache_dir,
                timeout_s=timeout_s,
            )
            for task in tasks
        ],
        timeout=timeout_s,
        fallback=0,
    )


def _select_best_candidates(tasks: list[dict[str, Any]], scores: list[int]) -> None:
    grouped: dict[str, list[tuple[dict[str, Any], int]]] = {}
    for task, score in zip(tasks, scores):
        card_id = task["card"]["id"]
        grouped.setdefault(card_id, []).append((task, score))

    for card_id, entries in grouped.items():
        max_score = max(score for _, score in entries)
        top_entries = [task for task, score in entries if score == max_score]
        chosen_task = random.choice(top_entries)
        final_path = chosen_task["final_out_path"]
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(chosen_task["out_path"], final_path)
        for task, _ in entries:
            if task["out_path"].exists():
                task["out_path"].unlink(missing_ok=True)

    _cleanup_candidate_dirs(tasks)


def _cleanup_candidate_dirs(tasks: list[dict[str, Any]]) -> None:
    candidate_dirs = {task["out_path"].parent for task in tasks}
    for candidate_dir in candidate_dirs:
        if candidate_dir.exists() and not any(candidate_dir.iterdir()):
            candidate_dir.rmdir()


async def _critique_image_task(
    *,
    task: dict[str, Any],
    client: OpenAIClient,
    prompt_path: str | None,
    model: str | None,
    reasoning_effort: str | None,
    store: bool,
    cache_dir: Path | None,
    timeout_s: float | None,
) -> int:
    out_path = task["out_path"]
    if not out_path.exists() or out_path.stat().st_size == 0:
        return 0
    card = task["card"]
    card_type = task["card_type"]
    if client.use_dummy or not client.api_key:
        return int(dummy_image_critique(card=card, card_type=card_type).get("rating", 0))
    prompt = render_prompt(
        "image_critique.jinja",
        prompt_path=prompt_path,
        card=card,
        card_type=card_type,
    )
    payload = _build_image_critique_payload(
        prompt=prompt,
        model=model,
        image_path=out_path,
        reasoning_effort=reasoning_effort,
        store=store,
    )
    try:
        if timeout_s is not None and timeout_s > 0:
            response = await asyncio.wait_for(client.responses_async(payload), timeout=timeout_s)
        else:
            response = await client.responses_async(payload)
    except asyncio.TimeoutError:
        console.print(f"[yellow]Image critique timed out for {card.get('id', 'card')}.[/yellow]")
        return 0
    except Exception as exc:  # noqa: BLE001 - keep image runs resilient
        console.print(
            f"[yellow]Image critique failed for {card.get('id', 'card')}. Reason: {exc}[/yellow]"
        )
        return 0
    if cache_dir:
        client.save_payload(cache_dir, f"image_critique_{card['id']}_{out_path.stem}", payload, response)
    parsed = _parse_image_critique_response(response)
    if parsed is None:
        return 0
    return int(parsed.get("rating", 0))


def _build_image_critique_payload(
    *,
    prompt: str,
    model: str | None,
    image_path: Path,
    reasoning_effort: str | None,
    store: bool,
) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": _encode_image_data_url(image_path)},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "image_critique",
                "schema": IMAGE_CRITIQUE_SCHEMA,
                "strict": True,
            }
        },
        "store": store,
        **({"reasoning": {"effort": reasoning_effort}} if reasoning_effort else {}),
    }


def _parse_image_critique_response(response: dict[str, Any]) -> dict[str, Any] | None:
    for output in response.get("output", []):
        for item in output.get("content", []):
            if item.get("json") and isinstance(item["json"], dict):
                return item["json"]
            text = item.get("text") or item.get("json")
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, dict):
                    return parsed
    return None


def _encode_image_data_url(path: Path) -> str:
    mime = _guess_image_mime(path)
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _guess_image_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".png":
        return "image/png"
    return "application/octet-stream"


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
    critique_model: str | None,
    critique_reasoning_effort: str | None,
    critique_store: bool,
    candidate_count: int,
    reference_multiplier: int,
    critique_concurrency: int,
    prompt_path: str | None,
    size: str | None,
    background: str | None,
    cache_dir: Path | None,
    resume: bool,
    regen_concurrency: int,
    image_timeout_s: float | None,
    critique_timeout_s: float | None,
) -> tuple[list[Path] | None, list[Path] | None]:
    policy_ref_paths = _resolve_reference_paths(reference_policy)
    dev_ref_paths = _resolve_reference_paths(reference_dev)

    reference_tasks: list[dict[str, Any]] = []
    policy_reference_out: Path | None = None
    dev_reference_out: Path | None = None

    reference_candidate_count = max(1, candidate_count * max(1, reference_multiplier))

    if policy_ref_paths is None and policies:
        reference_card = policies[0]
        policy_reference_out = policy_dir / f"{reference_card['id']}_reference.png"
        reference_tasks.extend(
            _build_candidate_tasks(
                cards=[reference_card],
                card_type="policy",
                out_dir=policy_dir,
                candidate_count=reference_candidate_count,
                reference_images=None,
                client=client,
                model=model,
                responses_model=responses_model,
                api=api,
                size=size,
                background=background,
                cache_dir=cache_dir,
                resume=resume,
                final_suffix="_reference",
            )
        )

    if dev_ref_paths is None and developments:
        reference_card = developments[0]
        dev_reference_out = dev_dir / f"{reference_card['id']}_reference.png"
        reference_tasks.extend(
            _build_candidate_tasks(
                cards=[reference_card],
                card_type="development",
                out_dir=dev_dir,
                candidate_count=reference_candidate_count,
                reference_images=None,
                client=client,
                model=model,
                responses_model=responses_model,
                api=api,
                size=size,
                background=background,
                cache_dir=cache_dir,
                resume=resume,
                final_suffix="_reference",
            )
        )

    if reference_tasks:
        _run_batches(
            reference_tasks,
            batch_size=len(reference_tasks),
            concurrency=regen_concurrency,
            desc="Reference image candidates",
            timeout_s=image_timeout_s,
        )
        _finalize_best_candidates(
            tasks=reference_tasks,
            client=client,
            prompt_path=prompt_path,
            model=critique_model,
            reasoning_effort=critique_reasoning_effort,
            store=critique_store,
            cache_dir=cache_dir,
            concurrency=critique_concurrency,
            desc="Reference image critiques",
            timeout_s=critique_timeout_s,
        )

    if policy_ref_paths is None and policy_reference_out is not None:
        policy_ref_paths = [policy_reference_out]
    if dev_ref_paths is None and dev_reference_out is not None:
        dev_ref_paths = [dev_reference_out]

    return policy_ref_paths, dev_ref_paths


def _resolve_reference_paths(reference_path: str | None) -> list[Path] | None:
    if reference_path:
        reference_paths = _gather_reference_paths(reference_path)
        if reference_paths:
            return reference_paths
        console.print(
            "[yellow]Reference image(s) not found or empty. Generating a fresh reference.[/yellow]"
        )
    return None


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
    timeout_s: float | None = None,
) -> None:
    if not tasks:
        return
    resolved_batch_size = _resolve_batch_size(tasks, batch_size)
    total_batches = (len(tasks) + resolved_batch_size - 1) // resolved_batch_size
    for batch_index, batch in enumerate(_chunked(tasks, resolved_batch_size)):
        console.print(f"[cyan]{desc}: batch {batch_index + 1}/{total_batches}[/cyan]")
        max_workers = _resolve_concurrency(len(batch), concurrency)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        futures = [
            executor.submit(_generate_card_image, **_strip_generation_task(task)) for task in batch
        ]
        pending = set(futures)
        start_times = {future: time.monotonic() for future in futures}
        with tqdm(total=len(futures), desc=desc) as progress:
            try:
                while pending:
                    done, pending = concurrent.futures.wait(
                        pending,
                        timeout=0.2,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    for future in done:
                        try:
                            future.result()
                        except Exception as exc:  # noqa: BLE001 - best-effort image runs
                            console.print(f"[yellow]Image task failed. Reason: {exc}[/yellow]")
                        progress.update(1)
                    if timeout_s is None or timeout_s <= 0:
                        continue
                    now = time.monotonic()
                    timed_out = [
                        future
                        for future in pending
                        if now - start_times.get(future, now) > timeout_s
                    ]
                    for future in timed_out:
                        future.cancel()
                        pending.discard(future)
                        progress.update(1)
                        console.print("[yellow]Image task timed out; skipping remaining work for that task.[/yellow]")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)


async def _run_batches_async(
    tasks: list[dict[str, Any]],
    batch_size: int,
    concurrency: int,
    *,
    desc: str,
    timeout_s: float | None = None,
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
                try:
                    thread_task = asyncio.to_thread(_generate_card_image, **_strip_generation_task(task))
                    if timeout_s is not None and timeout_s > 0:
                        await asyncio.wait_for(thread_task, timeout=timeout_s)
                    else:
                        await thread_task
                except asyncio.TimeoutError:
                    console.print("[yellow]Image task timed out; skipping remaining work for that task.[/yellow]")
                except Exception as exc:  # noqa: BLE001 - best-effort image runs
                    console.print(f"[yellow]Image task failed. Reason: {exc}[/yellow]")

        coros = [_run_task(task) for task in batch]
        for coro in tqdm(asyncio.as_completed(coros), total=len(coros), desc=desc):
            await coro


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _strip_generation_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if key not in {"card_type", "final_out_path"}}


def _resolve_batch_size(tasks: list[dict[str, Any]], batch_size: int) -> int:
    if batch_size <= 0:
        return len(tasks)
    return max(1, batch_size)


def _resolve_concurrency(task_count: int, concurrency: int) -> int:
    if concurrency <= 0:
        return task_count
    return max(1, min(concurrency, task_count))


def _resolve_timeout_seconds(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed
