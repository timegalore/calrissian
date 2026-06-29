"""PDF text extraction and colour sampling."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class PdfContent:
    text: str
    palette: list[tuple[int, int, int]]


def extract_pdf_content(pdf_path: Path, palette_size: int = 12) -> PdfContent:
    document = fitz.open(pdf_path)
    try:
        text_parts: list[str] = []
        colour_samples: list[tuple[int, int, int]] = []

        for page in document:
            text_parts.append(page.get_text("text"))
            colour_samples.extend(_sample_page_colours(page))

        text = "\n".join(text_parts)
        palette = _build_palette(colour_samples, palette_size)
        return PdfContent(text=text, palette=palette)
    finally:
        document.close()


def _sample_page_colours(page: fitz.Page, step: int = 8) -> list[tuple[int, int, int]]:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False)
    samples: list[tuple[int, int, int]] = []

    for y in range(0, pixmap.height, step):
        for x in range(0, pixmap.width, step):
            red, green, blue = pixmap.pixel(x, y)[:3]
            if _is_background(red, green, blue):
                continue
            samples.append((red, green, blue))

    return samples


def _is_background(red: int, green: int, blue: int) -> bool:
    return red > 240 and green > 240 and blue > 240


def _build_palette(
    samples: list[tuple[int, int, int]],
    palette_size: int,
) -> list[tuple[int, int, int]]:
    if not samples:
        return [
            (30, 90, 160),
            (180, 40, 40),
            (40, 120, 60),
            (120, 80, 160),
            (200, 120, 20),
            (20, 140, 140),
        ]

    quantised = Counter(_quantize(sample) for sample in samples)
    ranked = [colour for colour, _ in quantised.most_common(max(palette_size, 1))]

    if len(ranked) < palette_size:
        ranked.extend(_default_palette()[len(ranked) : palette_size])

    return ranked[:palette_size]


def _quantize(colour: tuple[int, int, int], bucket: int = 32) -> tuple[int, int, int]:
    return tuple(min(255, (channel // bucket) * bucket + bucket // 2) for channel in colour)


def _default_palette() -> list[tuple[int, int, int]]:
    return [
        (30, 90, 160),
        (180, 40, 40),
        (40, 120, 60),
        (120, 80, 160),
        (200, 120, 20),
        (20, 140, 140),
        (90, 90, 90),
        (160, 60, 120),
    ]
