"""Regenerate Calrission Atomic Requirements.rtf."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_REQUIREMENTS_RTF = "Calrission Atomic Requirements.rtf"
OUT_PATH = ROOT / MASTER_REQUIREMENTS_RTF
LAST_UPDATED = "2026-06-30"

# Table column widths in twips (page content width = 9360 with 1" margins)
LABEL_COL = 2880  # 2"
VALUE_COL = 9360  # full text width

# Each requirement: (id, source, category, title, statement, criteria, phase, status, notes)
REQUIREMENTS = [
    (
        "PAR-001",
        "PAR-001",
        "Parameters",
        "Python command-line application",
        "Calrission is a command-line application implemented in Python.",
        "Application is invoked from a shell; no GUI is required for core operation.",
        "Phase 1",
        "Not started",
        "Main entry point to be named calrission (see PAR-002).",
    ),
    (
        "PAR-002",
        "PAR-002",
        "Parameters",
        "Main entry point name",
        'The main entry point for the application is named "calrission".',
        "Running calrission (or python -m calrission, if packaged) starts the application.",
        "Phase 1",
        "Not started",
        "",
    ),
    (
        "PAR-003",
        "PAR-003",
        "Parameters",
        "PDF path argument",
        "The application accepts a required path argument pointing to the PDF file to inspect.",
        "CLI rejects missing path with a clear error; supplied path is used as the input document.",
        "Phase 1",
        "Not started",
        "Source spec names this parameter path.",
    ),
    (
        "PAR-004",
        "PAR-003",
        "Parameters",
        "Maximum word count",
        "The application accepts a maxwords parameter for the maximum number of words to appear in the cloud, defaulting to 100 when omitted.",
        "When maxwords is not supplied, 100 words are used; when supplied, at most that many distinct words appear in the output image.",
        "Phase 1",
        "Not started",
        "",
    ),
    (
        "PAR-011",
        "PAR-003",
        "Parameters",
        "Minimum word count",
        "The application accepts an optional minwords parameter for the minimum number of words that must appear in the cloud.",
        "When minwords is supplied, generation fails with a clear error if fewer distinct words remain after filtering; when omitted, no minimum is enforced beyond requiring at least one word.",
        "Phase 1",
        "Implemented",
        "CLI flag: --minwords.",
    ),
    (
        "PAR-012",
        "PAR-003",
        "Parameters",
        "minwords versus maxwords validation",
        "When both minwords and maxwords are supplied, minwords must be less than or equal to maxwords.",
        "CLI rejects minwords > maxwords with a clear error; minwords equal to or less than maxwords is accepted.",
        "Phase 1",
        "Implemented",
        "",
    ),
    (
        "PAR-005",
        "PAR-003",
        "Parameters",
        "Cloud shape selection",
        'The application accepts a shape parameter with allowed values "rectangle" or "cloud", defaulting to "cloud" when omitted.',
        'CLI accepts only rectangle and cloud; default is cloud; invalid values are rejected with a clear error.',
        "Phase 1",
        "Not started",
        "",
    ),
    (
        "PAR-006",
        "PAR-003",
        "Parameters",
        "Font family selection",
        "The application accepts a font parameter specifying the font family (for example tahoma or calibri).",
        "Supplied font name is applied to rendered words; missing font falls back to a sensible default documented in code.",
        "Phase 1",
        "Not started",
        "Source spec example spelling: calibiri.",
    ),
    (
        "PAR-007",
        "PAR-003",
        "Parameters",
        "Maximum font size",
        "The application accepts a max-font-size parameter for the largest font size in points, defaulting to 120 when omitted.",
        "Most frequent word uses a font size no greater than max-font-size; default is 120 pt.",
        "Phase 1",
        "Not started",
        "",
    ),
    (
        "PAR-008",
        "PAR-003",
        "Parameters",
        "Minimum font size",
        "The application accepts a min-font-size parameter for the smallest font size in points, defaulting to 20 when omitted.",
        "Least frequent included word uses a font size no smaller than min-font-size; default is 20 pt.",
        "Phase 1",
        "Not started",
        "",
    ),
    (
        "PAR-009",
        "PAR-003",
        "Parameters",
        "Maximum word angle",
        "The application accepts a max-angle parameter for the maximum absolute rotation of each word in degrees, defaulting to 45 when omitted.",
        "Each word orientation is randomised between 0 (horizontal) and max-angle; default max-angle is 45 degrees.",
        "Phase 1",
        "Not started",
        "",
    ),
    (
        "PAR-010",
        "PAR-003",
        "Parameters",
        "Output file path",
        "The application accepts an optional output parameter specifying the path of the JPEG file to write.",
        "When output is supplied, the word cloud is written to that path; when omitted, the default is <pdf_stem>_wordcloud.jpg in the current working directory.",
        "Phase 1",
        "Not started",
        "CLI flag: -o / --output.",
    ),
    (
        "FILT-001",
        "Overview",
        "Word filtering",
        "Exclude year-like numbers",
        "Words that are not significant to document content, such as numbers used as years, are excluded from the word cloud.",
        "Standalone numeric tokens resembling years (e.g. 1999, 2024) do not appear in the counted or rendered word set.",
        "Phase 2",
        "Not started",
        "Derived from project overview; not numbered in source spec.",
    ),
    (
        "FILT-002",
        "Overview",
        "Word filtering",
        "Exclude ordinals",
        "Ordinal tokens such as 1st, 2nd, and 3rd are excluded from the word cloud.",
        "Ordinal forms matching common patterns (1st, 2nd, 3rd, 4th, etc.) are not counted or rendered.",
        "Phase 2",
        "Not started",
        "Derived from project overview.",
    ),
    (
        "FILT-003",
        "Overview",
        "Word filtering",
        "Exclude proper names",
        "Proper names that are not significant to document content, such as Paul or Mike, are excluded from the word cloud.",
        "Detected proper-name tokens (capitalised personal names not at sentence start, or via NER/heuristic) are excluded from the word cloud.",
        "Phase 2",
        "Not started",
        "Derived from project overview; exact detection strategy is an implementation choice.",
    ),
    (
        "FILT-004",
        "Overview",
        "Word filtering",
        "Exclude prepositions and articles",
        "Grammatical devices such as prepositions, definite articles, indefinite articles, single-letter tokens, common function words, month names, number words, textual ordinals, and ordinal suffix fragments are omitted from the word cloud.",
        "Common prepositions and articles, single-letter tokens, function words (e.g. and, it, but, who, can, are), month names (e.g. april, feb), number words (e.g. one, two, three), textual ordinals (e.g. first, second, third), and ordinal suffix fragments (e.g. th, nd, rd) do not appear in the counted or rendered word set.",
        "Phase 2",
        "Not started",
        "Derived from project overview.",
    ),
    (
        "BAS-001",
        "BAS-001",
        "Basic function",
        "Count word occurrences in PDF",
        "The application inspects the referenced PDF and counts the number of occurrences of each remaining word.",
        "For a known test PDF, per-word counts match expected frequencies after filtering rules are applied.",
        "Phase 2",
        "Not started",
        "",
    ),
    (
        "BAS-002",
        "BAS-002",
        "Basic function",
        "Limit to maxwords by frequency",
        "If the number of unique words exceeds maxwords, the least frequent words are discarded so that at most maxwords words remain.",
        "When unique word count > maxwords, output contains exactly maxwords words ranked by descending frequency; lowest-frequency words are dropped.",
        "Phase 2",
        "Not started",
        "",
    ),
    (
        "BAS-003",
        "BAS-003",
        "Basic function",
        "Enforce minimum word count",
        "When minwords is supplied, the application requires at least that many distinct words after filtering before rendering.",
        "If filtered vocabulary size is less than minwords, processing stops with a clear error stating how many words remain; otherwise at least minwords words are included (subject to the maxwords cap).",
        "Phase 2",
        "Implemented",
        "",
    ),
    (
        "DIS-001",
        "DIS-001",
        "Display",
        "Rectangle layout",
        'When shape is "rectangle", words occupy a rectangular region in the image.',
        "Generated image word bounding boxes collectively fill a rectangular silhouette with minimal unused corner space relative to the chosen canvas.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-002",
        "DIS-002",
        "Display",
        "Cloud layout",
        'When shape is "cloud", words occupy a cloud-shaped region in the image.',
        "Generated image word bounding boxes collectively fill a cloud-like silhouette rather than a strict rectangle.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-003",
        "DIS-003",
        "Display",
        "Largest font for most frequent words",
        "The most frequently used words are rendered using the largest font sizes, up to max-font-size.",
        "Highest-frequency word uses the maximum rendered font size, capped at max-font-size.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-004",
        "DIS-004",
        "Display",
        "Smallest font for least frequent words",
        "The least frequently used included words are rendered using the smallest font sizes, down to min-font-size.",
        "Lowest-frequency included word uses the minimum rendered font size, floored at min-font-size.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-005",
        "DIS-005",
        "Display",
        "Linear font scaling by frequency",
        "Font sizes for words between the most and least frequent scale linearly in proportion to word frequency.",
        "For three or more words with distinct frequencies, intermediate font sizes interpolate linearly between min and max font sizes by rank/frequency.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-006",
        "DIS-006",
        "Display",
        "PDF-derived colour scheme",
        "The word cloud colour scheme is similar to the colours used in the source PDF.",
        "Dominant colours sampled from the PDF are reflected in the palette applied to rendered words (manual or automated colour-distance check).",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-007",
        "DIS-007",
        "Display",
        "Random word orientation",
        "Each word orientation is randomised between 0 degrees (horizontal) and max-angle, and may slope upward or downward left-to-right.",
        "Rendered words show rotation magnitudes in [0, max-angle]; both positive and negative slopes appear across a multi-word sample.",
        "Phase 3",
        "Not started",
        "Example from source: 35 degrees up or down left-to-right.",
    ),
    (
        "DIS-008",
        "DIS-008",
        "Display",
        "Centre-weighted placement",
        "More frequent (larger) words are placed near the centre of the image; less frequent words are spread around them to minimise gaps and honour the specified shape.",
        "Highest-frequency words appear closer to the image centroid than lower-frequency words; layout avoids large empty regions within the target shape.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-009",
        "DIS-009",
        "Display",
        "Distinct word colours",
        "Words use different colours where possible based on the derived colour scheme.",
        "When sufficient palette colours exist, adjacent high-rank words do not reuse the same colour unnecessarily.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "DIS-010",
        "DIS-010",
        "Display",
        "Colour reuse by frequency distance",
        "When colours must be reused, they are applied to words that are most distant in frequency from one another.",
        "If palette size < word count, colour repeats occur on pairs/groups with maximal frequency separation rather than on adjacent ranks.",
        "Phase 3",
        "Not started",
        "",
    ),
    (
        "OUT-001",
        "OUT-001",
        "Output",
        "JPEG output format",
        "The output is a JPEG (.jpg) file.",
        "Primary output file extension is .jpg.",
        "Phase 4",
        "Not started",
        "",
    ),
    (
        "OUT-002",
        "OUT-002",
        "Output",
        "Output resolution and dimensions",
        "The output image is saved at 300 DPI and is at least 1000 pixels wide.",
        "Saved JPEG metadata reports 300 DPI (horizontal and vertical); image width in pixels is >= 1000.",
        "Phase 4",
        "Not started",
        "",
    ),
]

PHASE_SUMMARY = [
    (
        "Phase 1 — Command-line interface",
        "Python CLI named calrission; PDF path and rendering parameters (PAR-001–PAR-012).",
        "12 requirements",
        "Not started",
    ),
    (
        "Phase 2 — PDF processing",
        "Extract and count words; exclude non-significant tokens; enforce minwords and cap vocabulary at maxwords (FILT, BAS).",
        "7 requirements",
        "Not started",
    ),
    (
        "Phase 3 — Word cloud rendering",
        "Shape, font scaling, colour, orientation, and placement rules (DIS-001–DIS-010).",
        "10 requirements",
        "Not started",
    ),
    (
        "Phase 4 — Output",
        "Write JPEG output at 300 DPI and minimum width (OUT-001–OUT-002).",
        "2 requirements",
        "Not started",
    ),
]

PROJECT_STATUS_NOTES = (
    "Derived from Calrission requirements.docx. "
    "30 atomic requirements; minwords support is documented in PAR-011, PAR-012, and BAS-003. "
    "Edit REQUIREMENTS in scripts/generate_atomic_requirements_rtf.py and regenerate to refresh this file."
)


def rtf_escape(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return "".join(ch if ord(ch) < 128 else f"\\u{ord(ch)}?" for ch in text)


def heading(title: str) -> str:
    return f"\\pard\\sb240\\sa60\\b {rtf_escape(title)}\\b0\\par"


def body(text: str, after: int = 120) -> str:
    return f"\\pard\\sa{after} {rtf_escape(text)}\\par"


def requirement_title(rid: str, title: str) -> str:
    return (
        f"\\pard\\sb180\\sa80\\tx2880\\b {rtf_escape(rid)}\\b0"
        f"\\tab\\i {rtf_escape(title)}\\i0\\par"
    )


def table_row(label: str, value: str) -> str:
    label_text = rtf_escape(label if label.endswith(":") else f"{label}:")
    border = "\\clbrdrt\\brdrs\\brdrw10\\clbrdrl\\brdrs\\brdrw10\\clbrdrb\\brdrs\\brdrw10\\clbrdrr\\brdrs\\brdrw10"
    return (
        f"\\trowd\\trgaph108\\trleft0\\trrh0\\clvertalt"
        f"{border}\\cellx{LABEL_COL}"
        f"{border}\\cellx{VALUE_COL}"
        f"\\pard\\intbl\\sb60\\sa60\\fi0\\li0\\b {label_text}\\b0\\cell"
        f"\\pard\\intbl\\sb60\\sa60\\fi0\\li0 {rtf_escape(value)}\\cell"
        f"\\row"
    )


def requirement_table(
    source: str,
    phase: str,
    status: str,
    statement: str,
    criteria: str,
    notes: str,
) -> str:
    rows = [
        table_row("Source", source),
        table_row("Phase", phase),
        table_row("Status", status),
        table_row("Requirement", statement),
        table_row("Acceptance criteria", criteria),
        table_row("Notes", notes if notes else "—"),
    ]
    return "".join(rows)


def phase_summary_section() -> str:
    parts = [heading("Project status (current)")]
    parts.append(body(f"Last updated: {LAST_UPDATED}.", after=80))
    parts.append(body(PROJECT_STATUS_NOTES, after=160))
    parts.append(heading("Phase summary"))
    for phase, scope, count, state in PHASE_SUMMARY:
        parts.append(requirement_title(phase, scope))
        parts.append(
            requirement_table(
                source="Delivery plan",
                phase=phase.split(" — ", 1)[0],
                status=state,
                statement=scope,
                criteria=count,
                notes="See requirements below for detail.",
            )
        )
        parts.append("\\pard\\sa120\\par")
    return "".join(parts)


def build_rtf() -> str:
    parts = [
        "{\\rtf1\\ansi\\deff0",
        "{\\fonttbl{\\f0\\fswiss Arial;}{\\f1\\fmodern Courier New;}}",
        "{\\colortbl;\\red0\\green0\\blue0;\\red0\\green70\\blue130;\\red100\\green100\\blue100;}",
        "\\paperw12240\\paperh15840\\margl1440\\margr1440\\margt1440\\margb1440",
        "\\viewkind4\\uc1\\f0\\fs22\\sl276\\slmult1",
        "\\pard\\qc\\sb0\\sa120\\b\\fs32 Calrission\\b0\\par",
        "\\pard\\qc\\sa60\\fs22\\cf3 Atomic Testable Requirements\\cf1\\par",
        "\\pard\\qc\\sa240\\i Derived from Calrission requirements.docx\\i0\\par",
        heading("Purpose"),
        body(
            "This document breaks the source requirements into atomic, independently testable items. "
            "Each requirement has a unique ID, traceability to the original requirement, acceptance criteria, "
            "phase, implementation status, and notes for collaboration."
        ),
        heading("How to use"),
        body(
            "Update the Status field as work progresses. Edit REQUIREMENTS in "
            "scripts/generate_atomic_requirements_rtf.py and regenerate this file. "
            "IDs are stable; do not renumber when adding new items — append with the next ID in the category."
        ),
        heading("Status values"),
        table_row(
            "Allowed values",
            "Not started  |  Partial  |  Implemented  |  Verified  |  Deferred",
        ),
        "\\pard\\sa240\\par",
        phase_summary_section(),
    ]

    current_category = None
    for rid, source, category, title, statement, criteria, phase, status, notes in REQUIREMENTS:
        if category != current_category:
            current_category = category
            parts.append(
                f"\\pard\\sb360\\sa120\\b\\fs26\\cf2 {rtf_escape(category)}\\cf1\\b0\\fs22\\par"
            )

        parts.append(requirement_title(rid, title))
        parts.append(
            requirement_table(source, phase, status, statement, criteria, notes)
        )
        parts.append("\\pard\\sa120\\par")

    parts.append("}")
    return "".join(parts)


def main() -> None:
    OUT_PATH.write_text(build_rtf(), encoding="ascii", errors="replace")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
