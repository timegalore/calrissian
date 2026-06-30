"""Word cloud image rendering."""

from __future__ import annotations

import math
import random
import struct
import sys
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
CLOUD_OUTLINE_STROKE_DILATE = max(round(1 * RENDER_SCALE), 2)
CLOUD_OUTLINE_MORPH_CLOSE = max(round(1 * RENDER_SCALE), 1)
CLOUD_PLACEMENT_INSET = max(round(8 * RENDER_SCALE), 10)
CLOUD_SURFACE_ROTATION_BLEND = 0.72
CLOUD_RANDOM_ANGLE_SCALE = 0.0
CLOUD_SURFACE_ARC_LIFT = 0.22
CLOUD_SURFACE_WARP_STRENGTH = 0.82
CLOUD_TANGENT_MAX_DEG = 42.0
CLOUD_TANGENT_RAMP = 0.14
CLOUD_DEPTH_SCALE_MIN = 0.54
CLOUD_DEPTH_SIZE_MIN = 0.62
CLOUD_PERSPECTIVE_STRENGTH = 0.88
CLOUD_SHEAR_STRENGTH = 0.46
CLOUD_SHADE_MIN = 0.38
CLOUD_DEPTH_CURVE = 1.85
CLOUD_VOLUME_EDGE_SHADE = 64
CLOUD_VOLUME_HIGHLIGHT = 34
CLOUD_WORD_SHADOW_ALPHA = 48
CLOUD_WORD_SHADOW_MIN_EDGE = 0.22

FONT_SEARCH_DIRS = (
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
)
FONT_EXTENSIONS = frozenset({".ttf", ".ttc", ".otf"})


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


@dataclass(frozen=True)
class CloudSurfaceParams:
    depth: float
    tangent_deg: float
    u: float
    v: float


@dataclass
class PendingPlacement:
    placement_index: int
    word: str
    count: int
    font_size: float
    angle: float
    colour: tuple[int, int, int]
    word_image: Image.Image
    position: tuple[int, int]
    depth: float
    word_center: tuple[float, float]


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
    if options.shape == "cloud":
        _draw_cloud_volume_shading(image, mask, centroid, placement_radii)
    colours = assign_colours(len(words), palette)
    counts = [count for _, count in words]
    min_count = min(counts)
    max_count = max(counts)

    font_path = _resolve_font(options.font_name)
    if font_path is None:
        raise ValueError(f"Font not found: {options.font_name!r}")
    placed: list[PlacedWord] = []
    placed_centers: list[tuple[float, float]] = []
    angle_bin_counts = [0] * PLACEMENT_ANGLE_BINS
    occupied = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)
    pending: list[PendingPlacement] = []
    use_depth_compositing = options.shape == "cloud"

    for (word, count), colour in zip(words, colours):
        font_size = _font_size_for_count(
            count,
            min_count,
            max_count,
            options.min_font_size,
            options.max_font_size,
        )
        font = _load_font(font_path, font_size)
        angle = 0.0 if options.shape == "cloud" else _random_angle(options.max_angle)
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

        flat_position = position
        depth = 1.0
        if options.shape == "cloud":
            flat_width, flat_height = word_image.size
            word_center = (
                flat_position[0] + flat_width / 2,
                flat_position[1] + flat_height / 2,
            )
            surface = _cloud_surface_params(word_center, centroid, placement_radii)
            depth = surface.depth
            word_image, position = _cloud_surface_word(
                word_image=word_image,
                word_center=word_center,
                centroid=centroid,
                placement_radii=placement_radii,
                surface=surface,
            )
            candidate_bbox = (
                position[0],
                position[1],
                position[0] + word_image.width,
                position[1] + word_image.height,
            )
            if not _alpha_fits_mask(word_image, position, mask) or _alpha_overlaps(
                word_image,
                position,
                occupied,
            ):
                word_image, position = _cloud_surface_word(
                    word_image=_render_word_image(word, font, 0.0, colour),
                    word_center=word_center,
                    centroid=centroid,
                    placement_radii=placement_radii,
                    surface=surface,
                    use_bulge=False,
                    warp_strength=0.72,
                )
                if not _alpha_fits_mask(word_image, position, mask) or _alpha_overlaps(
                    word_image,
                    position,
                    occupied,
                ):
                    word_image, position = _cloud_surface_word(
                        word_image=_render_word_image(word, font, 0.0, colour),
                        word_center=word_center,
                        centroid=centroid,
                        placement_radii=placement_radii,
                        surface=surface,
                        use_bulge=False,
                        warp_strength=0.45,
                    )
                    if not _alpha_fits_mask(word_image, position, mask) or _alpha_overlaps(
                        word_image,
                        position,
                        occupied,
                    ):
                        word_image = _render_word_image(word, font, 0.0, colour)
                        position = flat_position
                depth = surface.depth
        else:
            flat_width, flat_height = word_image.size
            word_center = (
                flat_position[0] + flat_width / 2,
                flat_position[1] + flat_height / 2,
            )

        if use_depth_compositing:
            pending.append(
                PendingPlacement(
                    placement_index=len(placed),
                    word=word,
                    count=count,
                    font_size=font_size,
                    angle=angle,
                    colour=colour,
                    word_image=word_image,
                    position=position,
                    depth=depth,
                    word_center=word_center,
                )
            )
            word_bbox = (
                position[0],
                position[1],
                position[0] + word_image.width,
                position[1] + word_image.height,
            )
        else:
            word_bbox = _paste_word(image, word_image, position)

        _mark_occupied(occupied, word_bbox)
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

    if use_depth_compositing:
        pending.sort(key=lambda item: item.depth)
        for item in pending:
            word_bbox = _paste_word(image, item.word_image, item.position)
            placed[item.placement_index] = PlacedWord(
                word=item.word,
                count=item.count,
                font_size=item.font_size,
                angle=item.angle,
                colour=item.colour,
                bbox=word_bbox,
            )

    _draw_shape_border(image, options.shape)
    if options.shape == "cloud":
        _draw_cloud_rim_shading(image, mask, centroid, placement_radii)
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


