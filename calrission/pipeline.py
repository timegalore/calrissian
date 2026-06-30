"""End-to-end word cloud generation pipeline."""

from __future__ import annotations

from pathlib import Path

from calrission.pdf_reader import extract_pdf_content
from calrission.renderer import RenderOptions, render_wordcloud, save_jpeg
from calrission.word_stats import count_words, top_words


def generate_wordcloud(
    pdf_path: Path,
    output_path: Path,
    maxwords: int,
    shape: str,
    font_name: str,
    max_font_size: float,
    min_font_size: float,
    max_angle: float,
    minwords: int | None = None,
    add_border: bool = False,
) -> Path:
    content = extract_pdf_content(pdf_path, palette_size=min(maxwords, 12))
    counts, display_forms = count_words(content.text)
    words = top_words(counts, maxwords, display_forms, minwords=minwords)

    options = RenderOptions(
        shape=shape,
        font_name=font_name,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        max_angle=max_angle,
        add_border=add_border,
    )
    image = render_wordcloud(words, content.palette, options)
    return save_jpeg(image, output_path)
