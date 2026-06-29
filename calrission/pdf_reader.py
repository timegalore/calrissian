"""PDF text extraction and colour sampling."""

from __future__ import annotations

import colorsys
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz

# Join words broken across lines: "organiza-\ntion" -> "organization".
LINE_BREAK_HYPHEN_PATTERN = re.compile(r"([A-Za-z]+)-\r?\n([a-z][A-Za-z']*)")


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
        text = dehyphenate_line_breaks(text)
        palette = _build_palette(colour_samples, palette_size)
        return PdfContent(text=text, palette=palette)
    finally:
        document.close()


def dehyphenate_line_breaks(text: str) -> str:
    """Rejoin words split by end-of-line hyphens in PDF text extraction."""
    previous = None
    while previous != text:
        previous = text
        text = LINE_BREAK_HYPHEN_PATTERN.sub(r"\1\2", text)
    return text


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
        return _default_palette()[:palette_size]

    quantised = Counter(
        _quantize(sample)
        for sample in samples
        if not _is_neutral(sample)
    )
    ranked: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for colour, _ in quantised.most_common(palette_size * 3):
        vibrant = _boost_vibrancy(colour)
        if vibrant in seen:
            continue
        seen.add(vibrant)
        ranked.append(vibrant)
        if len(ranked) >= palette_size:
            break

    if len(ranked) < palette_size:
        for colour in _default_palette():
            if colour in seen:
                continue
            ranked.append(colour)
            seen.add(colour)
            if len(ranked) >= palette_size:
                break

    return ranked[:palette_size]


def _quantize(colour: tuple[int, int, int], bucket: int = 32) -> tuple[int, int, int]:
    return tuple(min(255, (channel // bucket) * bucket + bucket // 2) for channel in colour)


def _colour_hsv(colour: tuple[int, int, int]) -> tuple[float, float, float]:
    red, green, blue = (channel / 255.0 for channel in colour)
    return colorsys.rgb_to_hsv(red, green, blue)


def _is_neutral(colour: tuple[int, int, int]) -> bool:
    _, saturation, value = _colour_hsv(colour)
    return value < 0.18 or (saturation < 0.12 and value > 0.85)


def _boost_vibrancy(
    colour: tuple[int, int, int],
    *,
    saturation_factor: float = 1.55,
    min_saturation: float = 0.58,
    min_value: float = 0.48,
) -> tuple[int, int, int]:
    hue, saturation, value = _colour_hsv(colour)
    saturation = min(1.0, max(min_saturation, saturation * saturation_factor))
    value = min(0.95, max(min_value, value))
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return (
        int(round(red * 255)),
        int(round(green * 255)),
        int(round(blue * 255)),
    )


def _default_palette() -> list[tuple[int, int, int]]:
    return [
        (255, 59, 48),
        (255, 149, 0),
        (255, 204, 0),
        (52, 199, 89),
        (48, 176, 199),
        (0, 122, 255),
        (88, 86, 214),
        (175, 82, 222),
        (255, 45, 85),
        (255, 102, 0),
        (0, 199, 190),
        (255, 59, 105),
    ]
