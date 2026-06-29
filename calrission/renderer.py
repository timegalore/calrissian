"""Word cloud image rendering."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from calrission.palette import assign_colours

LOGICAL_WIDTH = 1200
LOGICAL_HEIGHT = 800
RENDER_SCALE = 2.5
CANVAS_WIDTH = int(LOGICAL_WIDTH * RENDER_SCALE)
CANVAS_HEIGHT = int(LOGICAL_HEIGHT * RENDER_SCALE)
MARGIN = int(40 * RENDER_SCALE)
MIN_OUTPUT_WIDTH = 1000
OUTPUT_DPI = 300
JPEG_QUALITY = 95


@dataclass(frozen=True)
class RenderOptions:
    shape: str
    font_name: str
    max_font_size: float
    min_font_size: float
    max_angle: float


@dataclass
class PlacedWord:
    word: str
    count: int
    font_size: float
    angle: float
    colour: tuple[int, int, int]
    bbox: tuple[int, int, int, int]


def render_wordcloud(
    words: list[tuple[str, int]],
    palette: list[tuple[int, int, int]],
    options: RenderOptions,
    seed: int | None = None,
) -> Image.Image:
    if seed is not None:
        random.seed(seed)

    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")
    mask = _shape_mask(options.shape)
    centroid = _mask_centroid(mask)
    colours = assign_colours(len(words), palette)
    counts = [count for _, count in words]
    min_count = min(counts)
    max_count = max(counts)

    font_path = _resolve_font(options.font_name)
    placed: list[PlacedWord] = []
    occupied = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)

    for rank, ((word, count), colour) in enumerate(zip(words, colours)):
        font_size = _font_size_for_count(
            count,
            min_count,
            max_count,
            options.min_font_size,
            options.max_font_size,
        )
        font = _load_font(font_path, font_size)
        angle = _random_angle(options.max_angle)
        word_image = _render_word_image(word, font, angle, colour)

        position = _find_position(
            word_image=word_image,
            mask=mask,
            occupied=occupied,
            centroid=centroid,
            rank=rank,
            total=len(words),
        )
        if position is None:
            continue

        word_bbox = _paste_word(image, word_image, position)
        _mark_occupied(occupied, word_bbox)
        placed.append(
            PlacedWord(
                word=word,
                count=count,
                font_size=font_size,
                angle=angle,
                colour=colour,
                bbox=word_bbox,
            )
        )

    if not placed:
        raise ValueError("Unable to place any words inside the requested shape")

    return image


def save_jpeg(image: Image.Image, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if image.width < MIN_OUTPUT_WIDTH:
        scale = MIN_OUTPUT_WIDTH / image.width
        image = image.resize(
            (MIN_OUTPUT_WIDTH, max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )

    image.save(
        output_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        dpi=(OUTPUT_DPI, OUTPUT_DPI),
        subsampling=0,
    )
    return output_path


def _font_size_for_count(
    count: int,
    min_count: int,
    max_count: int,
    min_size: float,
    max_size: float,
) -> float:
    if max_count == min_count:
        return max_size
    ratio = (count - min_count) / (max_count - min_count)
    return min_size + ratio * (max_size - min_size)


def _random_angle(max_angle: float) -> float:
    if max_angle <= 0:
        return 0.0
    magnitude = random.uniform(0, max_angle)
    return magnitude if random.choice((True, False)) else -magnitude


def _resolve_font(font_name: str) -> str | None:
    candidates = [
        f"{font_name}.ttf",
        f"{font_name.lower()}.ttf",
        f"{font_name}.ttc",
        f"{font_name.lower()}.ttc",
    ]
    search_dirs = [
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
    ]

    for directory in search_dirs:
        if not directory.exists():
            continue
        for candidate in candidates:
            path = directory / candidate
            if path.exists():
                return str(path)
    return None


def _load_font(font_path: str | None, size: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    pixel_size = max(round(size * RENDER_SCALE), 1)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=pixel_size)
        except OSError:
            pass
    return ImageFont.load_default()


def _shape_mask(shape: str) -> np.ndarray:
    mask = Image.new("L", (CANVAS_WIDTH, CANVAS_HEIGHT), 0)
    draw = ImageDraw.Draw(mask)

    if shape == "rectangle":
        draw.rectangle(
            (MARGIN, MARGIN, CANVAS_WIDTH - MARGIN, CANVAS_HEIGHT - MARGIN),
            fill=255,
        )
    else:
        _draw_cloud_shape(draw)

    return np.array(mask) >= 128


def _draw_cloud_shape(draw: ImageDraw.ImageDraw) -> None:
    circles = [
        (CANVAS_WIDTH * 0.50, CANVAS_HEIGHT * 0.52, CANVAS_WIDTH * 0.34),
        (CANVAS_WIDTH * 0.30, CANVAS_HEIGHT * 0.55, CANVAS_WIDTH * 0.22),
        (CANVAS_WIDTH * 0.70, CANVAS_HEIGHT * 0.54, CANVAS_WIDTH * 0.24),
        (CANVAS_WIDTH * 0.42, CANVAS_HEIGHT * 0.38, CANVAS_WIDTH * 0.18),
        (CANVAS_WIDTH * 0.58, CANVAS_HEIGHT * 0.40, CANVAS_WIDTH * 0.20),
        (CANVAS_WIDTH * 0.50, CANVAS_HEIGHT * 0.66, CANVAS_WIDTH * 0.20),
        (CANVAS_WIDTH * 0.22, CANVAS_HEIGHT * 0.48, CANVAS_WIDTH * 0.14),
        (CANVAS_WIDTH * 0.78, CANVAS_HEIGHT * 0.50, CANVAS_WIDTH * 0.15),
    ]
    for x, y, radius in circles:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)


def _mask_centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2
    return float(xs.mean()), float(ys.mean())


def _render_word_image(
    word: str,
    font: ImageFont.ImageFont,
    angle: float,
    colour: tuple[int, int, int],
) -> Image.Image:
    scratch = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scratch)
    bbox = draw.textbbox((0, 0), word, font=font)
    padding = max(round(4 * RENDER_SCALE), 1)
    width = bbox[2] - bbox[0] + padding * 2
    height = bbox[3] - bbox[1] + padding * 2
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(image).text(
        (padding - bbox[0], padding - bbox[1]),
        word,
        font=font,
        fill=colour + (255,),
    )
    if angle:
        image = image.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    return image


def _find_position(
    word_image: Image.Image,
    mask: np.ndarray,
    occupied: np.ndarray,
    centroid: tuple[float, float],
    rank: int,
    total: int,
) -> tuple[int, int] | None:
    width, height = word_image.size
    cx, cy = centroid
    rank_ratio = rank / max(total - 1, 1)
    spread = 0.15 + rank_ratio * 0.85

    for _ in range(350):
        angle = random.uniform(0, 2 * math.pi)
        radius = random.random() ** 0.7 * spread
        max_radius = min(CANVAS_WIDTH, CANVAS_HEIGHT) * 0.42
        x = int(cx + math.cos(angle) * radius * max_radius - width / 2)
        y = int(cy + math.sin(angle) * radius * max_radius - height / 2)

        candidate = (x, y, x + width, y + height)
        if not _bbox_inside_mask(candidate, mask):
            continue
        if _bbox_overlaps(candidate, occupied):
            continue
        return x, y

    return None


def _bbox_inside_mask(
    bbox: tuple[int, int, int, int],
    mask: np.ndarray,
) -> bool:
    x1, y1, x2, y2 = bbox
    x1 = max(x1, 0)
    y1 = max(y1, 0)
    x2 = min(x2, CANVAS_WIDTH)
    y2 = min(y2, CANVAS_HEIGHT)

    if x2 <= x1 or y2 <= y1:
        return False

    region = mask[y1:y2, x1:x2]
    return region.size > 0 and region.mean() > 0.92


def _bbox_overlaps(
    bbox: tuple[int, int, int, int],
    occupied: np.ndarray,
) -> bool:
    x1, y1, x2, y2 = bbox
    x1 = max(x1, 0)
    y1 = max(y1, 0)
    x2 = min(x2, CANVAS_WIDTH)
    y2 = min(y2, CANVAS_HEIGHT)
    region = occupied[y1:y2, x1:x2]
    return region.size > 0 and region.any()


def _paste_word(
    image: Image.Image,
    word_image: Image.Image,
    position: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y = position
    image.paste(word_image, (x, y), word_image)
    alpha = word_image.split()[3]
    local_bbox = alpha.getbbox()
    if local_bbox is None:
        return (x, y, x + 1, y + 1)
    x1, y1, x2, y2 = local_bbox
    return (x + x1, y + y1, x + x2, y + y2)


def _mark_occupied(
    occupied: np.ndarray,
    bbox: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = bbox
    x1 = max(x1, 0)
    y1 = max(y1, 0)
    x2 = min(x2, CANVAS_WIDTH)
    y2 = min(y2, CANVAS_HEIGHT)
    occupied[y1:y2, x1:x2] = True
