"""Command-line interface for Calrission."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from calrission.pipeline import generate_wordcloud
from calrission.renderer import SHAPE_CHOICES


DEFAULT_FONT = "Cooper Black"
DEFAULT_MAXWORDS = 100
DEFAULT_SHAPE = "cloud"
DEFAULT_MAX_FONT_SIZE = 120
DEFAULT_MIN_FONT_SIZE = 20
DEFAULT_MAX_ANGLE = 45


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calrission",
        description="Generate a word cloud image from a PDF document.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to the PDF file to inspect",
    )
    parser.add_argument(
        "--maxwords",
        type=int,
        default=DEFAULT_MAXWORDS,
        metavar="N",
        help=f"Maximum number of words in the cloud (default: {DEFAULT_MAXWORDS})",
    )
    parser.add_argument(
        "--minwords",
        type=int,
        default=None,
        metavar="N",
        help="Minimum number of words that must appear in the cloud",
    )
    parser.add_argument(
        "--shape",
        choices=SHAPE_CHOICES,
        default=DEFAULT_SHAPE,
        help=f"Word cloud shape (default: {DEFAULT_SHAPE})",
    )
    parser.add_argument(
        "--font",
        default=DEFAULT_FONT,
        help=f"Font family name (default: {DEFAULT_FONT})",
    )
    parser.add_argument(
        "--max-font-size",
        type=float,
        default=DEFAULT_MAX_FONT_SIZE,
        metavar="PTS",
        help=f"Largest font size in points (default: {DEFAULT_MAX_FONT_SIZE})",
    )
    parser.add_argument(
        "--min-font-size",
        type=float,
        default=DEFAULT_MIN_FONT_SIZE,
        metavar="PTS",
        help=f"Smallest font size in points (default: {DEFAULT_MIN_FONT_SIZE})",
    )
    parser.add_argument(
        "--max-angle",
        type=float,
        default=DEFAULT_MAX_ANGLE,
        metavar="DEG",
        help=f"Maximum absolute word rotation in degrees (default: {DEFAULT_MAX_ANGLE})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JPEG path (default: <pdf_stem>_wordcloud.jpg in the current directory)",
    )
    parser.add_argument(
        "--addborder",
        action="store_true",
        help="Draw the profile outline around the word cloud shape",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not args.path.exists():
        raise SystemExit(f"Error: PDF not found: {args.path}")
    if not args.path.is_file():
        raise SystemExit(f"Error: path is not a file: {args.path}")
    if args.path.suffix.lower() != ".pdf":
        raise SystemExit(f"Error: expected a PDF file, got: {args.path}")
    if args.maxwords < 1:
        raise SystemExit("Error: --maxwords must be at least 1")
    if args.minwords is not None:
        if args.minwords < 1:
            raise SystemExit("Error: --minwords must be at least 1")
        if args.minwords > args.maxwords:
            raise SystemExit("Error: --minwords cannot exceed --maxwords")
    if args.min_font_size <= 0:
        raise SystemExit("Error: --min-font-size must be positive")
    if args.max_font_size <= 0:
        raise SystemExit("Error: --max-font-size must be positive")
    if args.min_font_size > args.max_font_size:
        raise SystemExit("Error: --min-font-size cannot exceed --max-font-size")
    if args.max_angle < 0 or args.max_angle > 90:
        raise SystemExit("Error: --max-angle must be between 0 and 90 degrees")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args)

    output_path = args.output or Path.cwd() / f"{args.path.stem}_wordcloud.jpg"

    try:
        written = generate_wordcloud(
            pdf_path=args.path,
            output_path=output_path,
            maxwords=args.maxwords,
            minwords=args.minwords,
            shape=args.shape,
            font_name=args.font,
            max_font_size=args.max_font_size,
            min_font_size=args.min_font_size,
            max_angle=args.max_angle,
            add_border=args.addborder,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {written}")
    return 0
