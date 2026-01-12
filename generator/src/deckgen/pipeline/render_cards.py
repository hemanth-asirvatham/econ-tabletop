from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm


CARD_SIZE = (1536, 1024)


def render_cards(policies: list[dict[str, Any]], developments: list[dict[str, Any]], out_dir: Path) -> None:
    policy_dir = out_dir / "images" / "policy"
    dev_dir = out_dir / "images" / "development"
    policy_dir.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    font = _load_font(48)
    for card in tqdm(policies, desc="Rendering policy cards"):
        _render_card(card, policy_dir / f"{card['id']}.png", font, "POLICY")
    for card in tqdm(developments, desc="Rendering development cards"):
        _render_card(card, dev_dir / f"{card['id']}.png", font, "DEVELOPMENT")


def _render_card(card: dict[str, Any], path: Path, font: ImageFont.ImageFont, label: str) -> None:
    image = Image.new("RGBA", CARD_SIZE, (15, 18, 28, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(20, 20), (CARD_SIZE[0] - 20, CARD_SIZE[1] - 20)], outline=(255, 255, 255, 80), width=4)
    draw.text((60, 60), label, font=font, fill=(255, 255, 255, 220))
    draw.text((60, 140), card["title"], font=font, fill=(255, 255, 255, 220))
    draw.text((60, 220), card["short_description"], font=_load_font(32), fill=(200, 200, 200, 220))
    image.save(path)


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()
