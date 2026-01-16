from __future__ import annotations

from pathlib import Path
from typing import Any, Coroutine
import asyncio
import base64
import concurrent.futures
import glob
import json
import math
import random
import shutil

from rich.console import Console
from tqdm import tqdm

from deckgen.config import resolve_config
from deckgen.schemas import IMAGE_CRITIQUE_SCHEMA
from deckgen.utils.asyncio_utils import run_async
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
    model = image_cfg.get("model") or "gpt-image-1.5"
    size = image_cfg.get("size")
    quality = image_cfg.get("quality") or "auto"
    reference_quality = image_cfg.get("reference_quality") or quality
    background = image_cfg.get("background")
    api = image_cfg.get("api", "images")
    if api != "images":
        console.print("[yellow]Overriding image API to 'images' for consistent generation.[/yellow]")
        api = "images"
    if model != "gpt-image-1.5":
        console.print("[yellow]Overriding image model to gpt-image-1.5 for consistent generation.[/yellow]")
        model = "gpt-image-1.5"
    responses_model = image_cfg.get("responses_model") or model or "gpt-5.2"
    critique_model = text_cfg.get("model") or responses_model or "gpt-5.2"
    reference_policy = image_cfg.get("reference_policy_image")
    reference_dev = image_cfg.get("reference_development_image")
    resume = runtime_cfg.get("resume", True)
    concurrency = runtime_cfg.get("concurrency_image", 4)
    candidate_count = _normalize_candidate_count(runtime_cfg.get("image_candidate_count", 8))
    reference_multiplier = runtime_cfg.get("image_reference_candidate_multiplier", 5)
    critique_concurrency = runtime_cfg.get("concurrency_text", 4)
    image_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("image_timeout_s"))
    critique_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("critique_timeout_s"))
    image_retry_limit = int(runtime_cfg.get("image_retry_limit", 0) or 0)
    critique_retry_limit = int(runtime_cfg.get("critique_retry_limit", 0) or 0)

    console.print(f"[cyan]Generating {len(policies)} policy images and {len(developments)} development images.[/cyan]")
    policy_dir = out_dir / "images" / "policy"
    dev_dir = out_dir / "images" / "development"
    thumbs_dir = out_dir / "render" / "thumbs"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

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
        reference_quality=reference_quality,
        background=background,
        resume=resume,
        regen_concurrency=concurrency,
        image_timeout_s=image_timeout_s,
        critique_timeout_s=critique_timeout_s,
        image_retry_limit=image_retry_limit,
        critique_retry_limit=critique_retry_limit,
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
        quality=quality,
        background=background,
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
        quality=quality,
        background=background,
        resume=resume,
    )

    _run_generation_tasks(
        candidate_tasks,
        concurrency,
        desc="Card image candidates",
        timeout_s=image_timeout_s,
        retry_limit=image_retry_limit,
    )
    _finalize_best_candidates(
        tasks=candidate_tasks,
        client=client,
        prompt_path=prompt_path,
        model=critique_model,
        reasoning_effort=text_cfg.get("reasoning_effort"),
        store=text_cfg.get("store", False),
        concurrency=critique_concurrency,
        desc="Card image critiques",
        timeout_s=critique_timeout_s,
        retry_limit=critique_retry_limit,
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
    model = image_cfg.get("model") or "gpt-image-1.5"
    size = image_cfg.get("size")
    quality = image_cfg.get("quality") or "auto"
    reference_quality = image_cfg.get("reference_quality") or quality
    background = image_cfg.get("background")
    api = image_cfg.get("api", "images")
    if api != "images":
        console.print("[yellow]Overriding image API to 'images' for consistent generation.[/yellow]")
        api = "images"
    if model != "gpt-image-1.5":
        console.print("[yellow]Overriding image model to gpt-image-1.5 for consistent generation.[/yellow]")
        model = "gpt-image-1.5"
    responses_model = image_cfg.get("responses_model") or model or "gpt-5.2"
    critique_model = text_cfg.get("model") or responses_model or "gpt-5.2"
    reference_policy = image_cfg.get("reference_policy_image")
    reference_dev = image_cfg.get("reference_development_image")
    resume = runtime_cfg.get("resume", True)
    concurrency = runtime_cfg.get("concurrency_image", 4)
    candidate_count = _normalize_candidate_count(runtime_cfg.get("image_candidate_count", 8))
    reference_multiplier = runtime_cfg.get("image_reference_candidate_multiplier", 5)
    critique_concurrency = runtime_cfg.get("concurrency_text", 4)
    image_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("image_timeout_s"))
    critique_timeout_s = _resolve_timeout_seconds(runtime_cfg.get("critique_timeout_s"))
    image_retry_limit = int(runtime_cfg.get("image_retry_limit", 0) or 0)
    critique_retry_limit = int(runtime_cfg.get("critique_retry_limit", 0) or 0)

    console.print(f"[cyan]Generating {len(policies)} policy images and {len(developments)} development images.[/cyan]")
    policy_dir = out_dir / "images" / "policy"
    dev_dir = out_dir / "images" / "development"
    thumbs_dir = out_dir / "render" / "thumbs"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

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
        reference_quality=reference_quality,
        background=background,
        resume=resume,
        regen_concurrency=concurrency,
        image_timeout_s=image_timeout_s,
        critique_timeout_s=critique_timeout_s,
        image_retry_limit=image_retry_limit,
        critique_retry_limit=critique_retry_limit,
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
        quality=quality,
        background=background,
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
        quality=quality,
        background=background,
        resume=resume,
    )

    await _run_generation_tasks_async(
        candidate_tasks,
        concurrency,
        desc="Card image candidates",
        timeout_s=image_timeout_s,
        retry_limit=image_retry_limit,
    )
    await _finalize_best_candidates_async(
        tasks=candidate_tasks,
        client=client,
        prompt_path=prompt_path,
        model=critique_model,
        reasoning_effort=text_cfg.get("reasoning_effort"),
        store=text_cfg.get("store", False),
        concurrency=critique_concurrency,
        desc="Card image critiques",
        timeout_s=critique_timeout_s,
        retry_limit=critique_retry_limit,
    )


