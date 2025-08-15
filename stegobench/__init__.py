# stegobench\__init__.py
"""
StegoBench: A modular benchmarking toolkit for steganography.

This package provides unified access to various modality-specific metrics
(audio, image, text) used in evaluating steganographic systems.
"""

from . import metrics

__all__ = ["metrics"]