def _normalize_font_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _resolve_font(font_name: str) -> str | None:
    normalized = _normalize_font_name(font_name)
    for directory in FONT_SEARCH_DIRS:
        if not directory.exists():
            continue
        for candidate in (
            f"{font_name}.ttf",
            f"{font_name.lower()}.ttf",
            f"{font_name}.ttc",
            f"{font_name.lower()}.ttc",
            f"{font_name}.otf",
            f"{font_name.lower()}.otf",
        ):
            path = directory / candidate
            if path.exists():
                return str(path)

    if sys.platform == "win32":
        path = _resolve_font_windows_registry(normalized)
        if path is not None:
            return path

    return _font_family_index().get(normalized)


def _resolve_font_windows_registry(normalized_name: str) -> str | None:
    import winreg

    fonts_dir = Path("C:/Windows/Fonts")
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        )
    except OSError:
        return None

    try:
        index = 0
        while True:
            try:
                display_name, filename, _ = winreg.EnumValue(key, index)
            except OSError:
                break
            index += 1
            family = _normalize_font_name(display_name.split("(", 1)[0])
            if family == normalized_name:
                font_path = fonts_dir / filename
                if font_path.exists():
                    return str(font_path)
    finally:
        winreg.CloseKey(key)
    return None


@lru_cache(maxsize=1)
def _font_family_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for directory in FONT_SEARCH_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in FONT_EXTENSIONS:
                continue
            for family in _font_family_names(path):
                index.setdefault(family, str(path))
    return index


@lru_cache(maxsize=512)
def _font_family_names(font_path: Path) -> frozenset[str]:
    try:
        data = font_path.read_bytes()
    except OSError:
        return frozenset()

    if data[:4] == b"ttcf":
        names: set[str] = set()
        num_fonts = struct.unpack_from(">I", data, 8)[0]
        for index in range(num_fonts):
            offset = struct.unpack_from(">I", data, 12 + index * 4)[0]
            names.update(_sfnt_family_names(data, offset))
        return frozenset(names)

    return frozenset(_sfnt_family_names(data))


def _sfnt_family_names(data: bytes, offset: int = 0) -> set[str]:
    num_tables = struct.unpack_from(">H", data, offset + 4)[0]
    name_table_offset = None
    for index in range(num_tables):
        record = offset + 12 + index * 16
        if data[record : record + 4] != b"name":
            continue
        name_table_offset = offset + struct.unpack_from(">I", data, record + 8)[0]
        break
    if name_table_offset is None:
        return set()
    return _parse_name_table(data, name_table_offset)


