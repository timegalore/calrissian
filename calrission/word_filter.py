"""Word filtering rules for Calrission."""

from __future__ import annotations

import re

YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")
ORDINAL_PATTERN = re.compile(r"^\d+(st|nd|rd|th)$", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[A-Za-z']+")

ARTICLES = frozenset({"a", "an", "the"})
PREPOSITIONS = frozenset(
    {
        "about",
        "above",
        "across",
        "after",
        "against",
        "along",
        "amid",
        "among",
        "around",
        "at",
        "before",
        "behind",
        "below",
        "beneath",
        "beside",
        "besides",
        "between",
        "beyond",
        "by",
        "down",
        "during",
        "except",
        "for",
        "from",
        "in",
        "inside",
        "into",
        "near",
        "of",
        "off",
        "on",
        "onto",
        "out",
        "outside",
        "over",
        "past",
        "since",
        "through",
        "throughout",
        "to",
        "toward",
        "towards",
        "under",
        "underneath",
        "until",
        "up",
        "upon",
        "with",
        "within",
        "without",
    }
)
GRAMMATICAL_STOP_WORDS = ARTICLES | PREPOSITIONS
COMMON_STOP_WORDS = frozenset(
    {
        "all",
        "also",
        "am",
        "and",
        "as",
        "are",
        "be",
        "but",
        "can",
        "co",
        "com",
        "could",
        "do",
        "does",
        "had",
        "have",
        "has",
        "he",
        "here",
        "his",
        "how",
        "however",
        "https",
        "if",
        "ing",
        "is",
        "it",
        "its",
        "me",
        "multi",
        "nd",
        "no",
        "not",
        "or",
        "our",
        "rd",
        "see",
        "shall",
        "she",
        "should",
        "so",
        "some",
        "that",
        "them",
        "their",
        "these",
        "they",
        "this",
        "those",
        "there",
        "then",
        "th",
        "thus",
        "too",
        "use",
        "what",
        "when",
        "which",
        "who",
        "will",
        "we",
        "you",
        "your",
    }
)
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
STOP_WORDS = GRAMMATICAL_STOP_WORDS | COMMON_STOP_WORDS | NUMBER_WORDS | TEXTUAL_ORDINALS | MONTH_NAMES


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


def is_single_letter_word(word: str) -> bool:
    return len(normalize_word(word)) == 1


def is_grammatical_stop_word(word: str) -> bool:
    normalized = normalize_word(word)
    if is_single_letter_word(word):
        return True
    return normalized in STOP_WORDS


def should_exclude(word: str, sentence_start: bool) -> bool:
    if is_year_like(word):
        return True
    if is_ordinal(word):
        return True
    if is_proper_name(word, sentence_start):
        return True
    if is_grammatical_stop_word(word):
        return True
    return False