def _generate_card_images(
    *,
    card: dict[str, Any],
    out_paths: list[Path],
    reference_images: list[Path] | None,
    client: OpenAIClient,
    model: str | None,
    responses_model: str | None,
    api: str,
    size: str | None,
    quality: str | None,
    background: str | None,
    resume: bool,
) -> None:
    if not out_paths:
        return
    pending_paths = [
        path for path in out_paths if not (resume and path.exists() and path.stat().st_size > 0)
    ]
    if not pending_paths:
        return
    prompt = card.get("art_prompt") or f"Horizontal illustration for {card.get('title', 'card')}."
    payload: dict[str, Any] = {"model": model, "prompt": prompt}
    if api == "images":
        payload["n"] = len(pending_paths)
    if size is not None:
        payload["size"] = size
    if quality is not None:
        payload["quality"] = quality
    if background is not None:
        payload["background"] = background
    response: dict[str, Any] | None = None
    payload_for_cache = payload
    try:
        if api == "responses":
            if len(pending_paths) > 1:
                console.print(
                    "[yellow]Responses API image generation does not support batching; "
                    "limiting to one output.[/yellow]"
                )
                pending_paths = pending_paths[:1]
            payload_for_cache = client.build_image_responses_payload(
                prompt=prompt,
                response_model=responses_model,
                image_model=model,
                size=size,
                quality=quality,
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
        for path in pending_paths:
            path.write_bytes(base64.b64decode(_DUMMY_PNG_BASE64))
        return

    if response is None:
        for path in pending_paths:
            path.write_bytes(base64.b64decode(_DUMMY_PNG_BASE64))
        return

    data_list = _extract_image_b64_list(client, response)
    if not data_list:
        data_list = []
    for path, data in zip(pending_paths, data_list + [_DUMMY_PNG_BASE64] * len(pending_paths)):
        try:
            path.write_bytes(base64.b64decode(data))
        except Exception as exc:  # noqa: BLE001 - guard against corrupt payloads
            console.print(
                f"[yellow]Invalid image data for {card.get('id', 'card')}. "
                f"Saving placeholder. Reason: {exc}[/yellow]"
            )
            path.write_bytes(base64.b64decode(_DUMMY_PNG_BASE64))


def _build_candidate_tasks(
    *,
    cards: list[dict[str, Any]],
    card_type: str,
    out_dir: Path,
    candidate_count: int,
    reference_images: list[Path] | None,
    is_reference: bool = False,
    client: OpenAIClient,
    model: str | None,
    responses_model: str | None,
    api: str,
    size: str | None,
    quality: str | None,
    background: str | None,
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
        alias_out_paths: list[Path] = []
        if card_type == "development" and card.get("card_type") == "power":
            alias_out_paths.append(out_dir / f"power_{card['id']}{final_suffix}.png")
        reference_image = reference_images[0] if reference_images else None
        for idx in range(candidate_count):
            candidate_path = candidate_dir / f"{card['id']}{final_suffix}_cand_{idx:02d}.png"
            tasks.append(
                {
                    "card": card,
                    "out_path": candidate_path,
                    "final_out_path": final_out_path,
                    "alias_out_paths": alias_out_paths,
                    "card_type": card_type,
                    "reference_images": reference_images,
                    "reference_image": reference_image,
                    "is_reference": is_reference,
                    "client": client,
                    "model": model,
                    "responses_model": responses_model,
                    "api": api,
                    "size": size,
                    "quality": quality,
                    "background": background,
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
    concurrency: int,
    desc: str,
    timeout_s: float | None = None,
    retry_limit: int = 0,
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
            concurrency=concurrency,
            desc=desc,
            timeout_s=timeout_s,
            retry_limit=retry_limit,
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
    concurrency: int,
    desc: str,
    timeout_s: float | None = None,
    retry_limit: int = 0,
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
        concurrency=concurrency,
        timeout_s=timeout_s,
        retry_limit=retry_limit,
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
    concurrency: int,
    timeout_s: float | None = None,
    retry_limit: int = 0,
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
                timeout_s=timeout_s,
                retry_limit=retry_limit,
            )
            for task in tasks
        ],
        timeout=timeout_s,
        fallback=0,
    )


_CANDIDATE_KEEP_COUNT = 2


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
        for alias_path in chosen_task.get("alias_out_paths", []):
            alias_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(chosen_task["out_path"], alias_path)

        sorted_entries = sorted(entries, key=lambda entry: entry[1], reverse=True)
        keep_limit = max(0, min(_CANDIDATE_KEEP_COUNT, len(sorted_entries) - 1))
        keep_paths: set[Path] = set()
        for task, _ in sorted_entries:
            if task["out_path"] == chosen_task["out_path"]:
                continue
            keep_paths.add(task["out_path"])
            if len(keep_paths) >= keep_limit:
                break

        for task, _ in entries:
            if task["out_path"] in keep_paths:
                continue
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
    timeout_s: float | None,
    retry_limit: int = 0,
) -> int:
    out_path = task["out_path"]
    if not out_path.exists() or out_path.stat().st_size == 0:
        return 0
    card = task["card"]
    card_type = task["card_type"]
    is_reference = bool(task.get("is_reference"))
    reference_image = None if is_reference else task.get("reference_image")
    if client.use_dummy or not client.api_key:
        return int(dummy_image_critique(card=card, card_type=card_type).get("rating", 0))
    prompt = render_prompt(
        "image_critique.jinja",
        prompt_path=prompt_path,
        card=card,
        card_type=card_type,
        reference_image_provided=bool(reference_image),
    )
    payload = _build_image_critique_payload(
        prompt=prompt,
        model=model,
        image_path=out_path,
        reference_image_path=reference_image,
        reasoning_effort=reasoning_effort,
        store=store,
    )
    attempts = 0
    response: dict[str, Any] | None = None
    while attempts <= retry_limit:
        try:
            if timeout_s is not None and timeout_s > 0:
                response = await asyncio.wait_for(client.responses_async(payload), timeout=timeout_s)
            else:
                response = await client.responses_async(payload)
            break
        except asyncio.TimeoutError:
            attempts += 1
            if attempts > retry_limit:
                console.print(f"[yellow]Image critique timed out for {card.get('id', 'card')}.[/yellow]")
                return 0
            console.print(
                f"[yellow]Image critique timed out for {card.get('id', 'card')}; retrying "
                f"({attempts}/{retry_limit}).[/yellow]"
            )
            await asyncio.sleep(_retry_delay_s(attempts))
        except Exception as exc:  # noqa: BLE001 - keep image runs resilient
            attempts += 1
            if attempts > retry_limit:
                console.print(
                    f"[yellow]Image critique failed for {card.get('id', 'card')}. Reason: {exc!r}[/yellow]"
                )
                return 0
            console.print(
                f"[yellow]Image critique failed for {card.get('id', 'card')}; retrying "
                f"({attempts}/{retry_limit}). Reason: {exc!r}[/yellow]"
            )
            await asyncio.sleep(_retry_delay_s(attempts))
    if response is None:
        return 0
    parsed = _parse_image_critique_response(response)
    if parsed is None:
        return 0
    return int(parsed.get("rating", 0))


