# worker.py
# Contains the MetricWorker class that runs the heavy metric calculations
# on a background thread to keep the UI responsive.

from pathlib import Path
from PySide6.QtCore import QObject, Signal
from utils import group_files_smart, calculate_image_stego_prob, calculate_audio_stego_prob # Utility functions

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
    
    "audio_ai_detection": calculate_audio_stego_prob, # AI-based stego detection

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
    
    "image_ai_detection": calculate_image_stego_prob, # AI-based stego detection

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
        """Calculates metrics based on ID matching from group_files_smart."""
        try:
            data_rows = []
            
            total_groups = len(self.groups)
            if total_groups == 0:
                self.progress.emit(100)
                self.finished.emit([])
                return

            # gid is the Integer ID assigned in utils.py
            for i, (gid, data) in enumerate(sorted(self.groups.items())):
                row = {"id": gid, "metrics": {}, "pairs": {}}
                
                # utils.py stores refs with STRING keys ("1", "2"), but groups use INT keys.
                # We convert gid to string to look up the reference file.
                str_gid = str(gid)

                # --- Audio Metrics ---
                # Checks if we have an original audio reference and a candidate stego file
                if self.metrics["audio"] and str_gid in self.refs["audio"] and data["stego"]:
                    ref_path = self.refs["audio"][str_gid]
                    cmp_path = data["stego"][0] # Take the first match
                    
                    row["pairs"]["audio"] = (ref_path, cmp_path)
                    
                    for met_name in self.metrics["audio"]:
                        metric_key = f"audio_{met_name}"
                        if metric_key in METRIC_REGISTRY:
                            try:
                                metric_func = METRIC_REGISTRY[metric_key]
                                row["metrics"][metric_key] = metric_func(ref_path, cmp_path)
                            except Exception as e:
                                print(f"Error calculating {metric_key}: {e}")

                # --- Image Metrics ---
                # Priority: Compare Original vs Stego (common for PSNR/SSIM)
                # If no Stego file, try Original vs Extract (common for payload extraction)
                target_img = None
                if data["stego"]: target_img = data["stego"][0]
                elif data["extract"]: target_img = data["extract"][0]

                if self.metrics["image"] and str_gid in self.refs["image"] and target_img:
                    ref_path = self.refs["image"][str_gid]
                    row["pairs"]["image"] = (ref_path, target_img)
                    
                    for met_name in self.metrics["image"]:
                        metric_key = f"image_{met_name}"
                        if metric_key in METRIC_REGISTRY:
                            try:
                                metric_func = METRIC_REGISTRY[metric_key]
                                row["metrics"][metric_key] = metric_func(ref_path, target_img)
                            except Exception as e:
                                print(f"Error calculating {metric_key}: {e}")

                # --- Text Metrics ---
                target_text = None
                if data["stego"]: target_text = data["stego"][0]
                elif data["extract"]: target_text = data["extract"][0]
                
                if self.metrics["text"] and str_gid in self.refs["text"] and target_text:
                    ref_path = self.refs["text"][str_gid]
                    row["pairs"]["text"] = (ref_path, target_text)
                    for met_name in self.metrics["text"]:
                        metric_key = f"text_{met_name}"
                        if metric_key in METRIC_REGISTRY:
                            try:
                                metric_func = METRIC_REGISTRY[metric_key]
                                row["metrics"][metric_key] = metric_func(ref_path, target_text)
                            except Exception as e:
                                print(f"Error calculating {metric_key}: {e}")
                
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