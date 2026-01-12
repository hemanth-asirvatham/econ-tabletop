from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


CARD_WIDTH_IN = 3.75
CARD_HEIGHT_IN = 2.5


def export_print(deck_dir: Path) -> None:
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
