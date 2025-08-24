"""
Perceptual image quality metrics for steganography evaluation.

This module includes perceptual similarity metrics that aim to reflect
human visual perception when comparing stego and cover images.

Included Metrics
----------------
- SSIM (greyscale or RGB)
- DSSIM (1 - SSIM)
- LPIPS (deep perceptual similarity, optional)

Assumptions
-----------
* Images are read as RGB and compared in float32 format [0..255] or [0..1].
* SSIM requires `scikit-image`.
* LPIPS requires `lpips`, `torch`, and `torchvision`.
"""

from typing import Literal
import numpy as np
from PIL import Image

# Optional imports
try:
    from skimage.metrics import structural_similarity as _ssim
    _HAS_SSIM = True
except ImportError:
    _HAS_SSIM = False

try:
    import torch
    import lpips
    _HAS_LPIPS = True
except ImportError:
    _HAS_LPIPS = False


__all__ = ["image_ssim", "image_dssim", "image_lpips"]


def _read_rgb(path: str) -> np.ndarray:
    """Read image as float32 RGB array with shape (H, W, 3) in [0,255]."""
    return np.array(Image.open(path).convert("RGB"), dtype=np.float32)


def image_ssim(img_a: str, img_b: str, *, use_color: bool = False) -> float:
    """
    Compute SSIM (Structural Similarity Index) between two images.

    Parameters
    ----------
    img_a, img_b : str
        Paths to input images.
    use_color : bool
        Whether to compute SSIM over RGB instead of greyscale.

    Returns
    -------
    float
        SSIM in [0,1]. Higher is better.

    Raises
    ------
    RuntimeError
        If scikit-image is not installed.
    """
    if not _HAS_SSIM:
        raise RuntimeError("SSIM requires `scikit-image`. Install via: pip install scikit-image")

    if use_color:
        a = _read_rgb(img_a)
        b = _read_rgb(img_b)
        if a.shape != b.shape:
            raise ValueError("Image sizes do not match.")
        try:
            return float(_ssim(a, b, data_range=255, channel_axis=2))
        except TypeError:
            return float(_ssim(a, b, data_range=255, multichannel=True))
    else:
        a = np.array(Image.open(img_a).convert("L"), dtype=np.float32)
        b = np.array(Image.open(img_b).convert("L"), dtype=np.float32)
        if a.shape != b.shape:
            raise ValueError("Image sizes do not match.")
        return float(_ssim(a, b, data_range=255))


def image_dssim(img_a: str, img_b: str, *, use_color: bool = False) -> float:
    """
    Compute DSSIM = 1 - SSIM.

    Returns
    -------
    float
        DSSIM value in [0,1]. Lower is better.
    """
    return 1.0 - image_ssim(img_a, img_b, use_color=use_color)


def image_lpips(img_a: str, img_b: str, net: Literal["alex", "vgg"] = "vgg") -> float:
    """
    Compute LPIPS (Learned Perceptual Image Patch Similarity).

    Parameters
    ----------
    img_a, img_b : str
        Paths to images.
    net : {'alex', 'vgg'}
        Backbone network to use (LPIPS supports alexnet and VGG).

    Returns
    -------
    float
        LPIPS distance. Lower is better.

    Raises
    ------
    RuntimeError
        If lpips or torch is not installed.
    """
    if not _HAS_LPIPS:
        raise RuntimeError("LPIPS requires `lpips` and `torch`. Install via: pip install lpips torch torchvision")

    img1 = _read_rgb(img_a) / 255.0  # [0,1]
    img2 = _read_rgb(img_b) / 255.0

    # Convert to torch tensors
    t1 = torch.tensor(img1).permute(2, 0, 1).unsqueeze(0).float()
    t2 = torch.tensor(img2).permute(2, 0, 1).unsqueeze(0).float()

    loss_fn = lpips.LPIPS(net=net)
    dist = loss_fn(t1, t2)
    return float(dist.item())
