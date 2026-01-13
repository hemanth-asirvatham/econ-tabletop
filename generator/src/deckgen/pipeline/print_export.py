from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Tuple, Type


CARD_WIDTH_IN = 3.75
CARD_HEIGHT_IN = 2.5


def _load_reportlab() -> Tuple[Tuple[float, float], Type[Any]]:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "reportlab is required to export printable PDFs. "
            "Install it with `pip install reportlab` and re-run the print step."
        ) from exc
    return letter, canvas


def export_print(deck_dir: Path) -> None:
    letter, canvas = _load_reportlab()
    print_dir = deck_dir / "print"
    print_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = print_dir / "cards_letter.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    margin = 36
    x = margin
    y = height - margin - (CARD_HEIGHT_IN * 72)
    for _ in range(6):
        c.rect(x, y, CARD_WIDTH_IN * 72, CARD_HEIGHT_IN * 72)
        x += CARD_WIDTH_IN * 72 + 12
        if x + CARD_WIDTH_IN * 72 > width - margin:
            x = margin
            y -= CARD_HEIGHT_IN * 72 + 12
    c.showPage()
    c.save()


def export_text_mockups(
    policies: list[dict[str, Any]],
    developments: list[dict[str, Any]],
    deck_dir: Path,
) -> None:
    letter, canvas = _load_reportlab()
    from reportlab.lib.utils import simpleSplit

    mockup_dir = deck_dir / "mockups"
    mockup_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = mockup_dir / "cards_text_mockups.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    margin = 36
    slots = _page_slots(width, height, margin)

    def _wrap(text: str, max_width: float, font: str, size: int) -> list[str]:
        return simpleSplit(text, font, size, max_width)

    cards: Iterable[tuple[dict[str, Any], str]] = (
        [(card, "POLICY") for card in policies] + [(card, "DEVELOPMENT") for card in developments]
    )
    slot_index = 0
    for card, label in cards:
        if slot_index >= len(slots):
            c.showPage()
            slot_index = 0
        x, y = slots[slot_index]
        _draw_text_card(c, card, label, x, y, _wrap)
        slot_index += 1
    c.showPage()
    c.save()


def _page_slots(width: float, height: float, margin: float) -> list[tuple[float, float]]:
    slots = []
    x = margin
    y = height - margin - (CARD_HEIGHT_IN * 72)
    for _ in range(6):
        slots.append((x, y))
        x += CARD_WIDTH_IN * 72 + 12
        if x + CARD_WIDTH_IN * 72 > width - margin:
            x = margin
            y -= CARD_HEIGHT_IN * 72 + 12
    return slots


def _draw_text_card(
    canvas: Any,
    card: dict[str, Any],
    label: str,
    x: float,
    y: float,
    wrap_fn: Any,
) -> None:
    card_width = CARD_WIDTH_IN * 72
    card_height = CARD_HEIGHT_IN * 72
    canvas.setStrokeColorRGB(0.85, 0.85, 0.9)
    canvas.rect(x, y, card_width, card_height, stroke=1, fill=0)

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(x + 8, y + card_height - 16, label)

    title = card.get("title", "")
    desc = card.get("short_description", "")
    canvas.setFont("Helvetica-Bold", 9)
    y_offset = 0
    for line in wrap_fn(title, card_width - 16, "Helvetica-Bold", 9):
        canvas.drawString(x + 8, y + card_height - 30 - y_offset, line)
        y_offset += 10

    canvas.setFont("Helvetica", 8)
    desc_lines = wrap_fn(desc, card_width - 16, "Helvetica", 8)
    desc_y = y + card_height - 54 - y_offset
    for line in desc_lines[:6]:
        canvas.drawString(x + 8, desc_y, line)
        desc_y -= 10

    if label == "DEVELOPMENT":
        _draw_valence_icons(canvas, card, x + card_width - 32, y + card_height - 20)


def _draw_valence_icons(canvas: Any, card: dict[str, Any], x_right: float, y_top: float) -> None:
    arrows_up = int(card.get("arrows_up", 0) or 0)
    arrows_down = int(card.get("arrows_down", 0) or 0)
    size = 6
    spacing = 2
    if arrows_up == 0 and arrows_down == 0:
        canvas.setStrokeColorRGB(0.6, 0.6, 0.6)
        canvas.line(x_right - 16, y_top, x_right, y_top)
        return
    y_cursor = y_top
    canvas.setFillColorRGB(0.29, 0.87, 0.5)
    for _ in range(arrows_up):
        _draw_triangle(canvas, x_right, y_cursor, size, direction="up")
        y_cursor -= size + spacing
    canvas.setFillColorRGB(0.97, 0.44, 0.44)
    for _ in range(arrows_down):
        _draw_triangle(canvas, x_right, y_cursor, size, direction="down")
        y_cursor -= size + spacing


def _draw_triangle(canvas: Any, x_right: float, y_top: float, size: float, *, direction: str) -> None:
    x_left = x_right - size
    x_mid = x_left + size / 2
    if direction == "up":
        points = [(x_mid, y_top), (x_left, y_top - size), (x_right, y_top - size)]
    else:
        points = [(x_left, y_top), (x_right, y_top), (x_mid, y_top - size)]
    path = canvas.beginPath()
    path.moveTo(points[0][0], points[0][1])
    for point in points[1:]:
        path.lineTo(point[0], point[1])
    path.close()
    canvas.drawPath(path, stroke=0, fill=1)
