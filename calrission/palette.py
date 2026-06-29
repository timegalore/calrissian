"""Colour palette assignment for rendered words."""

from __future__ import annotations


def assign_colours(
    word_count: int,
    palette: list[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    if word_count <= 0:
        return []
    if not palette:
        palette = [(0, 122, 255)]

    if word_count <= len(palette):
        return palette[:word_count]

    assignments: list[tuple[int, int, int]] = [palette[0]] * word_count
    colour_count = len(palette)

    for colour_index in range(colour_count):
        rank = colour_index
        while rank < word_count:
            assignments[rank] = palette[colour_index]
            rank += colour_count

    return assignments
