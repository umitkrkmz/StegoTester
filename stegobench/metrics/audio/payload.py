"""
Payload-level accuracy metrics for audio steganography.

This module provides metrics to evaluate how accurately a hidden message
(payload) is extracted from a stego-audio file. It compares the original
(secret) payload with the extracted one.

Included Metrics
----------------
- bitwise_ber: Bit Error Rate between original and extracted payload.
- byte_accuracy: Percentage of correctly extracted bytes.
- exact_match: Whether the payload is exactly recovered.

Assumptions
-----------
* Inputs are either bytes or file paths pointing to binary data.
* All metrics treat data as raw bytes.
"""

from __future__ import annotations
from typing import Union


__all__ = [
    "bitwise_ber",
    "byte_accuracy",
    "exact_match",
]


def _read_bytes(data: Union[str, bytes]) -> bytes:
    """Helper: If input is a filepath, read file as bytes. Otherwise return as-is."""
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
        BER value in [0, 1]. 0 = perfect match, 1 = completely different.
    """
    a = _read_bytes(original)
    b = _read_bytes(extracted)
    min_len = min(len(a), len(b))

    if min_len == 0:
        return 1.0 if len(a) != len(b) else 0.0

    # Truncate to match length
    a = a[:min_len]
    b = b[:min_len]

    total_bits = min_len * 8
    errors = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    return errors / total_bits


def byte_accuracy(original: Union[str, bytes], extracted: Union[str, bytes]) -> float:
    """
    Compute percentage of correctly matched bytes.

    Parameters
    ----------
    original : str or bytes
        Path to original payload file or raw bytes.
    extracted : str or bytes
        Path to extracted payload file or raw bytes.

    Returns
    -------
    float
        Accuracy percentage in [0, 100].
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
    Check if the extracted payload matches the original exactly (bitwise).

    Parameters
    ----------
    original : str or bytes
        Original payload.
    extracted : str or bytes
        Extracted payload.

    Returns
    -------
    bool
        True if payloads are exactly identical.
    """
    return _read_bytes(original) == _read_bytes(extracted)
