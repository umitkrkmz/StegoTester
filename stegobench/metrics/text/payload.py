"""
Payload-level comparison for text-based steganography.

This module provides metrics for evaluating how accurately
the hidden text message (payload) is extracted.

Included Metrics
----------------
- exact_match: Whether the entire text matches.
- char_accuracy: Percentage of matching characters.
- bitwise_ber: Bit Error Rate over the underlying bytes.

Assumptions
-----------
* Input can be a path to .txt file or a text string.
* Comparisons are case-sensitive unless normalized beforehand.
"""

from typing import Union
from pathlib import Path

__all__ = [
    "exact_match",
    "char_accuracy",
    "bitwise_ber",
]


def _read_text(data: Union[str, Path]) -> str:
    """Helper: if input is a file path, read it as UTF-8. Otherwise return as-is."""
    if isinstance(data, (str, Path)) and Path(data).is_file():
        return Path(data).read_text(encoding="utf-8", errors="ignore")
    return str(data)


def exact_match(original: Union[str, Path], extracted: Union[str, Path]) -> bool:
    """
    Check if extracted text is exactly equal to the original.

    Returns
    -------
    bool
        True if exact match, False otherwise.
    """
    return _read_text(original) == _read_text(extracted)


def char_accuracy(original: Union[str, Path], extracted: Union[str, Path]) -> float:
    """
    Percentage of matching characters (position-wise).

    Returns
    -------
    float
        Accuracy in [0,100].
    """
    a = _read_text(original)
    b = _read_text(extracted)
    min_len = min(len(a), len(b))
    if min_len == 0:
        return 100.0 if len(a) == len(b) else 0.0
    correct = sum(x == y for x, y in zip(a[:min_len], b[:min_len]))
    return (correct / min_len) * 100.0


def bitwise_ber(original: Union[str, Path], extracted: Union[str, Path]) -> float:
    """
    Bit Error Rate (BER) over UTF-8 encoded bytes.

    Returns
    -------
    float
        BER value in [0,1]. 0 = perfect match.
    """
    a = _read_text(original).encode("utf-8", errors="ignore")
    b = _read_text(extracted).encode("utf-8", errors="ignore")
    min_len = min(len(a), len(b))
    if min_len == 0:
        return 1.0 if len(a) != len(b) else 0.0
    a = a[:min_len]
    b = b[:min_len]
    total_bits = min_len * 8
    bit_errors = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    return bit_errors / total_bits
