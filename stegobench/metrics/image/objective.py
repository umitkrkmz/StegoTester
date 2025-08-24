"""
Objective image quality metrics for steganography analysis.

This module provides basic, dependency-light image quality metrics that operate
on file paths. Metrics are designed to detect perceptual and bit-level
differences between two images — typically a cover and a stego version.

Included Metrics
----------------
- Mean Squared Error (MSE)
- Peak Signal-to-Noise Ratio (PSNR)
- Structural Similarity Index (SSIM)     [optional, requires scikit-image]
- Bit Error Rate over bit-planes (BER)   [for LSB-based analysis]

Usage
-----
from stegobench.metrics.image.objective import (
    image_mse,
    image_psnr,
    image_ssim,
    image_ber,
)

psnr_val = image_psnr("orig.png", "stego.png")
ssim_val = image_ssim("orig.png", "stego.png")               # grayscale SSIM
ssim_rgb = image_ssim("orig.png", "stego.png", use_color=True)  # RGB SSIM
ber_val  = image_ber("orig.png", "stego.png", bitplane=0, channel="all")
mse_val  = image_mse("orig.png", "stego.png")

Notes
-----
* All image files are read from disk each call. Cache arrays if performance matters.
* MSE/PSNR operate in RGB float32 space, assuming [0..255] range.
* SSIM defaults to greyscale. For color SSIM, pass `use_color=True` (requires scikit-image).
* BER is useful for LSB-based stego methods; `bitplane=0` targets the LSB.
"""


from __future__ import annotations

import math
from typing import Literal

import numpy as np
from PIL import Image

# Optional import: scikit-image is a heavy dependency, only needed for SSIM.
try:
    from skimage.metrics import structural_similarity as _ssim
    _HAS_SSIM = True
except Exception:
    _HAS_SSIM = False


__all__ = [
    "image_mse",
    "image_psnr",
    "image_ssim",
    "image_ber",
]


# --------------------------
# Internal helper utilities
# --------------------------
def _mse(a: np.ndarray, b: np.ndarray) -> float:
    """Return the mean squared error between two float32 arrays."""
    return float(np.mean((a - b) ** 2))


def _psnr_from_mse(mse: float, peak: float) -> float:
    """
    Compute PSNR (dB) from MSE and the peak value.
    For 8-bit images in float space, use peak=255.0.
    """
    if mse <= 0.0:
        # Identical images -> infinite PSNR by definition.
        return float("inf")
    return 10.0 * math.log10((peak ** 2) / mse)


def _read_rgb(path: str) -> np.ndarray:
    """
    Load an image file as RGB and return a float32 array in [0..255] range.
    Raises PIL.UnidentifiedImageError if the file is not a valid image.
    """
    return np.array(Image.open(path).convert("RGB"), dtype=np.float32)


# --------------------------
# Public metrics
# --------------------------
def image_mse(img_a: str, img_b: str) -> float:
    """
    Mean Squared Error (MSE) between two images in RGB space.

    Parameters
    ----------
    img_a, img_b : str
        Paths to the two images. They must have the same dimensions.

    Returns
    -------
    float
        MSE value (lower is better). Computed over RGB channels.

    Raises
    ------
    ValueError
        If image sizes (H, W, C) do not match.
    """
    a = _read_rgb(img_a)
    b = _read_rgb(img_b)
    if a.shape != b.shape:
        raise ValueError("Image dimensions do not match.")
    return _mse(a, b)


def image_psnr(img_a: str, img_b: str) -> float:
    """
    Peak Signal-to-Noise Ratio (PSNR) in dB.

    Parameters
    ----------
    img_a, img_b : str
        Paths to the two images. They must have the same dimensions.

    Returns
    -------
    float
        PSNR in dB (higher is better). Uses peak=255 for 8-bit-like RGB arrays.
    """
    return _psnr_from_mse(image_mse(img_a, img_b), peak=255.0)