def _build_image_critique_payload(
    *,
    prompt: str,
    model: str | None,
    image_path: Path,
    reference_image_path: Path | None,
    reasoning_effort: str | None,
    store: bool,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": _encode_image_data_url(image_path)},
    ]
    if reference_image_path:
        content.append({"type": "input_image", "image_url": _encode_image_data_url(reference_image_path)})
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
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
    reference_quality: str | None,
    background: str | None,
    resume: bool,
    regen_concurrency: int,
    image_timeout_s: float | None,
    critique_timeout_s: float | None,
    image_retry_limit: int,
    critique_retry_limit: int,
) -> tuple[list[Path] | None, list[Path] | None]:
    policy_ref_paths = _resolve_reference_paths(reference_policy)
    dev_ref_paths = _resolve_reference_paths(reference_dev)

    reference_tasks: list[dict[str, Any]] = []
    policy_reference_out: Path | None = None
    dev_reference_out: Path | None = None

    reference_candidate_count = _normalize_candidate_count(
        max(1, candidate_count * max(1, reference_multiplier))
    )

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
                is_reference=True,
                client=client,
                model=model,
                responses_model=responses_model,
                api=api,
                size=size,
                quality=reference_quality,
                background=background,
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
                is_reference=True,
                client=client,
                model=model,
                responses_model=responses_model,
                api=api,
                size=size,
                quality=reference_quality,
                background=background,
                resume=resume,
                final_suffix="_reference",
            )
        )

    if reference_tasks:
        _run_generation_tasks(
            reference_tasks,
            regen_concurrency,
            desc="Reference image candidates",
            timeout_s=image_timeout_s,
            retry_limit=image_retry_limit,
        )
        _finalize_best_candidates(
            tasks=reference_tasks,
            client=client,
            prompt_path=prompt_path,
            model=critique_model,
            reasoning_effort=critique_reasoning_effort,
            store=critique_store,
            concurrency=critique_concurrency,
            desc="Reference image critiques",
            timeout_s=critique_timeout_s,
            retry_limit=critique_retry_limit,
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


def _run_generation_tasks(
    tasks: list[dict[str, Any]],
    concurrency: int,
    *,
    desc: str,
    timeout_s: float | None = None,
    retry_limit: int = 0,
) -> None:
    if not tasks:
        return
    run_async(
        _run_generation_tasks_async(
            _build_generation_batches(tasks),
            concurrency,
            desc=desc,
            timeout_s=timeout_s,
            retry_limit=retry_limit,
        )
    )


async def _run_generation_tasks_async(
    tasks: list[dict[str, Any]],
    concurrency: int,
    *,
    desc: str,
    timeout_s: float | None = None,
    retry_limit: int = 0,
) -> None:
    if not tasks:
        return
    if tasks and "out_path" in tasks[0]:
        tasks = _build_generation_batches(tasks)
    resolved_concurrency = _resolve_concurrency(len(tasks), concurrency)
    console.print(
        f"[cyan]{desc}: running {len(tasks)} tasks with concurrency {resolved_concurrency}[/cyan]"
    )
    semaphore = asyncio.Semaphore(resolved_concurrency)

    async def _run_task(task: dict[str, Any]) -> None:
        async with semaphore:
            attempts = 0
            while attempts <= retry_limit:
                try:
                    thread_task = asyncio.to_thread(_generate_card_images, **task)
                    if timeout_s is not None and timeout_s > 0:
                        await asyncio.wait_for(thread_task, timeout=timeout_s)
                    else:
                        await thread_task
                    return
                except asyncio.TimeoutError:
                    attempts += 1
                    if attempts > retry_limit:
                        console.print(
                            "[yellow]Image task timed out; skipping remaining work for that task.[/yellow]"
                        )
                        return
                    console.print(
                        "[yellow]Image task timed out; retrying "
                        f"({attempts}/{retry_limit}).[/yellow]"
                    )
                    await asyncio.sleep(_retry_delay_s(attempts))
                except Exception as exc:  # noqa: BLE001 - best-effort image runs
                    attempts += 1
                    if attempts > retry_limit:
                        console.print(f"[yellow]Image task failed. Reason: {exc!r}[/yellow]")
                        return
                    console.print(
                        "[yellow]Image task failed; retrying "
                        f"({attempts}/{retry_limit}). Reason: {exc!r}[/yellow]"
                    )
                    await asyncio.sleep(_retry_delay_s(attempts))

    coros = [_run_task(task) for task in tasks]
    for coro in tqdm(asyncio.as_completed(coros), total=len(coros), desc=desc):
        await coro


def _build_generation_batches(tasks: list[dict[str, Any]], max_batch_size: int = 10) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for task in tasks:
        if task.get("resume") and task["out_path"].exists() and task["out_path"].stat().st_size > 0:
            continue
        reference_images = tuple(str(path) for path in (task.get("reference_images") or []))
        key = (
            task["card"]["id"],
            task.get("is_reference", False),
            task.get("api"),
            task.get("model"),
            task.get("responses_model"),
            task.get("size"),
            task.get("quality"),
            task.get("background"),
            reference_images,
        )
        grouped.setdefault(key, []).append(task)

    batches: list[dict[str, Any]] = []
    for grouped_tasks in grouped.values():
        grouped_tasks.sort(key=lambda item: item["out_path"].name)
        api = grouped_tasks[0].get("api")
        batch_size = max_batch_size if api == "images" else 1
        for idx in range(0, len(grouped_tasks), batch_size):
            chunk = grouped_tasks[idx : idx + batch_size]
            first = chunk[0]
            batches.append(
                {
                    "card": first["card"],
                    "out_paths": [item["out_path"] for item in chunk],
                    "reference_images": first.get("reference_images"),
                    "client": first["client"],
                    "model": first.get("model"),
                    "responses_model": first.get("responses_model"),
                    "api": api,
                    "size": first.get("size"),
                    "quality": first.get("quality"),
                    "background": first.get("background"),
                    "resume": first.get("resume", False),
                }
            )
    return batches


def _extract_image_b64_list(client: OpenAIClient, response: dict[str, Any]) -> list[str]:
    if "data" in response:
        data = response.get("data") or []
        if isinstance(data, list):
            return [item.get("b64_json") for item in data if isinstance(item, dict) and item.get("b64_json")]
    extracted = client.extract_image_b64(response)
    return [extracted] if extracted else []


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


def _normalize_candidate_count(value: Any, *, batch_size: int = 10) -> int:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        return 1
    count = max(1, count)
    if count <= batch_size:
        return count
    return int(math.ceil(count / batch_size) * batch_size)


def _retry_delay_s(attempt: int) -> float:
    return min(10.0, 1.5 * attempt)
