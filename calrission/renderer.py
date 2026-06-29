"""Word cloud image rendering."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
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
SHAPE_BORDER_WIDTH = max(round(2 * RENDER_SCALE), 1)
PLACEMENT_ANGLE_BINS = 36
PLACEMENT_CANDIDATES = 450
PLACEMENT_SOFT_DISTANCE_WEIGHT = 0.3
PLACEMENT_ANGLE_BIN_WEIGHT = 1.0
PLACEMENT_GAP_WEIGHT = 1.4
CLOUD_OUTLINE_PATH = Path(__file__).resolve().parent / "assets" / "cloud_outline.png"
CLOUD_OUTLINE_STROKE_THRESHOLD = 128
CLOUD_OUTLINE_ANTIALIAS_MAX = 220


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
    placement_radii = _mask_placement_radii(mask, centroid)
    colours = assign_colours(len(words), palette)
    counts = [count for _, count in words]
    min_count = min(counts)
    max_count = max(counts)

    font_path = _resolve_font(options.font_name)
    placed: list[PlacedWord] = []
    placed_centers: list[tuple[float, float]] = []
    angle_bin_counts = [0] * PLACEMENT_ANGLE_BINS
    occupied = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)

    for (word, count), colour in zip(words, colours):
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
            placement_radii=placement_radii,
            font_size=font_size,
            min_font_size=options.min_font_size,
            max_font_size=options.max_font_size,
            placed_centers=placed_centers,
            angle_bin_counts=angle_bin_counts,
        )
        if position is None:
            continue

        word_bbox = _paste_word(image, word_image, position)
        _mark_occupied(occupied, word_bbox)
        word_center = (
            (word_bbox[0] + word_bbox[2]) / 2,
            (word_bbox[1] + word_bbox[3]) / 2,
        )
        placed_centers.append(word_center)
        angle_bin_counts[_angle_bin_index(word_center, centroid)] += 1
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

    _draw_shape_border(image, options.shape)
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


def _font_size_ratio(
    font_size: float,
    min_font_size: float,
    max_font_size: float,
) -> float:
    if max_font_size <= min_font_size:
        return 1.0
    return (font_size - min_font_size) / (max_font_size - min_font_size)


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
    if shape == "cloud":
        return _cloud_interior_mask(_cloud_outline_array())

    mask = Image.new("L", (CANVAS_WIDTH, CANVAS_HEIGHT), 0)
    draw = ImageDraw.Draw(mask)
    _draw_shape(draw, shape)
    return np.array(mask) >= 128


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str) -> None:
    draw.rectangle(
        (MARGIN, MARGIN, CANVAS_WIDTH - MARGIN, CANVAS_HEIGHT - MARGIN),
        fill=255,
    )


def _draw_shape_border(image: Image.Image, shape: str) -> None:
    if shape == "cloud":
        _draw_cloud_outline_image(image, _cloud_outline_array())
        return

    border = _outline_mask(_shape_mask(shape), SHAPE_BORDER_WIDTH)
    pixels = np.array(image)
    pixels[border] = (0, 0, 0)
    image.paste(Image.fromarray(pixels))


@lru_cache(maxsize=1)
def _cloud_outline_array() -> np.ndarray:
    if not CLOUD_OUTLINE_PATH.exists():
        raise FileNotFoundError(f"Cloud outline image not found: {CLOUD_OUTLINE_PATH}")

    outline = Image.open(CLOUD_OUTLINE_PATH).convert("RGBA")
    background = Image.new("RGBA", outline.size, (255, 255, 255, 255))
    source = np.array(Image.alpha_composite(background, outline).convert("L"))
    binary = np.where(source < CLOUD_OUTLINE_STROKE_THRESHOLD, 0, 255).astype(np.uint8)
    binary_image = Image.fromarray(binary, mode="L")

    scale = min(
        (CANVAS_WIDTH - 2 * MARGIN) / binary_image.width,
        (CANVAS_HEIGHT - 2 * MARGIN) / binary_image.height,
    )
    resized = binary_image.resize(
        (max(1, int(binary_image.width * scale)), max(1, int(binary_image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("L", (CANVAS_WIDTH, CANVAS_HEIGHT), 255)
    offset_x = (CANVAS_WIDTH - resized.width) // 2
    offset_y = (CANVAS_HEIGHT - resized.height) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return np.array(canvas)


def _cloud_stroke_mask(outline: np.ndarray) -> np.ndarray:
    return outline < CLOUD_OUTLINE_STROKE_THRESHOLD


def _cloud_interior_mask(outline: np.ndarray) -> np.ndarray:
    barrier = _dilate_bool(_cloud_stroke_mask(outline), 2)
    height, width = outline.shape
    exterior = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        for y in (0, height - 1):
            _enqueue_exterior(exterior, barrier, queue, x, y)
    for y in range(height):
        for x in (0, width - 1):
            _enqueue_exterior(exterior, barrier, queue, x, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            _enqueue_exterior(exterior, barrier, queue, nx, ny)

    return ~barrier & ~exterior


def _enqueue_exterior(
    exterior: np.ndarray,
    barrier: np.ndarray,
    queue: deque[tuple[int, int]],
    x: int,
    y: int,
) -> None:
    height, width = exterior.shape
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    if barrier[y, x] or exterior[y, x]:
        return
    exterior[y, x] = True
    queue.append((x, y))


def _draw_cloud_outline_image(image: Image.Image, outline: np.ndarray) -> None:
    alpha = _cloud_outline_alpha(outline)
    if not alpha.any():
        return

    pixels = np.array(image, dtype=np.float32)
    pixels *= 1.0 - alpha[:, :, np.newaxis]
    image.paste(Image.fromarray(np.rint(pixels).astype(np.uint8)))


def _cloud_outline_alpha(outline: np.ndarray) -> np.ndarray:
    tone = outline.astype(np.float32)
    alpha = np.zeros_like(tone)
    stroke_region = tone < CLOUD_OUTLINE_ANTIALIAS_MAX
    alpha[stroke_region] = (CLOUD_OUTLINE_ANTIALIAS_MAX - tone[stroke_region]) / CLOUD_OUTLINE_ANTIALIAS_MAX
    return np.clip(alpha, 0.0, 1.0)


def _dilate_bool(mask: np.ndarray, radius: int) -> np.ndarray:
    expanded = mask.copy()
    for _ in range(radius):
        grown = expanded.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                grown |= _shift_mask(expanded, dy, dx)
        expanded = grown
    return expanded


def _outline_mask(mask: np.ndarray, thickness: int) -> np.ndarray:
    eroded = mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            eroded &= _shift_mask(mask, dy, dx)
    outline = mask & ~eroded

    if thickness <= 1:
        return outline

    expanded = outline.copy()
    for _ in range(thickness - 1):
        grown = expanded.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                grown |= _shift_mask(expanded, dy, dx)
        expanded = grown
    return expanded


def _shift_mask(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask)
    y_src = slice(max(0, -dy), min(height, height - dy))
    x_src = slice(max(0, -dx), min(width, width - dx))
    y_dst = slice(max(0, dy), min(height, height + dy))
    x_dst = slice(max(0, dx), min(width, width + dx))
    shifted[y_dst, x_dst] = mask[y_src, x_src]
    return shifted


def _mask_centroid(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2
    return float(xs.mean()), float(ys.mean())


def _mask_placement_radii(
    mask: np.ndarray,
    centroid: tuple[float, float],
) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return CANVAS_WIDTH * 0.45, CANVAS_HEIGHT * 0.45

    cx, cy = centroid
    max_rx = max(cx - xs.min(), xs.max() - cx) * 0.96
    max_ry = max(cy - ys.min(), ys.max() - cy) * 0.96
    return max_rx, max_ry


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
    placement_radii: tuple[float, float],
    font_size: float,
    min_font_size: float,
    max_font_size: float,
    placed_centers: list[tuple[float, float]],
    angle_bin_counts: list[int],
) -> tuple[int, int] | None:
    width, height = word_image.size
    cx, cy = centroid
    max_rx, max_ry = placement_radii
    size_ratio = _font_size_ratio(font_size, min_font_size, max_font_size)
    min_radius = (1.0 - size_ratio) * 0.05
    radius_exponent = 0.35 + size_ratio * 1.25

    mask_ys, mask_xs = np.nonzero(mask)
    if len(mask_xs) == 0:
        return None

    best_position: tuple[int, int] | None = None
    best_score = float("inf")

    for _ in range(PLACEMENT_CANDIDATES):
        if len(mask_xs) > 0 and random.random() < 0.35:
            index = random.randrange(len(mask_xs))
            x = int(mask_xs[index] - width / 2)
            y = int(mask_ys[index] - height / 2)
        else:
            angle = random.uniform(0, 2 * math.pi)
            radius = min_radius + (1.0 - min_radius) * (random.random() ** radius_exponent)
            x = int(cx + math.cos(angle) * radius * max_rx - width / 2)
            y = int(cy + math.sin(angle) * radius * max_ry - height / 2)

        candidate = (x, y, x + width, y + height)
        if not _bbox_inside_mask(candidate, mask):
            continue
        if _bbox_overlaps(candidate, occupied):
            continue

        word_center = (x + width / 2, y + height / 2)
        score = _placement_score(
            word_center=word_center,
            centroid=centroid,
            placement_radii=placement_radii,
            size_ratio=size_ratio,
            placed_centers=placed_centers,
            angle_bin_counts=angle_bin_counts,
        )
        if score < best_score:
            best_score = score
            best_position = (x, y)

    if best_position is not None:
        return best_position

    for _ in range(200):
        index = random.randrange(len(mask_xs))
        x = int(mask_xs[index] - width / 2)
        y = int(mask_ys[index] - height / 2)
        candidate = (x, y, x + width, y + height)
        if not _bbox_inside_mask(candidate, mask):
            continue
        if _bbox_overlaps(candidate, occupied):
            continue
        return x, y

    return None


def _placement_score(
    word_center: tuple[float, float],
    centroid: tuple[float, float],
    placement_radii: tuple[float, float],
    size_ratio: float,
    placed_centers: list[tuple[float, float]],
    angle_bin_counts: list[int],
) -> float:
    cx, cy = centroid
    max_rx, max_ry = placement_radii
    wx, wy = word_center
    norm_dist = math.hypot((wx - cx) / max_rx, (wy - cy) / max_ry)
    preferred_dist = (1.0 - size_ratio) * 0.55
    score = abs(norm_dist - preferred_dist) * PLACEMENT_SOFT_DISTANCE_WEIGHT

    if norm_dist < (1.0 - size_ratio) * 0.1:
        score += ((1.0 - size_ratio) * 0.1 - norm_dist) * (1.0 - size_ratio) * 1.5
    if norm_dist > 0.2 + (1.0 - size_ratio) * 0.65 and size_ratio > 0.35:
        score += (norm_dist - (0.2 + (1.0 - size_ratio) * 0.65)) * size_ratio * 0.6

    score += angle_bin_counts[_angle_bin_index(word_center, centroid)] * PLACEMENT_ANGLE_BIN_WEIGHT

    if placed_centers:
        nearest = min(math.hypot(wx - px, wy - py) for px, py in placed_centers)
        score -= min(nearest / 180.0, 2.0) * PLACEMENT_GAP_WEIGHT

    return score


def _angle_bin_index(
    point: tuple[float, float],
    centroid: tuple[float, float],
) -> int:
    angle = math.atan2(point[1] - centroid[1], point[0] - centroid[0])
    bin_index = int((angle + math.pi) / (2 * math.pi) * PLACEMENT_ANGLE_BINS)
    return min(max(bin_index, 0), PLACEMENT_ANGLE_BINS - 1)


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
