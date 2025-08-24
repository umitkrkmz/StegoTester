"""
Objective audio quality metrics for waveform comparison.

This module provides a collection of signal-level metrics that compare
two WAV files — typically a reference signal (e.g., clean or cover audio)
and a test version (e.g., stego, compressed, enhanced, or degraded audio).

Included Metrics
----------------
- Mean Squared Error (MSE)
- Mean Absolute Error (MAE)
- Peak Signal-to-Noise Ratio (PSNR)
- Signal-to-Noise Ratio (SNR)
- Log-Spectral Distance (LSD)

Assumptions
-----------
* Input audio files must be 16-bit PCM WAV format.
* Stereo files are automatically converted to mono by averaging channels.
* Samples are normalized to float32 values in the range [-1.0, 1.0].

Usage
-----
from stegobench.metrics.audio.objective import (
    audio_mse,
    audio_mae,
    audio_psnr,
    audio_snr,
    audio_lsd,
)

mse  = audio_mse("reference.wav", "test.wav")
mae  = audio_mae("reference.wav", "test.wav")
psnr = audio_psnr("reference.wav", "test.wav")   # dB, higher is better
snr  = audio_snr("reference.wav", "test.wav")    # dB, higher is better
lsd  = audio_lsd("reference.wav", "test.wav")    # dB, lower is better

Notes
-----
* Both WAV files must have the **same length** after stereo-to-mono conversion.
  A ValueError is raised otherwise.
* PSNR assumes a peak signal value of 1.0, as audio is normalized.
* LSD compares the log-magnitude STFT spectra between signals.
* For non-16-bit or compressed formats, decode externally
  (e.g., using `librosa` or `soundfile`) and use array-level metrics.
* This module is designed for simplicity, reproducibility, and minimal dependencies.
"""


from __future__ import annotations

import math
import wave
from typing import Tuple
import scipy.signal

import numpy as np

__all__ = [
    "audio_mse",
    "audio_mae", 
    "audio_psnr",
    "audio_snr",
    "audio_lsd",
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
def audio_mse(reference_wav: str, test_wav: str) -> float:
    """
    Mean Squared Error (MSE) between two WAV files.

    Parameters
    ----------
    reference_wav, test_wav : str
        Paths to the reference and test WAV files. Must be 16-bit PCM.

    Returns
    -------
    float
        MSE value (lower is better).

    Raises
    ------
    ValueError
        If sample widths are not 16-bit PCM or lengths do not match.
    """
    a, _ = _read_wav_float32_mono(reference_wav)
    b, _ = _read_wav_float32_mono(test_wav)
    _ensure_same_length(a, b)
    return _mse(a, b)


def audio_mae(reference_wav: str, test_wav: str) -> float:
    """
    Mean Absolute Error (MAE) between two WAV files.

    Parameters
    ----------
    reference_wav, test_wav : str
        Paths to the reference and test WAV files. Must be 16-bit PCM.

    Returns
    -------
    float
        MAE value (lower is better).

    Raises
    ------
    ValueError
        If sample widths are not 16-bit PCM or lengths do not match.
    """
    a, _ = _read_wav_float32_mono(reference_wav)
    b, _ = _read_wav_float32_mono(test_wav)
    _ensure_same_length(a, b)
    return float(np.mean(np.abs(a - b)))


def audio_psnr(reference_wav: str, test_wav: str) -> float:
    """
    Peak Signal-to-Noise Ratio (PSNR) in dB for two WAV files.

    Parameters
    ----------
    reference_wav, test_wav : str
        Paths to the reference and test WAV files. Must be 16-bit PCM.

    Returns
    -------
    float
        PSNR in dB (higher is better), with peak=1.0 due to normalization.
    """
    mse = audio_mse(reference_wav, test_wav)
    return _psnr_from_mse(mse, peak=1.0)


def audio_snr(reference_wav: str, test_wav: str) -> float:
    """
    Signal-to-Noise Ratio (SNR) in dB for two WAV files.

    SNR is computed as 10*log10(P_signal / P_noise), where:
      P_signal = mean(reference^2), P_noise = mean((test - reference)^2)

    Parameters
    ----------
    reference_wav, test_wav : str
        Paths to the reference and test WAV files. Must be 16-bit PCM.

    Returns
    -------
    float
        SNR in dB (higher is better).

    Raises
    ------
    ValueError
        If sample widths are not 16-bit PCM or lengths do not match.
    """
    a, _ = _read_wav_float32_mono(reference_wav)
    b, _ = _read_wav_float32_mono(test_wav)
    _ensure_same_length(a, b)

    noise = b - a
    p_signal = float(np.mean(a ** 2) + 1e-12)
    p_noise  = float(np.mean(noise ** 2) + 1e-12)
    return 10.0 * math.log10(p_signal / p_noise)


def audio_lsd(reference_wav: str, test_wav: str, frame_size: int = 512, hop_size: int = 256) -> float:
    """
    Log-Spectral Distance (LSD) between two WAV files.

    LSD measures frame-wise spectral distortion in dB.

    Parameters
    ----------
    reference_wav, test_wav : str
        Paths to the reference and test WAV files. Must be 16-bit PCM.
    frame_size : int, optional
        STFT window size in samples (default: 512).
    hop_size : int, optional
        STFT hop length in samples (default: 256).

    Returns
    -------
    float
        Average LSD across frames (lower is better).
    """

    a, _ = _read_wav_float32_mono(reference_wav)
    b, _ = _read_wav_float32_mono(test_wav)
    _ensure_same_length(a, b)

    def stft_log_mag(signal: np.ndarray) -> np.ndarray:
        _, _, Zxx = scipy.signal.stft(signal, nperseg=frame_size, noverlap=frame_size - hop_size)
        return 20 * np.log10(np.abs(Zxx) + 1e-12)

    log_a = stft_log_mag(a)
    log_b = stft_log_mag(b)

    return float(np.mean(np.sqrt(np.mean((log_a - log_b) ** 2, axis=0))))