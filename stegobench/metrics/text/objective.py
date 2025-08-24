"""
Text metrics for StegoBench.

This module exposes three text-comparison metrics as simple functions that accept
file paths and return numeric scores:

- text_similarity: Character-level similarity percentage in [0..100].
- text_levenshtein: Edit distance (integer).
- text_jaccard: Jaccard similarity (percentage) over tokens/characters or n-grams.

Design goals
------------
* Minimal dependencies (pure stdlib), with optional acceleration via
  python-Levenshtein if installed.
* Small, predictable API for easy GUI integration: call once, get a number.

Usage
-----
from stegobench.metrics.text.objective import (
    text_similarity, text_levenshtein, text_jaccard
)

sim = text_similarity("orig.txt", "stego.txt")   # % in [0..100]

lev = text_levenshtein("orig.txt", "stego.txt")  # integer distance

jac = text_jaccard("orig.txt", "stego.txt", level="word")     # % in [0..100]

jac3 = text_jaccard("orig.txt", "stego.txt", level="ngram", n=3)  # 3-gram

Notes
-----
* All functions read files from disk on each call. If you run them repeatedly on
  the same data, consider caching the loaded strings in your application layer.
* Normalization: text_similarity lowercases and collapses whitespace; likewise
  text_jaccard tokenizes with simple rules (see docstring below).
"""

from __future__ import annotations
from difflib import SequenceMatcher

import re
from typing import Literal

__all__ = [
    "text_similarity",
    "text_levenshtein",
    "text_jaccard",
]


try:
    import Levenshtein as _lev  # pip install Levenshtein
    _HAS_LEV = True
except Exception:
    _HAS_LEV = False


# --------------------------
# Internal helper utilities
# --------------------------

def _normalize_spaces_lower(s: str) -> str:
    """Lowercase and collapse consecutive whitespace to a single space."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _tokenize_words(s: str) -> list[str]:
    """
    Tokenize to 'words' using a simple regex for alphanumerics/underscore.
    For more advanced tokenization, replace this with your own tokenizer.
    """
    return re.findall(r"\w+", s.lower(), flags=re.UNICODE)


def _char_ngrams(s: str, n: int) -> list[str]:
    """Return a list of character n-grams for a lowercased string."""
    s = s.lower()
    return [s[i:i+n] for i in range(max(0, len(s) - n + 1))]


# --------------------------
# Public metrics
# --------------------------
def text_similarity(txt_a: str, txt_b: str) -> float:
    """
    Compute the character-level similarity percentage between two text strings.

    This function compares two text inputs (already-loaded strings) using 
    either the Levenshtein ratio (if available) or difflib's SequenceMatcher 
    as a fallback. Before comparison, both texts are normalized by converting 
    to lowercase and collapsing multiple spaces to improve robustness.

    Parameters
    ----------
    txt_a : str
        First text input (already read from file).
    txt_b : str
        Second text input (already read from file).

    Returns
    -------
    float
        Similarity percentage in [0..100]. Higher is more similar.
    
    Example
    -------
    >>> text_similarity("hello world", "hello  world")
    100.0
    """
    a = _normalize_spaces_lower(txt_a)
    b = _normalize_spaces_lower(txt_b)

    if _HAS_LEV:
        ratio = _lev.ratio(a, b)
    else:
        ratio = SequenceMatcher(None, a, b).ratio()

    return float(ratio * 100.0)



def text_levenshtein(txt_a: str, txt_b: str) -> int:
    """
    Compute the Levenshtein distance between two text strings.

    This function compares two preloaded text strings and calculates the minimum
    number of single-character edits (insertions, deletions, or substitutions)
    required to change one string into the other.

    Parameters
    ----------
    txt_a : str
        First text content.
    txt_b : str
        Second text content.

    Returns
    -------
    int
        Levenshtein distance (non-negative integer). Lower is more similar.
    """
    a = _normalize_spaces_lower(txt_a)
    b = _normalize_spaces_lower(txt_b)

    if _HAS_LEV:
        return int(_lev.distance(a, b))

    sm = SequenceMatcher(None, a, b)
    return int((1.0 - sm.ratio()) * max(len(a), len(b)))



def text_jaccard(
    txt_a: str,
    txt_b: str,
    *,
    level: Literal["word", "char", "ngram"] = "word",
    n: int = 3,
) -> float:
    """
    Compute the Jaccard similarity between two text strings.

    The Jaccard similarity is the ratio of the intersection size to the union size
    of token sets. Tokens can be defined by words, characters, or character n-grams.

    Parameters
    ----------
    txt_a : str
        First text content.
    txt_b : str
        Second text content.
    level : {'word', 'char', 'ngram'}, optional
        Tokenization level to compute Jaccard similarity.
    n : int, optional
        Length of character n-grams if level='ngram'.

    Returns
    -------
    float
        Jaccard similarity percentage in [0..100]. Higher is more similar.
    """
    a = txt_a
    b = txt_b

    if level == "word":
        set_a = set(_tokenize_words(a))
        set_b = set(_tokenize_words(b))
    elif level == "char":
        set_a = set(a.lower())
        set_b = set(b.lower())
    elif level == "ngram":
        if n <= 0:
            raise ValueError("n must be a positive integer for n-grams.")
        set_a = set(_char_ngrams(a, n))
        set_b = set(_char_ngrams(b, n))
    else:
        raise ValueError("level must be one of: 'word', 'char', 'ngram'.")

    union = len(set_a | set_b)
    if union == 0:
        return 100.0
    inter = len(set_a & set_b)
    return float(100.0 * inter / union)