def image_ssim(img_a: str, img_b: str, *, use_color: bool = False) -> float:
    """
    Structural Similarity (SSIM) index in [0..1].

    Parameters
    ----------
    img_a, img_b : str
        Paths to the two images. They must have the same dimensions.
    use_color : bool, default False
        If False (default), compute SSIM on greyscale.
        If True, compute SSIM on RGB. Requires scikit-image.

    Returns
    -------
    float
        SSIM value in [0..1] (higher is better).

    Raises
    ------
    RuntimeError
        If scikit-image is not installed.
    ValueError
        If image sizes do not match.
    """
    if not _HAS_SSIM:
        raise RuntimeError(
            "SSIM requires scikit-image. Install via: 'pip install scikit-image'"
        )

    # --- Load as float32, matching the module's conventions ---
    if use_color:
        a = np.array(Image.open(img_a).convert("RGB"), dtype=np.float32)
        b = np.array(Image.open(img_b).convert("RGB"), dtype=np.float32)
        channel_axis = 2  # skimage >= 0.19
    else:
        a = np.array(Image.open(img_a).convert("L"), dtype=np.float32)
        b = np.array(Image.open(img_b).convert("L"), dtype=np.float32)
        channel_axis = None

    if a.shape != b.shape:
        raise ValueError("Image dimensions do not match.")

    # --- Fast path: identical arrays should have SSIM=1.0 ---
    if np.array_equal(a, b):
        return 1.0

    # --- Safe data_range: use joint range; if degenerate, fall back to 255.0 ---
    joint_min = min(float(a.min()), float(b.min()))
    joint_max = max(float(a.max()), float(b.max()))
    data_range = joint_max - joint_min
    if data_range <= 0.0 or not np.isfinite(data_range):
        data_range = 255.0  # 8-bit-like safe default in this module

    # --- Constant-image handling: if both constant but different, return 0.0 ---
    def _is_constant(x: np.ndarray) -> bool:
        # For float32, this equality check is fine as we compared raw loads.
        return bool(np.all(x == x.flat[0]))

    if _is_constant(a) and _is_constant(b):
        # They are not equal (handled above), so treat as maximally dissimilar
        # under SSIM's structure/contrast terms.
        return 0.0

    # --- Compute SSIM with compatibility for old/new scikit-image APIs ---
    try:
        val = float(_ssim(a, b, data_range=data_range, channel_axis=channel_axis))
    except TypeError:
        # Legacy API (pre-0.19): 'multichannel' instead of 'channel_axis'
        if channel_axis is None:
            val = float(_ssim(a, b, data_range=data_range))
        else:
            val = float(_ssim(a, b, data_range=data_range, multichannel=True))

    # --- Guard against inf/nan from pathological cases ---
    if math.isinf(val) or np.isnan(val):
        val = 0.0

    # --- Clamp tiny numeric overshoots/undershoots to [0, 1] ---
    if val < 0.0:
        val = 0.0
    elif val > 1.0:
        val = 1.0

    return val

def image_ber(
    img_a: str,
    img_b: str,
    *,
    bitplane: int = 0,
    channel: Literal["R", "G", "B", "all"] = "all",
) -> float:
    """
    Bit Error Rate (BER) over a selected bit-plane, optionally per channel.

    This is especially useful for LSB-based steganography. It extracts the
    specified bit-plane (e.g., LSB with bitplane=0) from both images and
    computes the fraction of differing bits.

    Parameters
    ----------
    img_a, img_b : str
        Paths to the two images. Must have the same dimensions.
    bitplane : int, default 0
        Bit-plane index in [0..7]. 0 = LSB.
    channel : {"R","G","B","all"}, default "all"
        If "all": compute over all RGB channels combined.
        If "R"/"G"/"B": restrict to a single channel.

    Returns
    -------
    float
        BER in [0..1]. 0 means no bit differences; 1 means all bits differ.

    Raises
    ------
    ValueError
        If bitplane is out of range or image sizes do not match.
    """
    if not (0 <= bitplane <= 7):
        raise ValueError("bitplane must be in the range [0..7].")

    A = np.array(Image.open(img_a).convert("RGB"), dtype=np.uint8)
    B = np.array(Image.open(img_b).convert("RGB"), dtype=np.uint8)
    if A.shape != B.shape:
        raise ValueError("Image dimensions do not match.")

    if channel in {"R", "G", "B"}:
        idx = {"R": 0, "G": 1, "B": 2}[channel]
        A = A[..., idx]
        B = B[..., idx]

    # Isolate the chosen bit-plane and compute XOR differences
    mask = np.uint8(1 << bitplane)
    bits_a = (A & mask) >> bitplane
    bits_b = (B & mask) >> bitplane
    diff = (bits_a ^ bits_b).astype(np.uint8)

    total = diff.size or 1
    errors = int(np.count_nonzero(diff))
    return errors / float(total)
