# worker.py
# Contains the MetricWorker class that runs the heavy metric calculations
# on a background thread to keep the UI responsive.

from pathlib import Path
from PySide6.QtCore import QObject, Signal

# Import the helper function from our new utils module
from utils import group_files

# Import reporting functions
import reporting

# --- StegoBench Imports ---
# Audio
from stegobench.metrics.audio.objective import (
    audio_mse, audio_psnr, audio_snr, audio_mae, audio_lsd
)
from stegobench.metrics.audio.perceptual import perceptual_score as audio_perceptual_score
from stegobench.metrics.audio.payload import (
    bitwise_ber as audio_bitwise_ber,
    byte_accuracy as audio_byte_accuracy,
    exact_match as audio_exact_match,
)

# Image
from stegobench.metrics.image.objective import (
    image_mse, image_psnr, image_ssim, image_ber
)
from stegobench.metrics.image.perceptual import (
    image_dssim, image_lpips
)
from stegobench.metrics.image.payload import (
    bitwise_ber as image_bitwise_ber,
    byte_accuracy as image_byte_accuracy,
    exact_match as image_exact_match,
)

# Text
from stegobench.metrics.text.objective import (
    text_similarity, text_levenshtein, text_jaccard
)
from stegobench.metrics.text.payload import (
    exact_match as text_exact_match,
    char_accuracy,
    bitwise_ber as text_bitwise_ber,
)


# ---------------- Metric Registry ----------------
# Maps metric names (strings) to their actual function objects.
METRIC_REGISTRY = {
    # Audio Metrics
    "audio_mse": audio_mse,
    "audio_psnr": audio_psnr,
    "audio_snr": audio_snr,
    "audio_mae": audio_mae,
    "audio_lsd": audio_lsd,
    "audio_perceptual_score": audio_perceptual_score,
    "audio_bitwise_ber": audio_bitwise_ber,
    "audio_byte_accuracy": audio_byte_accuracy,
    "audio_exact_match": audio_exact_match,

    # Image Metrics
    "image_mse": image_mse,
    "image_psnr": image_psnr,
    "image_ssim": image_ssim,
    "image_ber": image_ber,
    "image_dssim": image_dssim,
    "image_lpips": image_lpips,
    "image_bitwise_ber": image_bitwise_ber,
    "image_byte_accuracy": image_byte_accuracy,
    "image_exact_match": image_exact_match,

    # Text Metrics
    "text_similarity": text_similarity,
    "text_levenshtein": text_levenshtein,
    "text_jaccard": text_jaccard,
    "text_exact_match": text_exact_match,
    "text_char_accuracy": char_accuracy,
    "text_bitwise_ber": text_bitwise_ber,
}



# ---------------- Metric Worker ----------------
class MetricWorker(QObject):
    finished = Signal(list)
    progress = Signal(int)
    error = Signal(str)

    def __init__(self, refs, groups, metrics):
        super().__init__()
        self.refs = refs
        self.groups = groups
        self.metrics = metrics

    def run(self):
        """Calculates metrics on pre-grouped data using a dynamic registry."""
        try:
            data_rows = []
            
            total_groups = len(self.groups)
            if total_groups == 0:
                self.progress.emit(100)
                self.finished.emit([])
                return

            for i, (gid, data) in enumerate(sorted(self.groups.items())):
                row = {"id": gid, "metrics": {}, "pairs": {}}
                
                # --- Audio Metrics Calculation (Refactored) ---
                if self.metrics["audio"] and self.refs["audio"] and data["stego"]:
                    ref_path, cmp_path = None, data["stego"][0]
                    for key, path in self.refs["audio"].items():
                        if key in Path(cmp_path).name:
                            ref_path = path
                            break
                    if ref_path:
                        row["pairs"]["audio"] = (ref_path, cmp_path)
                        for met_name in self.metrics["audio"]:
                            metric_key = f"audio_{met_name}"
                            if metric_key in METRIC_REGISTRY:
                                metric_func = METRIC_REGISTRY[metric_key]
                                row["metrics"][metric_key] = metric_func(ref_path, cmp_path)

                # --- Image Metrics Calculation (Refactored) ---
                if self.metrics["image"] and self.refs["image"] and data["extract"]:
                    ref_path, cmp_path = None, data["extract"][0]
                    for key, path in self.refs["image"].items():
                        if key in Path(cmp_path).name:
                            ref_path = path
                            break
                    if ref_path:
                        row["pairs"]["image"] = (ref_path, cmp_path)
                        for met_name in self.metrics["image"]:
                            metric_key = f"image_{met_name}"
                            if metric_key in METRIC_REGISTRY:
                                metric_func = METRIC_REGISTRY[metric_key]
                                row["metrics"][metric_key] = metric_func(ref_path, cmp_path)

                # --- Text Metrics Calculation (Refactored) ---
                if self.metrics["audio"] and self.refs["audio"] and data["stego"]:
                    ref_path, cmp_path = None, data["stego"][0]
                    for key, path in self.refs["audio"].items():
                        if key in Path(cmp_path).name.lower():
                            ref_path = path
                            break
                    if ref_path:
                        row["pairs"]["audio"] = (ref_path, cmp_path)
                        for met_name in self.metrics["audio"]:
                            metric_key = f"audio_{met_name}"
                            if metric_key in METRIC_REGISTRY:
                                metric_func = METRIC_REGISTRY[metric_key]
                                row["metrics"][metric_key] = metric_func(ref_path, cmp_path)
                
                data_rows.append(row)
                progress_percent = int(((i + 1) / total_groups) * 100)
                self.progress.emit(progress_percent)

            self.finished.emit(data_rows)

        except Exception as e:
            self.error.emit(str(e))
            
            
# ---------------- Report Worker ----------------
class ReportWorker(QObject):
    finished = Signal(str)  # When the job is finished, it returns the file path
    error = Signal(str)     # If an error occurs, it returns an error message.

    def __init__(self, data_rows, path, timestamp):
        super().__init__()
        self.data_rows = data_rows
        self.path = path
        self.timestamp = timestamp

    def run(self):
        """Generates the report in the background."""
        try:
            # Select the correct reporting function based on the file extension
            if self.path.endswith('.pdf'):
                reporting.save_pdf_table(self.data_rows, self.path, self.timestamp)
            elif self.path.endswith('.txt'):
                reporting.save_txt_table(self.data_rows, self.path, self.timestamp)
            elif self.path.endswith('.json'):
                reporting.save_json_table(self.data_rows, self.path, self.timestamp)
            elif self.path.endswith('.csv'):
                reporting.save_csv_table(self.data_rows, self.path, self.timestamp)
            else:
                raise ValueError("Unsupported file extension selected.")
            
            self.finished.emit(self.path)
        except Exception as e:
            self.error.emit(str(e))