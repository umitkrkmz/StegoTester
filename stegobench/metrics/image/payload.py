"""
Payload-level metrics for image-based steganography.

This module provides utility functions to compare a known payload
(secret message) with one extracted from an image after decoding.

Included Metrics
----------------
- bitwise_ber: Bit Error Rate between original and extracted payload.
- byte_accuracy: Byte-level match percentage.
- exact_match: Bitwise equality.

Assumptions
-----------
* Payloads are raw bytes or file paths pointing to binary data.
* This module does not extract hidden data — it only compares.
"""

from __future__ import annotations
from typing import Union

__all__ = [
    "bitwise_ber",
    "byte_accuracy",
    "exact_match",
]


def _read_bytes(data: Union[str, bytes]) -> bytes:
    """Read bytes from a file path or return as-is if already bytes."""
    if isinstance(data, str):
        with open(data, "rb") as f:
            return f.read()
    return data


def bitwise_ber(original: Union[str, bytes], extracted: Union[str, bytes]) -> float:
    """
    Compute Bit Error Rate (BER) between original and extracted payload.

    Parameters
    ----------
    original : str or bytes
        Path to original payload file or raw bytes.
    extracted : str or bytes
        Path to extracted payload file or raw bytes.

    Returns
    -------
    float
        BER value in [0, 1]. 0 = perfect match.
    """
    a = _read_bytes(original)
    b = _read_bytes(extracted)
    min_len = min(len(a), len(b))

    if min_len == 0:
        return 1.0 if len(a) != len(b) else 0.0

    a = a[:min_len]
    b = b[:min_len]

    total_bits = min_len * 8
    bit_errors = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    return bit_errors / total_bits


def byte_accuracy(original: Union[str, bytes], extracted: Union[str, bytes]) -> float:
    """
    Compute percentage of correctly matching bytes.

    Parameters
    ----------
    original : str or bytes
        Ground truth payload.
    extracted : str or bytes
        Extracted payload.

    Returns
    -------
    float
        Accuracy in [0, 100]. 100 = perfect match.
    """
    a = _read_bytes(original)
    b = _read_bytes(extracted)
    min_len = min(len(a), len(b))

    if min_len == 0:
        return 100.0 if len(a) == len(b) else 0.0

    a = a[:min_len]
    b = b[:min_len]
    correct = sum(x == y for x, y in zip(a, b))
    return (correct / min_len) * 100.0


def exact_match(original: Union[str, bytes], extracted: Union[str, bytes]) -> bool:
    """
    Check for exact bitwise match between payloads.

    Parameters
    ----------
    original : str or bytes
        Ground truth.
    extracted : str or bytes
        Output from decoder.

    Returns
    -------
    bool
        True if payloads are identical.
    """
    return _read_bytes(original) == _read_bytes(extracted)
