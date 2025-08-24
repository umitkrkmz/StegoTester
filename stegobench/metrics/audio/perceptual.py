"""
Perceptual audio quality metrics.

This module implements metrics that aim to reflect how a human listener
might perceive differences between two WAV signals — typically a cover and a stego version.

Included Metrics
----------------
- dummy: 1 - MSE (as a naive perceptual proxy)
- PESQ: Perceptual Evaluation of Speech Quality (ITU-T P.862)
- STOI: Short-Time Objective Intelligibility

Assumptions
-----------
* Inputs are 16-bit PCM WAV files.
* Stereo signals are averaged to mono.
* Samples are normalized to float32 in [-1.0, 1.0].

Dependencies
------------
* PESQ: pip install pesq
* STOI: pip install pystoi
"""

from typing import Literal
import numpy as np
from .objective import _read_wav_float32_mono, _ensure_same_length

# Optional imports
try:
    from pesq import pesq
    _HAS_PESQ = True
except ImportError:
    _HAS_PESQ = False

try:
    from pystoi import stoi
    _HAS_STOI = True
except ImportError:
    _HAS_STOI = False


__all__ = ["perceptual_score"]


def perceptual_score(
    reference_wav: str,
    test_wav: str,
    method: Literal["dummy", "pesq", "stoi"] = "dummy",
    fs: int = 16000,
) -> float:
    """
    Compute a perceptual similarity score between two audio files.

    Parameters
    ----------
    reference_wav : str
        Path to the reference WAV file (e.g., cover or clean signal).
    test_wav : str
        Path to the test WAV file (e.g., stego or degraded signal).
    method : str
        Perceptual method to use: 'dummy', 'pesq', or 'stoi'.
    fs : int, default 16000
        Sampling rate for PESQ/STOI. Must be 8000 or 16000 for PESQ.

    Returns
    -------
    float
        Perceptual score. Range and interpretation depend on method:
        - dummy: [0..1] (1 is best)
        - pesq: 1.0–4.5 (4.5 is best)
        - stoi: 0.0–1.0 (1 is best)

    Raises
    ------
    ImportError
        If required method library is not available.
    ValueError
        If method or sampling rate is unsupported.
    """
    a, sr = _read_wav_float32_mono(reference_wav)
    b, _ = _read_wav_float32_mono(test_wav)
    _ensure_same_length(a, b)

    if method == "dummy":
        mse = np.mean((a - b) ** 2)
        return float(1.0 - min(mse, 1.0))  # [0,1] scale, higher = better

    elif method == "pesq":
        if not _HAS_PESQ:
            raise ImportError("PESQ method requires `pesq` package. Install with: pip install pesq")
        if fs not in (8000, 16000):
            raise ValueError("PESQ supports only fs=8000 or fs=16000.")
        return pesq(fs, a, b, 'wb' if fs == 16000 else 'nb')

    elif method == "stoi":
        if not _HAS_STOI:
            raise ImportError("STOI method requires `pystoi`. Install with: pip install pystoi")
        return stoi(a, b, fs, extended=False)

    else:
        raise ValueError(f"Unknown method '{method}'. Choose from 'dummy', 'pesq', 'stoi'.")
