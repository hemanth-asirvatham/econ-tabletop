from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm


CARD_SIZE = (1536, 1024)


def render_cards(policies: list[dict[str, Any]], developments: list[dict[str, Any]], out_dir: Path) -> None:
    policy_dir = out_dir / "render" / "policy"
    dev_dir = out_dir / "render" / "development"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    font = _load_font(48)
    for card in tqdm(policies, desc="Rendering policy cards"):
        _render_card(card, policy_dir / f"{card['id']}.png", font, "POLICY")
    for card in tqdm(developments, desc="Rendering development cards"):
        primary_path = dev_dir / f"{card['id']}.png"
        _render_card(card, primary_path, font, "DEVELOPMENT")
        if card.get("card_type") == "power":
            _render_card(card, dev_dir / f"power_{card['id']}.png", font, "DEVELOPMENT")


def _render_card(card: dict[str, Any], path: Path, font: ImageFont.ImageFont, label: str) -> None:
    image = Image.new("RGBA", CARD_SIZE, (15, 18, 28, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(20, 20), (CARD_SIZE[0] - 20, CARD_SIZE[1] - 20)], outline=(255, 255, 255, 80), width=4)
    draw.text((60, 60), label, font=font, fill=(255, 255, 255, 220))
    if label == "DEVELOPMENT":
        _draw_valence_icons(draw, card)
    draw.text((60, 140), card["title"], font=font, fill=(255, 255, 255, 220))
    draw.text((60, 220), card["short_description"], font=_load_font(32), fill=(200, 200, 200, 220))
    image.save(path)


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _draw_valence_icons(draw: ImageDraw.ImageDraw, card: dict[str, Any]) -> None:
    arrows_up = int(card.get("arrows_up", 0) or 0)
    arrows_down = int(card.get("arrows_down", 0) or 0)
    icon_size = 20
    spacing = 6
    x_right = CARD_SIZE[0] - 70
    y_top = 50
    if arrows_up == 0 and arrows_down == 0:
        draw.line([(x_right - 30, y_top + 8), (x_right, y_top + 8)], fill=(160, 160, 160, 220), width=4)
        return
    y_cursor = y_top
    for _ in range(arrows_up):
        _draw_triangle(draw, x_right, y_cursor, icon_size, direction="up", fill=(74, 222, 128, 220))
        y_cursor += icon_size + spacing
    for _ in range(arrows_down):
        _draw_triangle(draw, x_right, y_cursor, icon_size, direction="down", fill=(248, 113, 113, 220))
        y_cursor += icon_size + spacing


def _draw_triangle(
    draw: ImageDraw.ImageDraw,
    x_right: int,
    y_top: int,
    size: int,
    *,
    direction: str,
    fill: tuple[int, int, int, int],
) -> None:
    x_left = x_right - size
    x_mid = x_left + size / 2
    if direction == "up":
        points = [(x_mid, y_top), (x_left, y_top + size), (x_right, y_top + size)]
    else:
        points = [(x_left, y_top), (x_right, y_top), (x_mid, y_top + size)]
    draw.polygon(points, fill=fill)
