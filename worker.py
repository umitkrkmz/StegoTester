# worker.py
# Contains the MetricWorker class that runs the heavy metric calculations
# on a background thread to keep the UI responsive.

import joblib 
import os
from pathlib import Path
from PySide6.QtCore import QObject, Signal
# Import utils
from utils import (
    group_files_smart, 
    extract_image_features, 
    extract_audio_features, 
    calculate_gatekeeper_score
)

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

# --- GATEKEEPER CONSTANT ---
AUDIO_LSB_THRESHOLD = 0.455

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
        
        # --- Load Models ---
        self.img_model = None
        self.aud_model = None
        self._load_models()
        
    def _load_models(self):
        """The application loads the models once when it starts."""
        try:
            base_path = Path(__file__).parent / "models"
            img_model_path = base_path / "stego_model_image.pkl"
            aud_model_path = base_path / "stego_model_audio.pkl"
            
            if img_model_path.exists():
                self.img_model = joblib.load(img_model_path)
            
            if aud_model_path.exists():
                self.aud_model = joblib.load(aud_model_path)
                
        except Exception as e:
            print(f"Model yükleme hatası: {e}")
            # Even if there's an error, the application won't crash; the AI ​​results will simply return 0.0

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
                if str_gid in self.refs["audio"] and data["stego"]:
                    ref_path = self.refs["audio"][str_gid]
                    cmp_path = data["stego"][0]
                    row["pairs"]["audio"] = (ref_path, cmp_path)
                    
                    # 1. Standart Metrikler
                    if self.metrics["audio"]:
                        for met_name in self.metrics["audio"]:
                            if met_name == "ai_detection": continue # AI'yı ayrı işleyeceğiz
                            
                            key = f"audio_{met_name}"
                            if key in METRIC_REGISTRY:
                                try:
                                    row["metrics"][key] = METRIC_REGISTRY[key](ref_path, cmp_path)
                                except: pass
                        
                        # 2. AI & GATEKEEPER DETECTION
                        if "ai_detection" in self.metrics["audio"]:
                            ai_score = 0.0
                            try:
                                # A) Gatekeeper Check (Matematiksel Kontrol)
                                trans_rate = calculate_gatekeeper_score(cmp_path)
                                if trans_rate > AUDIO_LSB_THRESHOLD:
                                    # LSB çok dağınık, kesin Stego. AI'ya sormaya gerek yok.
                                    ai_score = 1.0 
                                else:
                                    # B) Dedektif Check (AI Model)
                                    if self.aud_model:
                                        features = extract_audio_features(cmp_path)
                                        if features is not None:
                                            # predict_proba -> [[prob_clean, prob_stego]]
                                            ai_score = self.aud_model.predict_proba(features)[0][1]
                            except Exception as e:
                                print(f"Audio AI Error: {e}")
                            
                            row["metrics"]["audio_ai_detection"] = ai_score

                # --- Image Metrics ---
                # Priority: Compare Original vs Stego (common for PSNR/SSIM)
                # If no Stego file, try Original vs Extract (common for payload extraction)
                target_img = None
                if data["stego"]: target_img = data["stego"][0]
                elif data["extract"]: target_img = data["extract"][0]

                if str_gid in self.refs["image"] and target_img:
                    ref_path = self.refs["image"][str_gid]
                    row["pairs"]["image"] = (ref_path, target_img)
                    
                    if self.metrics["image"]:
                        for met_name in self.metrics["image"]:
                            if met_name == "ai_detection": continue
                            
                            key = f"image_{met_name}"
                            if key in METRIC_REGISTRY:
                                try:
                                    row["metrics"][key] = METRIC_REGISTRY[key](ref_path, target_img)
                                except: pass
                        
                        # AI DETECTION (IMAGE)
                        if "ai_detection" in self.metrics["image"]:
                            ai_score = 0.0
                            try:
                                if self.img_model:
                                    features = extract_image_features(target_img)
                                    if features is not None:
                                        ai_score = self.img_model.predict_proba(features)[0][1]
                            except Exception as e:
                                print(f"Image AI Error: {e}")
                            
                            row["metrics"]["image_ai_detection"] = ai_score

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