def _parse_name_table(data: bytes, table_offset: int) -> set[str]:
    count = struct.unpack_from(">H", data, table_offset + 2)[0]
    string_offset = struct.unpack_from(">H", data, table_offset + 4)[0]
    names: set[str] = set()
    record_base = table_offset + 6

    for index in range(count):
        record = record_base + index * 12
        platform_id, _encoding_id, _language_id, name_id, length, name_offset = struct.unpack_from(
            ">HHHHHH",
            data,
            record,
        )
        if name_id not in (1, 16):
            continue
        start = table_offset + string_offset + name_offset
        decoded = _decode_name_record(data[start : start + length], platform_id)
        if decoded:
            names.add(_normalize_font_name(decoded))
    return names


def _decode_name_record(raw: bytes, platform_id: int) -> str | None:
    if not raw:
        return None
    try:
        if platform_id in (0, 3):
            return raw.decode("utf-16-be")
        if platform_id == 1:
            return raw.decode("latin-1")
    except UnicodeDecodeError:
        return None
    return None


def _load_font(font_path: str, size: float) -> ImageFont.FreeTypeFont:
    pixel_size = max(round(size * RENDER_SCALE), 1)
    try:
        return ImageFont.truetype(font_path, size=pixel_size)
    except OSError as exc:
        raise ValueError(f"Unable to load font {font_path!r}: {exc}") from exc


def _shape_mask(shape: str) -> np.ndarray:
    if shape == "cloud":
        interior, _ = _cloud_shape_arrays()
        return _erode_bool(interior, CLOUD_PLACEMENT_INSET)

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
        _, outline = _cloud_shape_arrays()
        pixels = np.array(image)
        pixels[outline < CLOUD_OUTLINE_STROKE_THRESHOLD] = (0, 0, 0)
        image.paste(Image.fromarray(pixels))
        return

    border = _outline_mask(_shape_mask(shape), SHAPE_BORDER_WIDTH)
    pixels = np.array(image)
    pixels[border] = (0, 0, 0)
    image.paste(Image.fromarray(pixels))


@lru_cache(maxsize=1)
def _cloud_shape_arrays() -> tuple[np.ndarray, np.ndarray]:
    if not CLOUD_OUTLINE_PATH.exists():
        raise FileNotFoundError(f"Cloud outline image not found: {CLOUD_OUTLINE_PATH}")

    outline = Image.open(CLOUD_OUTLINE_PATH).convert("RGBA")
    background = Image.new("RGBA", outline.size, (255, 255, 255, 255))
    source = Image.alpha_composite(background, outline).convert("L")

    scale = min(
        (CANVAS_WIDTH - 2 * MARGIN) / source.width,
        (CANVAS_HEIGHT - 2 * MARGIN) / source.height,
    )
    target_width = max(1, int(source.width * scale))
    target_height = max(1, int(source.height * scale))

    resized = source.resize((target_width, target_height), Image.Resampling.LANCZOS)
    resized_array = np.array(resized)
    stroke = resized_array < CLOUD_OUTLINE_STROKE_THRESHOLD
    barrier = _close_bool(
        _dilate_bool(stroke, CLOUD_OUTLINE_STROKE_DILATE),
        CLOUD_OUTLINE_MORPH_CLOSE,
    )
    interior = _interior_from_barrier(barrier)

    outline_canvas = np.full((CANVAS_HEIGHT, CANVAS_WIDTH), 255, dtype=np.uint8)
    interior_canvas = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)
    offset_x = (CANVAS_WIDTH - target_width) // 2
    offset_y = (CANVAS_HEIGHT - target_height) // 2
    outline_canvas[offset_y : offset_y + target_height, offset_x : offset_x + target_width] = resized_array
    interior_canvas[offset_y : offset_y + target_height, offset_x : offset_x + target_width] = interior
    return interior_canvas, outline_canvas


def _interior_from_barrier(barrier: np.ndarray) -> np.ndarray:
    height, width = barrier.shape
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


def _erode_bool(mask: np.ndarray, radius: int) -> np.ndarray:
    eroded = mask.copy()
    for _ in range(radius):
        shrunk = eroded.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                shrunk &= _shift_mask(eroded, dy, dx)
        eroded = shrunk
    return eroded


