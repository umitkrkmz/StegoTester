"""
Audio quality/stego metrics for StegoBench.

This module provides simple metrics that operate directly on WAV file paths:
- Mean Squared Error (MSE)
- Peak Signal-to-Noise Ratio (PSNR)
- Signal-to-Noise Ratio (SNR)

Assumptions
-----------
* Input audio files are 16-bit PCM WAV.
* Stereo files are averaged to mono.
* Samples are normalized to float32 in [-1, 1].

Usage
-----
from stegobench.metrics import audio_mse, audio_psnr, audio_snr

mse  = audio_mse("orig.wav", "stego.wav")
psnr = audio_psnr("orig.wav", "stego.wav")   # dB, higher is better
snr  = audio_snr("orig.wav", "stego.wav")    # dB, higher is better

Notes
-----
* Both WAV files must have the **same length** (after stereo→mono conversion).
  A ValueError is raised otherwise.
* PSNR in this module assumes a peak value of 1.0 (because audio is normalized
  to [-1, 1]). If you prefer a different convention, adapt `_psnr_from_mse`.
* For non‑16‑bit or compressed formats, consider decoding externally (e.g., librosa,
  soundfile) and then computing metrics on arrays—this module aims to have minimal
  dependencies and predictable behavior.
"""

from __future__ import annotations

import math
import wave
from typing import Tuple

import numpy as np

__all__ = [
    "audio_mse",
    "audio_psnr",
    "audio_snr",
]


# --------------------------
# Internal helper utilities
# --------------------------
def _read_wav_float32_mono(path: str) -> Tuple[np.ndarray, int]:
    """
    Read a 16-bit PCM WAV file and return (mono_signal, sample_rate).

    * Stereo signals are averaged to mono.
    * Output samples are float32 normalized to [-1, 1].

    Raises
    ------
    ValueError
        If the WAV is not 16-bit PCM.
    """
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth  = wf.getsampwidth()
        samplerate = wf.getframerate()
        n_frames   = wf.getnframes()

        if sampwidth != 2:
            raise ValueError("Only 16-bit PCM WAV is supported in this function.")

        frames = wf.readframes(n_frames)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32)

    if n_channels == 2:
        data = data.reshape(-1, 2).mean(axis=1)

    # Normalize to [-1, 1]
    data /= 32767.0
    return data, samplerate


def _ensure_same_length(a: np.ndarray, b: np.ndarray):
    """
    Ensure two 1-D arrays have the same length; raise otherwise.
    """
    if a.shape != b.shape:
        raise ValueError("Audio lengths do not match.")


def _mse(a: np.ndarray, b: np.ndarray) -> float:
    """Mean squared error between two float32 arrays."""
    return float(np.mean((a - b) ** 2))


def _psnr_from_mse(mse: float, peak: float = 1.0) -> float:
    """
    Compute PSNR (dB) given MSE and peak value.

    For normalized audio in [-1, 1], use peak=1.0 (default).
    """
    if mse <= 0.0:
        # Identical signals -> infinite PSNR by definition.
        return float("inf")
    return 10.0 * math.log10((peak ** 2) / mse)


# --------------------------
# Public metrics
# --------------------------
def audio_mse(orig_wav: str, stego_wav: str) -> float:
    """
    Mean Squared Error (MSE) between two WAV files.

    Parameters
    ----------
    orig_wav, stego_wav : str
        Paths to the original and stego WAVs. Must be 16-bit PCM.

    Returns
    -------
    float
        MSE value (lower is better).

    Raises
    ------
    ValueError
        If sample widths are not 16-bit PCM or lengths do not match.
    """
    a, _ = _read_wav_float32_mono(orig_wav)
    b, _ = _read_wav_float32_mono(stego_wav)
    _ensure_same_length(a, b)
    return _mse(a, b)


def audio_psnr(orig_wav: str, stego_wav: str) -> float:
    """
    Peak Signal-to-Noise Ratio (PSNR) in dB for two WAV files.

    Parameters
    ----------
    orig_wav, stego_wav : str
        Paths to the original and stego WAVs. Must be 16-bit PCM.

    Returns
    -------
    float
        PSNR in dB (higher is better), with peak=1.0 due to normalization.
    """
    mse = audio_mse(orig_wav, stego_wav)
    return _psnr_from_mse(mse, peak=1.0)


def audio_snr(orig_wav: str, stego_wav: str) -> float:
    """
    Signal-to-Noise Ratio (SNR) in dB for two WAV files.

    SNR is computed as 10*log10(P_signal / P_noise), where:
      P_signal = mean(orig^2), P_noise = mean((stego - orig)^2)

    Parameters
    ----------
    orig_wav, stego_wav : str
        Paths to the original and stego WAVs. Must be 16-bit PCM.

    Returns
    -------
    float
        SNR in dB (higher is better).

    Raises
    ------
    ValueError
        If sample widths are not 16-bit PCM or lengths do not match.
    """
    a, _ = _read_wav_float32_mono(orig_wav)
    b, _ = _read_wav_float32_mono(stego_wav)
    _ensure_same_length(a, b)

    noise = b - a
    p_signal = float(np.mean(a ** 2) + 1e-12)
    p_noise  = float(np.mean(noise ** 2) + 1e-12)
    return 10.0 * math.log10(p_signal / p_noise)
