"""Word filtering rules for Calrission."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files

from wordfreq import zipf_frequency

YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")
ORDINAL_PATTERN = re.compile(r"^\d+(st|nd|rd|th)$", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[A-Za-z']+")
DIGIT_IN_WORD_PATTERN = re.compile(r"\d")

# Second halves of words split by end-of-line hyphens (e.g. organiza-\ntion).
HYPHENATION_SUFFIX_FRAGMENTS = frozenset(
    {
        "ally",
        "ance",
        "bility",
        "cial",
        "edly",
        "ence",
        "eous",
        "ical",
        "ically",
        "ious",
        "ities",
        "ity",
        "ment",
        "ness",
        "nality",
        "sion",
        "tion",
        "tial",
        "ually",
        "uous",
        "ward",
        "wards",
    }
)

# Short tokens use a lower bar; longer tokens must be extremely common to drop.
SHORT_WORD_MAX_ZIPF = 5.5
MAX_GENERAL_ENGLISH_ZIPF = 5.5

NUMBER_WORDS = frozenset(
    {
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
    }
)
TEXTUAL_ORDINALS = frozenset(
    {
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
        "thirteenth",
        "fourteenth",
        "fifteenth",
        "sixteenth",
        "seventeenth",
        "eighteenth",
        "nineteenth",
        "twentieth",
    }
)
MONTH_NAMES = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
    }
)
TEMPORAL_ENUMERATIVE_WORDS = (
    NUMBER_WORDS
    | TEXTUAL_ORDINALS
    | MONTH_NAMES
    | frozenset(
        {
            "day",
            "days",
            "hour",
            "hours",
            "minute",
            "minutes",
            "month",
            "months",
            "week",
            "weeks",
            "year",
            "years",
        }
    )
)


# Topical two-letter tokens that share a code with ISO 3166-1 alpha-2.
COUNTRY_CODE_ALLOWLIST = frozenset({"ai"})

# Boilerplate tokens that are not topical document content.
EXCLUDED_TOKENS = frozenset({"scsc"})


@lru_cache(maxsize=1)
def _country_codes() -> frozenset[str]:
    path = files("calrission").joinpath("data/country_codes.txt")
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


@lru_cache(maxsize=1)
def _function_words() -> frozenset[str]:
    """Closed-class English words (articles, pronouns, auxiliaries, etc.)."""
    path = files("calrission").joinpath("data/function_words.txt")
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


def tokenize(text: str) -> list[tuple[str, bool]]:
    """Return (word, is_sentence_start) pairs extracted from text."""
    tokens: list[tuple[str, bool]] = []
    sentence_start = True
    index = 0

    while index < len(text):
        match = WORD_PATTERN.match(text, index)
        if match:
            tokens.append((match.group(0), sentence_start))
            sentence_start = False
            index = match.end()
            continue

        if text[index] in ".!?":
            sentence_start = True
        index += 1

    return tokens


def is_year_like(word: str) -> bool:
    return bool(YEAR_PATTERN.match(word))


def is_ordinal(word: str) -> bool:
    return bool(ORDINAL_PATTERN.match(word))


def is_proper_name(word: str, sentence_start: bool) -> bool:
    if sentence_start:
        return False
    if not word[:1].isupper():
        return False
    if word.isupper() and len(word) > 1:
        return False
    return True


def normalize_word(word: str) -> str:
    return word.lower().strip("'").replace("'", "")


def is_acronym(word: str) -> bool:
    stripped = word.strip("'").replace("'", "")
    return len(stripped) >= 2 and stripped.isalpha() and stripped.isupper()


def display_form(word: str) -> str:
    stripped = word.strip("'").replace("'", "")
    if is_acronym(stripped):
        return stripped
    return stripped.lower()


def merge_display_form(current: str, word: str) -> str:
    candidate = display_form(word)
    if is_acronym(current):
        return current
    if is_acronym(candidate):
        return candidate
    return candidate


def is_globally_common(word: str) -> bool:
    """True for open-class words that are too frequent in general English."""
    normalized = normalize_word(word)
    if len(normalized) <= 2:
        return False

    zipf = zipf_frequency(normalized, "en")
    if len(normalized) == 3:
        return zipf >= SHORT_WORD_MAX_ZIPF
    return zipf >= MAX_GENERAL_ENGLISH_ZIPF


def is_function_word(word: str) -> bool:
    """True for closed-class words that carry grammar rather than topic."""
    normalized = normalize_word(word)
    if len(normalized) <= 1:
        return True
    return normalized in _function_words()


def is_temporal_or_enumerative(word: str) -> bool:
    """True for calendar, counting, and sequencing tokens."""
    return normalize_word(word) in TEMPORAL_ENUMERATIVE_WORDS


def is_extraction_artifact(word: str) -> bool:
    """True for PDF/URL debris and other non-lexical tokens."""
    normalized = normalize_word(word)
    if DIGIT_IN_WORD_PATTERN.search(normalized):
        return True
    if normalized in HYPHENATION_SUFFIX_FRAGMENTS:
        return True
    return False


def is_country_code(word: str) -> bool:
    """True for two-letter ISO country/geopolitical codes (e.g. eu, de, uk)."""
    normalized = normalize_word(word)
    if len(normalized) != 2 or not normalized.isalpha():
        return False
    if normalized in COUNTRY_CODE_ALLOWLIST:
        return False
    return normalized in _country_codes()


def is_excluded_token(word: str) -> bool:
    """True for known non-topical tokens (e.g. publication boilerplate)."""
    return normalize_word(word) in EXCLUDED_TOKENS


def lacks_contextual_meaning(word: str) -> bool:
    """True when a token is unlikely to convey topical meaning in a word cloud."""
    return (
        is_function_word(word)
        or is_temporal_or_enumerative(word)
        or is_extraction_artifact(word)
        or is_country_code(word)
        or is_globally_common(word)
    )


def should_exclude(word: str, sentence_start: bool) -> bool:
    if is_year_like(word):
        return True
    if is_ordinal(word):
        return True
    if is_proper_name(word, sentence_start):
        return True
    if is_excluded_token(word):
        return True
    if lacks_contextual_meaning(word):
        return True
    return False