def _close_bool(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask
    return _erode_bool(_dilate_bool(mask, radius), radius)


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


def _cloud_surface_params(
    point: tuple[float, float],
    centroid: tuple[float, float],
    radii: tuple[float, float],
) -> CloudSurfaceParams:
    cx, cy = centroid
    max_rx, max_ry = radii
    u = (point[0] - cx) / max_rx if max_rx else 0.0
    v = (point[1] - cy) / max_ry if max_ry else 0.0
    radial = min(math.hypot(u, v), 1.0)
    depth = math.sqrt(max(0.04, 1.0 - radial * radial))
    tangent_strength = min(1.0, radial / CLOUD_TANGENT_RAMP)
    tangent_deg = (
        math.degrees(math.atan2(v, u) + math.pi / 2)
        * tangent_strength
        * (0.45 + 0.55 * depth)
    )
    tangent_deg = max(-CLOUD_TANGENT_MAX_DEG, min(CLOUD_TANGENT_MAX_DEG, tangent_deg))
    return CloudSurfaceParams(depth=depth, tangent_deg=tangent_deg, u=u, v=v)


def _cloud_surface_bulge(
    point: tuple[float, float],
    centroid: tuple[float, float],
    radii: tuple[float, float],
    params: CloudSurfaceParams,
) -> tuple[float, float]:
    cx, cy = centroid
    max_rx, max_ry = radii
    dx = point[0] - cx
    dy = point[1] - cy
    if max_rx <= 0 or max_ry <= 0:
        return point

    norm_x = dx / max_rx
    norm_y = dy / max_ry
    norm_dist = math.hypot(norm_x, norm_y)
    if norm_dist <= 1e-6:
        return point

    edge = 1.0 - _visual_depth(params.depth)
    bulge = edge * 20 * RENDER_SCALE / 2.5
    scale_x = max_rx / norm_dist
    scale_y = max_ry / norm_dist
    return (
        point[0] + norm_x * scale_x * bulge,
        point[1] + norm_y * scale_y * bulge,
    )


def _cloud_surface_word(
    word_image: Image.Image,
    word_center: tuple[float, float],
    centroid: tuple[float, float],
    placement_radii: tuple[float, float],
    surface: CloudSurfaceParams | None = None,
    use_bulge: bool = True,
    warp_strength: float = CLOUD_SURFACE_WARP_STRENGTH,
) -> tuple[Image.Image, tuple[int, int]]:
    params = surface or _cloud_surface_params(word_center, centroid, placement_radii)
    if use_bulge:
        word_center = _cloud_surface_bulge(word_center, centroid, placement_radii, params)
    transformed, position = _warp_word_onto_cloud_surface(
        word_image,
        word_center,
        centroid,
        placement_radii,
        params,
        warp_strength=warp_strength,
    )
    transformed = _add_cloud_word_shadow(transformed, params)
    return transformed, position


def _warp_word_onto_cloud_surface(
    image: Image.Image,
    word_center: tuple[float, float],
    centroid: tuple[float, float],
    placement_radii: tuple[float, float],
    center_surface: CloudSurfaceParams,
    warp_strength: float = 1.0,
) -> tuple[Image.Image, tuple[int, int]]:
    width, height = image.size
    if width <= 4 or height <= 4:
        warped = _apply_cloud_surface_effect(image, center_surface, 0.0)
        position = (
            int(round(word_center[0] - warped.width / 2)),
            int(round(word_center[1] - warped.height / 2)),
        )
        return warped, position

    source = np.array(image, dtype=np.float32)
    grid_x = np.arange(width, dtype=np.float32)
    grid_y = np.arange(height, dtype=np.float32)
    source_x, source_y = np.meshgrid(grid_x, grid_y)
    delta_x = source_x - width / 2
    delta_y = source_y - height / 2

    target_x, target_y = _forward_surface_point_vectorized(
        word_center,
        delta_x,
        delta_y,
        centroid,
        placement_radii,
        center_surface,
        warp_strength,
    )

    valid = source[:, :, 3] > 8
    if not valid.any():
        position = (
            int(round(word_center[0] - width / 2)),
            int(round(word_center[1] - height / 2)),
        )
        return image, position

    min_x = float(target_x[valid].min()) - 2.0
    min_y = float(target_y[valid].min()) - 2.0
    max_x = float(target_x[valid].max()) + 2.0
    max_y = float(target_y[valid].max()) + 2.0
    out_width = max(1, int(math.ceil(max_x - min_x)))
    out_height = max(1, int(math.ceil(max_y - min_y)))

    output = _splat_rgba(
        source,
        target_x,
        target_y,
        min_x,
        min_y,
        valid,
        out_height,
        out_width,
    )
    if output[:, :, 3].max() <= 0:
        position = (
            int(round(word_center[0] - width / 2)),
            int(round(word_center[1] - height / 2)),
        )
        return image, position

    warped = Image.fromarray(np.clip(output, 0, 255).astype(np.uint8), mode="RGBA")
    visual_depth = _visual_depth(center_surface.depth)
    warped = _add_word_surface_light(warped, visual_depth)
    warped = _shade_rgba_image(warped, visual_depth)
    return warped, (int(math.floor(min_x)), int(math.floor(min_y)))


def _forward_surface_point_vectorized(
    word_center: tuple[float, float],
    delta_x: np.ndarray,
    delta_y: np.ndarray,
    centroid: tuple[float, float],
    placement_radii: tuple[float, float],
    center_surface: CloudSurfaceParams,
    warp_strength: float,
) -> tuple[np.ndarray, np.ndarray]:
    cx, cy = centroid
    max_rx, max_ry = placement_radii
    edge_readability = 0.42 + 0.58 * center_surface.depth
    effective_warp = warp_strength * edge_readability
    center_theta = math.radians(
        center_surface.tangent_deg * CLOUD_SURFACE_ROTATION_BLEND * effective_warp
    )
    cos_t = math.cos(center_theta)
    sin_t = math.sin(center_theta)

    rotated_x = delta_x * cos_t - delta_y * sin_t
    rotated_y = delta_x * sin_t + delta_y * cos_t
    probe_x = word_center[0] + rotated_x
    probe_y = word_center[1] + rotated_y

    if max_rx <= 0 or max_ry <= 0:
        return probe_x, probe_y

    u = (probe_x - cx) / max_rx
    v = (probe_y - cy) / max_ry
    radial = np.minimum(np.hypot(u, v), 1.0)
    depth = np.sqrt(np.maximum(0.04, 1.0 - radial * radial))
    visual_depth = np.power(np.clip(depth, 0.0, 1.0), CLOUD_DEPTH_CURVE)
    edge = 1.0 - visual_depth
    scale_y = CLOUD_DEPTH_SCALE_MIN + (1.0 - CLOUD_DEPTH_SCALE_MIN) * visual_depth
    scale_x = scale_y * (1.0 - edge * np.abs(u) * 0.32 * effective_warp)
    arc_y = (
        (depth - center_surface.depth)
        * max_ry
        * CLOUD_SURFACE_ARC_LIFT
        * effective_warp
    )
    return (
        word_center[0] + rotated_x * scale_x,
        word_center[1] + rotated_y * scale_y + arc_y,
    )


def _splat_rgba(
    source: np.ndarray,
    target_x: np.ndarray,
    target_y: np.ndarray,
    min_x: float,
    min_y: float,
    valid: np.ndarray,
    out_height: int,
    out_width: int,
) -> np.ndarray:
    pixels = source[valid]
    xs = (target_x[valid] - min_x).astype(np.float32)
    ys = (target_y[valid] - min_y).astype(np.float32)

    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    wx = xs - x0
    wy = ys - y0
    alphas = pixels[:, 3] / 255.0

    rgb_accum = np.zeros((out_height, out_width, 3), dtype=np.float32)
    alpha_accum = np.zeros((out_height, out_width), dtype=np.float32)

    corner_weights = (
        ((0, 0), (1.0 - wx) * (1.0 - wy)),
        ((1, 0), wx * (1.0 - wy)),
        ((0, 1), (1.0 - wx) * wy),
        ((1, 1), wx * wy),
    )
    for (dx, dy), weight in corner_weights:
        px = x0 + dx
        py = y0 + dy
        contribution = weight * alphas
        in_bounds = (
            (px >= 0) & (px < out_width) & (py >= 0) & (py < out_height) & (contribution > 0)
        )
        if not in_bounds.any():
            continue
        px = px[in_bounds]
        py = py[in_bounds]
        contribution = contribution[in_bounds]
        rgb = pixels[in_bounds, :3]
        premultiplied = rgb * contribution[:, np.newaxis]
        np.add.at(rgb_accum, (py, px), premultiplied)
        np.add.at(alpha_accum, (py, px), contribution)

    output = np.zeros((out_height, out_width, 4), dtype=np.float32)
    painted = alpha_accum > 1e-6
    output[painted, :3] = rgb_accum[painted] / alpha_accum[painted, np.newaxis]
    output[painted, 3] = np.clip(alpha_accum[painted] * 255.0, 0, 255)
    return output


def _surface_warp_bounds(
    word_center: tuple[float, float],
    width: int,
    height: int,
    centroid: tuple[float, float],
    placement_radii: tuple[float, float],
    center_surface: CloudSurfaceParams,
    warp_strength: float = 1.0,
) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for dx in np.linspace(-width / 2, width / 2, 24):
        for dy in np.linspace(-height / 2, height / 2, 10):
            sx, sy = _forward_surface_point(
                word_center,
                float(dx),
                float(dy),
                centroid,
                placement_radii,
                center_surface,
                warp_strength,
            )
            xs.append(sx)
            ys.append(sy)
    pad = 4.0
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _forward_surface_point(
    word_center: tuple[float, float],
    dx: float,
    dy: float,
    centroid: tuple[float, float],
    placement_radii: tuple[float, float],
    center_surface: CloudSurfaceParams,
    warp_strength: float = 1.0,
) -> tuple[float, float]:
    probe_x = word_center[0] + dx
    probe_y = word_center[1] + dy
    params = _cloud_surface_params(
        (probe_x, probe_y),
        centroid,
        placement_radii,
    )
    visual_depth = _visual_depth(params.depth)
    edge = 1.0 - visual_depth
    scale_y = CLOUD_DEPTH_SCALE_MIN + (1.0 - CLOUD_DEPTH_SCALE_MIN) * visual_depth
    scale_x = scale_y * (1.0 - edge * abs(params.u) * 0.38 * warp_strength)

    scaled_x = dx * scale_x
    scaled_y = dy * scale_y
    theta = math.radians(
        params.tangent_deg * CLOUD_SURFACE_ROTATION_BLEND * warp_strength
    )
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    rotated_x = scaled_x * cos_t - scaled_y * sin_t
    rotated_y = scaled_x * sin_t + scaled_y * cos_t

    _, max_ry = placement_radii
    arc_y = (
        (params.depth - center_surface.depth)
        * max_ry
        * CLOUD_SURFACE_ARC_LIFT
        * warp_strength
    )
    return word_center[0] + rotated_x, word_center[1] + rotated_y + arc_y


def _bilinear_sample_rgba(
    source: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    height, width, _ = source.shape
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    x0 = np.clip(x0, 0, width - 1)
    y0 = np.clip(y0, 0, height - 1)

    wx = (x - x0).astype(np.float32)
    wy = (y - y0).astype(np.float32)
    wa = (1.0 - wx) * (1.0 - wy)
    wb = wx * (1.0 - wy)
    wc = (1.0 - wx) * wy
    wd = wx * wy

    return (
        source[y0, x0] * wa[:, np.newaxis]
        + source[y0, x1] * wb[:, np.newaxis]
        + source[y1, x0] * wc[:, np.newaxis]
        + source[y1, x1] * wd[:, np.newaxis]
    )


def _draw_cloud_volume_shading(
    image: Image.Image,
    mask: np.ndarray,
    centroid: tuple[float, float],
    radii: tuple[float, float],
) -> None:
    cx, cy = centroid
    max_rx, max_ry = radii
    if max_rx <= 0 or max_ry <= 0:
        return

    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return

    normalized = np.sqrt(
        np.square((xs - cx) / max_rx) + np.square((ys - cy) / max_ry)
    )
    depth = np.sqrt(np.clip(1.0 - np.minimum(normalized, 1.0) ** 2, 0.04, 1.0))
    edge = 1.0 - depth
    shade = (
        255
        - np.power(edge, 1.35) * CLOUD_VOLUME_EDGE_SHADE
        + np.power(depth, 2.4) * CLOUD_VOLUME_HIGHLIGHT
    )

    pixels = np.array(image)
    cloud_pixels = pixels[ys, xs].astype(np.float32)
    shade_factor = np.clip(shade, 185, 255)[:, np.newaxis] / 255.0
    pixels[ys, xs] = np.clip(cloud_pixels * shade_factor, 0, 255).astype(np.uint8)
    image.paste(Image.fromarray(pixels))


def _visual_depth(depth: float) -> float:
    return max(0.0, min(1.0, depth ** CLOUD_DEPTH_CURVE))


def _draw_cloud_rim_shading(
    image: Image.Image,
    mask: np.ndarray,
    centroid: tuple[float, float],
    radii: tuple[float, float],
) -> None:
    cx, cy = centroid
    max_rx, max_ry = radii
    if max_rx <= 0 or max_ry <= 0:
        return

    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return

    normalized = np.sqrt(
        np.square((xs - cx) / max_rx) + np.square((ys - cy) / max_ry)
    )
    edge = np.clip(normalized, 0.0, 1.0)
    rim = np.clip((edge - 0.55) / 0.45, 0.0, 1.0)
    shade = 1.0 - rim * 0.16

    pixels = np.array(image)
    cloud_pixels = pixels[ys, xs].astype(np.float32)
    shade_factor = shade[:, np.newaxis]
    pixels[ys, xs] = np.clip(cloud_pixels * shade_factor, 0, 255).astype(np.uint8)
    image.paste(Image.fromarray(pixels))


def _apply_cloud_surface_effect(
    image: Image.Image,
    params: CloudSurfaceParams,
    extra_angle: float,
) -> Image.Image:
    visual_depth = _visual_depth(params.depth)
    depth_scale = CLOUD_DEPTH_SIZE_MIN + (1.0 - CLOUD_DEPTH_SIZE_MIN) * visual_depth
    if depth_scale < 0.999:
        width, height = image.size
        image = image.resize(
            (
                max(1, int(width * depth_scale)),
                max(1, int(height * depth_scale)),
            ),
            Image.Resampling.LANCZOS,
        )

    rotation = (
        params.tangent_deg * CLOUD_SURFACE_ROTATION_BLEND
        + extra_angle * (1.0 - CLOUD_SURFACE_ROTATION_BLEND)
    )
    if abs(rotation) > 0.01:
        image = image.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

    edge = 1.0 - visual_depth
    shear_x = params.u * edge * CLOUD_SHEAR_STRENGTH
    shear_y = params.v * edge * (CLOUD_SHEAR_STRENGTH * 0.55)
    if abs(shear_x) > 0.001:
        image = _shear_rgba(image, shear_x, axis="x")
    if abs(shear_y) > 0.001:
        image = _shear_rgba(image, shear_y, axis="y")

    image = _perspective_foreshorten(image, params.u, params.v, visual_depth)
    image = _add_word_surface_light(image, visual_depth)
    return _trim_transparent(_shade_rgba_image(image, visual_depth))


def _trim_transparent(image: Image.Image) -> Image.Image:
    alpha = image.split()[3]
    bbox = alpha.getbbox()
    if bbox is None:
        return image
    return image.crop(bbox)


def _shear_rgba(image: Image.Image, shear: float, axis: str = "x") -> Image.Image:
    width, height = image.size
    if axis == "x":
        pad = int(abs(shear) * height) + 4
        padded = Image.new("RGBA", (width + pad * 2, height), (0, 0, 0, 0))
        padded.paste(image, (pad, 0))
        return _trim_transparent(
            padded.transform(
                padded.size,
                Image.Transform.AFFINE,
                (1, -shear, shear * pad, 0, 1, 0),
                resample=Image.Resampling.BICUBIC,
                fillcolor=(0, 0, 0, 0),
            )
        )

    pad = int(abs(shear) * width) + 4
    padded = Image.new("RGBA", (width, height + pad * 2), (0, 0, 0, 0))
    padded.paste(image, (0, pad))
    return _trim_transparent(
        padded.transform(
            padded.size,
            Image.Transform.AFFINE,
            (1, 0, 0, -shear, 1, shear * pad),
            resample=Image.Resampling.BICUBIC,
            fillcolor=(0, 0, 0, 0),
        )
    )


def _perspective_foreshorten(
    image: Image.Image,
    u: float,
    v: float,
    depth: float,
) -> Image.Image:
    width, height = image.size
    if width <= 1 or height <= 1:
        return image

    edge = 1.0 - depth
    strength = CLOUD_PERSPECTIVE_STRENGTH * edge
    vertical_scale = CLOUD_DEPTH_SCALE_MIN + (1.0 - CLOUD_DEPTH_SCALE_MIN) * depth
    horizontal_scale = 1.0 - strength * abs(u) * 0.42

    target_width = max(1, int(width * horizontal_scale))
    target_height = max(1, int(height * vertical_scale))
    scaled = image.resize(
        (target_width, target_height),
        Image.Resampling.LANCZOS,
    )

    perspective_x = max(-0.00055, min(0.00055, u * edge * 0.00078))
    perspective_y = max(-0.00055, min(0.00055, -v * edge * 0.00088))
    pad = 6
    padded = Image.new(
        "RGBA",
        (target_width + pad * 2, target_height + pad * 2),
        (0, 0, 0, 0),
    )
    padded.paste(scaled, (pad, pad))
    warped = padded.transform(
        padded.size,
        Image.Transform.PERSPECTIVE,
        (1, 0, 0, 0, 1, 0, perspective_x, perspective_y),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )
    return _trim_transparent(warped)


def _add_word_surface_light(image: Image.Image, depth: float) -> Image.Image:
    if depth < 0.45:
        return image

    width, height = image.size
    split_y = max(1, int(height * 0.34))
    top = image.crop((0, 0, width, split_y))
    bottom = image.crop((0, split_y, width, height))
    boost = 1.0 + (depth - 0.45) * 0.16
    red, green, blue, alpha = top.split()
    brighten = lambda value: max(0, min(255, int(value * boost)))
    top = Image.merge(
        "RGBA",
        (
            red.point(brighten),
            green.point(brighten),
            blue.point(brighten),
            alpha,
        ),
    )
    merged = Image.new("RGBA", image.size, (0, 0, 0, 0))
    merged.paste(top, (0, 0))
    merged.paste(bottom, (0, split_y))
    return merged


def _add_cloud_word_shadow(
    image: Image.Image,
    params: CloudSurfaceParams,
) -> Image.Image:
    visual_depth = _visual_depth(params.depth)
    edge = 1.0 - visual_depth
    if edge < CLOUD_WORD_SHADOW_MIN_EDGE:
        return image

    blur_radius = max(1, int(round(edge * 3 * RENDER_SCALE / 2.5)))
    offset_x = int(round(-params.u * edge * 10 * RENDER_SCALE / 2.5))
    offset_y = int(round(-params.v * edge * 8 * RENDER_SCALE / 2.5 + edge * 4))

    alpha = image.split()[3]
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(blur_radius))
    shadow_alpha = shadow_alpha.point(
        lambda value: min(255, int(value * CLOUD_WORD_SHADOW_ALPHA / 255))
    )
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 255))
    shadow.putalpha(shadow_alpha)

    canvas = Image.new(
        "RGBA",
        (
            image.width + abs(offset_x) + blur_radius * 2,
            image.height + abs(offset_y) + blur_radius * 2,
        ),
        (0, 0, 0, 0),
    )
    base_x = blur_radius + max(0, -offset_x)
    base_y = blur_radius + max(0, -offset_y)
    canvas.paste(shadow, (base_x + offset_x, base_y + offset_y), shadow)
    canvas.paste(image, (base_x, base_y), image)
    return canvas


def _shade_rgba_image(image: Image.Image, depth: float) -> Image.Image:
    shade = CLOUD_SHADE_MIN + (1.0 - CLOUD_SHADE_MIN) * depth
    if shade >= 0.999:
        return image

    red, green, blue, alpha = image.split()
    scale = lambda value: max(0, min(255, int(value * shade)))
    return Image.merge(
        "RGBA",
        (
            red.point(scale),
            green.point(scale),
            blue.point(scale),
            alpha,
        ),
    )


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


def _alpha_fits_mask(
    word_image: Image.Image,
    position: tuple[int, int],
    mask: np.ndarray,
) -> bool:
    alpha = np.array(word_image.split()[3])
    rows, cols = np.nonzero(alpha > 32)
    if len(rows) == 0:
        return False

    x_offset, y_offset = position
    ys = rows + y_offset
    xs = cols + x_offset
    if (
        ys.min() < 0
        or xs.min() < 0
        or ys.max() >= mask.shape[0]
        or xs.max() >= mask.shape[1]
    ):
        return False
    return bool(mask[ys, xs].all())


def _alpha_overlaps(
    word_image: Image.Image,
    position: tuple[int, int],
    occupied: np.ndarray,
) -> bool:
    alpha = np.array(word_image.split()[3])
    rows, cols = np.nonzero(alpha > 32)
    if len(rows) == 0:
        return False

    x_offset, y_offset = position
    ys = rows + y_offset
    xs = cols + x_offset
    valid = (
        (ys >= 0)
        & (xs >= 0)
        & (ys < occupied.shape[0])
        & (xs < occupied.shape[1])
    )
    if not valid.any():
        return False
    return bool(occupied[ys[valid], xs[valid]].any())


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
    return region.size > 0 and region.all()


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


