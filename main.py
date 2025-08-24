import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import matplotlib.pyplot as plt
from fpdf import FPDF

# ---------- StegoBench imports ----------
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

# ---------- Qt ----------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsOpacityEffect,
    QFileDialog, QMessageBox, QTableWidgetItem,
)

from ui_form import Ui_MainWindow

# ---------------- Constants ----------------
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
AUD_EXT = {".wav"}
TXT_EXT = {".txt", ".bin"}


def fmt_val(v) -> str:
    """Formats numbers nicely for reporting."""
    try:
        if v == float("inf"):
            return "inf"
    except Exception:
        pass
    if isinstance(v, int):
        return str(v)
    try:
        fval = float(v)
        # If the number is 0, return "0" directly
        if fval == 0.0:
            return "0"
        # Otherwise, format as before
        if abs(fval) < 1e-4:
            return f"{fval:.4e}"
        return f"{fval:.4f}"
    except Exception:
        return str(v)


def group_files(originals, stegos, extracts):
    """
    Groups original, stego, and extract files.

    Original files are stored in a dictionary mapped by a keyword, while stego
    and extract files are grouped by a numerical ID from their filenames.
    The function assumes a naming convention where original files contain a
    keyword (e.g., "baboon" in "orig_image_baboon.png") that is also present
    in the corresponding stego/extract filenames.
    """
    refs = {"image": {}, "audio": {}, "text": {}}
    groups = defaultdict(lambda: {"stego": [], "extract": []})

    # Store originals in a dictionary by keyword
    for f in originals:
        p = Path(f)
        suf = p.suffix.lower()
        name_stem = p.stem  # e.g., "orig_image_baboon"

        key = None
        if suf in IMG_EXT:
            if name_stem.startswith("orig_image_"):
                key = name_stem.replace("orig_image_", "")
            elif name_stem.startswith("orig_"):
                key = name_stem.replace("orig_", "")
            if key:
                refs["image"][key] = f
        
        elif suf in AUD_EXT:
            if name_stem.startswith("orig_audio_"):
                key = name_stem.replace("orig_audio_", "")
            elif name_stem.startswith("orig_"):
                key = name_stem.replace("orig_", "")
            if key:
                refs["audio"][key] = f

        elif suf in TXT_EXT:
            if name_stem.startswith("orig_text_"):
                key = name_stem.replace("orig_text_", "")
            elif name_stem.startswith("orig_"):
                key = name_stem.replace("orig_", "")
            if key:
                refs["text"][key] = f

    # Match stego files by ID
    for f in stegos:
        m = re.match(r"stego_(\d+)_", Path(f).name)
        if m:
            gid = int(m.group(1))
            groups[gid]["stego"].append(f)

    # Match extract files by ID
    for f in extracts:
        m = re.match(r"extract_(\d+)_", Path(f).name)
        if m:
            gid = int(m.group(1))
            groups[gid]["extract"].append(f)

    return refs, groups


# ---------------- MainWindow ----------------
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.last_data_rows: list[dict] = []

        # Disable metric group boxes initially
        self.set_group_state(self.ui.grb_audio_metrics, False)
        self.set_group_state(self.ui.grb_image_metrics, False)
        self.set_group_state(self.ui.grb_text_metrics, False)

        # Connect file drop signals
        self.ui.lst_original.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_stego.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_extract.filesChanged.connect(self.update_metrics_availability)

        # Allow all supported file extensions
        self.ui.lst_original.allowed_ext = IMG_EXT | AUD_EXT | TXT_EXT
        self.ui.lst_stego.allowed_ext = IMG_EXT | AUD_EXT | TXT_EXT
        self.ui.lst_extract.allowed_ext = IMG_EXT | AUD_EXT | TXT_EXT

        # Connect button actions
        self.ui.btn_export_report.clicked.connect(self.on_export_report)
        self.ui.btn_compute.clicked.connect(self.run_metrics)

    # ---------------- UI helpers ----------------
    def set_group_state(self, groupbox, enabled: bool, disabled_opacity: float = 0.4):
        groupbox.setEnabled(enabled)
        eff = groupbox.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(groupbox)
            groupbox.setGraphicsEffect(eff)
        eff.setOpacity(1.0 if enabled else disabled_opacity)

    def list_file_paths(self, lst) -> list[str]:
        out = []
        for i in range(lst.count()):
            it = lst.item(i)
            path_str = it.data(Qt.UserRole) or it.text()
            out.append(str(path_str))
        return out

    def list_file_exts(self, lst) -> set[str]:
        exts = set()
        for i in range(lst.count()):
            it = lst.item(i)
            path_str = it.data(Qt.UserRole) or it.text()
            suffix = Path(path_str).suffix.lower()
            if suffix:
                exts.add(suffix)
        return exts

    def any_ext_in(self, exts: set[str], pool: set[str]) -> bool:
        return any(e in pool for e in exts)

    def update_metrics_availability(self):
        exts_all = (
            self.list_file_exts(self.ui.lst_original)
            | self.list_file_exts(self.ui.lst_stego)
            | self.list_file_exts(self.ui.lst_extract)
        )
        has_img = self.any_ext_in(exts_all, IMG_EXT)
        has_aud = self.any_ext_in(exts_all, AUD_EXT)
        has_txt = self.any_ext_in(exts_all, TXT_EXT)

        self.set_group_state(self.ui.grb_image_metrics, has_img)
        self.set_group_state(self.ui.grb_audio_metrics, has_aud)
        self.set_group_state(self.ui.grb_text_metrics, has_txt)

    # ---------------- Metric Selection ----------------
    def get_selected_metrics(self) -> dict[str, list[str]]:
        sel = {"audio": [], "image": [], "text": []}
        # Audio
        if self.ui.chk_audio_mse.isChecked(): sel["audio"].append("mse")
        if self.ui.chk_audio_psnr.isChecked(): sel["audio"].append("psnr")
        if self.ui.chk_audio_snr.isChecked(): sel["audio"].append("snr")
        if self.ui.chk_audio_mae.isChecked(): sel["audio"].append("mae")
        if self.ui.chk_audio_lsd.isChecked(): sel["audio"].append("lsd")
        if self.ui.chk_audio_perceptual_score.isChecked(): sel["audio"].append("perceptual_score")
        if self.ui.chk_audio_bitwise_ber.isChecked(): sel["audio"].append("bitwise_ber")
        if self.ui.chk_audio_byte_accuracy.isChecked(): sel["audio"].append("byte_accuracy")
        if self.ui.chk_audio_exact_match.isChecked(): sel["audio"].append("exact_match")

        # Image
        if self.ui.chk_image_mse.isChecked(): sel["image"].append("mse")
        if self.ui.chk_image_psnr.isChecked(): sel["image"].append("psnr")
        if self.ui.chk_image_ssim.isChecked(): sel["image"].append("ssim")
        if self.ui.chk_image_ber.isChecked(): sel["image"].append("ber")
        if self.ui.chk_image_dssim.isChecked(): sel["image"].append("image_dssim")
        if self.ui.chk_image_lpips.isChecked(): sel["image"].append("image_lpips")
        if self.ui.chk_image_bitwise_ber.isChecked(): sel["image"].append("bitwise_ber")
        if self.ui.chk_image_byte_accuracy.isChecked(): sel["image"].append("byte_accuracy")
        if self.ui.chk_image_exact_match.isChecked(): sel["image"].append("exact_match")

        # Text
        if self.ui.chk_text_similarity.isChecked(): sel["text"].append("similarity")
        if self.ui.chk_text_levenshtein.isChecked(): sel["text"].append("levenshtein")
        if self.ui.chk_text_jaccard.isChecked(): sel["text"].append("jaccard")
        if self.ui.chk_text_exact_match.isChecked(): sel["text"].append("exact_match")
        if self.ui.chk_text_char_accuracy.isChecked(): sel["text"].append("char_accuracy")
        if self.ui.chk_text_bitwise_ber.isChecked(): sel["text"].append("bitwise_ber")

        return sel

    # ---------------- Metric Calculation ----------------
    def run_metrics(self):
        metrics = self.get_selected_metrics()
        if not any(metrics.values()):
            QMessageBox.warning(self, "Warning", "Please select at least one metric.")
            return

        # Read file paths from the drop lists
        originals = self.list_file_paths(self.ui.lst_original)
        stegos = self.list_file_paths(self.ui.lst_stego)
        extracts = self.list_file_paths(self.ui.lst_extract)

        refs, groups = group_files(originals, stegos, extracts)

        data_rows = []
        try:
            for gid, data in sorted(groups.items()):
                row = {"id": gid, "metrics": {}, "pairs": {}}
                
                # Audio: original vs. stego
                if metrics["audio"] and refs["audio"] and data["stego"]:
                    cmp_audio_path = data["stego"][0]
                    cmp_audio_name = Path(cmp_audio_path).name
                    ref_audio_path = None
                    
                    for key, path in refs["audio"].items():
                        if key in cmp_audio_name:
                            ref_audio_path = path
                            break
                    
                    if ref_audio_path:
                        row["pairs"]["audio"] = (ref_audio_path, cmp_audio_path)
                        for met in metrics["audio"]:
                            match met:
                                case "mse": row["metrics"]["audio_mse"] = audio_mse(ref_audio_path, cmp_audio_path)
                                case "psnr": row["metrics"]["audio_psnr"] = audio_psnr(ref_audio_path, cmp_audio_path)
                                case "snr": row["metrics"]["audio_snr"] = audio_snr(ref_audio_path, cmp_audio_path)
                                case "mae": row["metrics"]["audio_mae"] = audio_mae(ref_audio_path, cmp_audio_path)
                                case "lsd": row["metrics"]["audio_lsd"] = audio_lsd(ref_audio_path, cmp_audio_path)
                                case "perceptual_score": row["metrics"]["audio_perceptual_score"] = audio_perceptual_score(ref_audio_path, cmp_audio_path)
                                case "bitwise_ber": row["metrics"]["audio_bitwise_ber"] = audio_bitwise_ber(ref_audio_path, cmp_audio_path)
                                case "byte_accuracy": row["metrics"]["audio_byte_accuracy"] = audio_byte_accuracy(ref_audio_path, cmp_audio_path)
                                case "exact_match": row["metrics"]["audio_exact_match"] = audio_exact_match(ref_audio_path, cmp_audio_path)

                # Image: original vs. extract
                if metrics["image"] and refs["image"] and data["extract"]:
                    cmp_img_path = data["extract"][0]
                    cmp_img_name = Path(cmp_img_path).name
                    ref_img_path = None

                    for key, path in refs["image"].items():
                        if key in cmp_img_name:
                            ref_img_path = path
                            break
                    
                    if ref_img_path:
                        row["pairs"]["image"] = (ref_img_path, cmp_img_path)
                        for met in metrics["image"]:
                            match met:
                                case "mse": row["metrics"]["image_mse"] = image_mse(ref_img_path, cmp_img_path)
                                case "psnr": row["metrics"]["image_psnr"] = image_psnr(ref_img_path, cmp_img_path)
                                case "ssim": row["metrics"]["image_ssim"] = image_ssim(ref_img_path, cmp_img_path)
                                case "ber": row["metrics"]["image_ber"] = image_ber(ref_img_path, cmp_img_path)
                                case "image_dssim": row["metrics"]["image_dssim"] = image_dssim(ref_img_path, cmp_img_path)
                                case "image_lpips": row["metrics"]["image_lpips"] = image_lpips(ref_img_path, cmp_img_path)
                                case "bitwise_ber": row["metrics"]["image_bitwise_ber"] = image_bitwise_ber(ref_img_path, cmp_img_path)
                                case "byte_accuracy": row["metrics"]["image_byte_accuracy"] = image_byte_accuracy(ref_img_path, cmp_img_path)
                                case "exact_match": row["metrics"]["image_exact_match"] = image_exact_match(ref_img_path, cmp_img_path)

                # Text: original vs. extract
                if metrics["text"] and refs["text"] and data["extract"]:
                    cmp_txt_path = data["extract"][0]
                    cmp_txt_name = Path(cmp_txt_path).name
                    ref_txt_path = None

                    for key, path in refs["text"].items():
                        if key in cmp_txt_name:
                            ref_txt_path = path
                            break
                    
                    if ref_txt_path:
                        ref_txt = Path(ref_txt_path).read_text(encoding="utf-8", errors="ignore")
                        cmp_txt = Path(cmp_txt_path).read_text(encoding="utf-8", errors="ignore")
                        row["pairs"]["text"] = (ref_txt_path, cmp_txt_path)
                        for met in metrics["text"]:
                            match met:
                                case "similarity": row["metrics"]["text_similarity"] = text_similarity(ref_txt, cmp_txt)
                                case "levenshtein": row["metrics"]["text_levenshtein"] = text_levenshtein(ref_txt, cmp_txt)
                                case "jaccard": row["metrics"]["text_jaccard"] = text_jaccard(ref_txt, cmp_txt)
                                case "exact_match": row["metrics"]["text_exact_match"] = text_exact_match(ref_txt, cmp_txt)
                                case "char_accuracy": row["metrics"]["text_char_accuracy"] = char_accuracy(ref_txt, cmp_txt)
                                case "bitwise_ber": row["metrics"]["text_bitwise_ber"] = text_bitwise_ber(ref_txt, cmp_txt)

                data_rows.append(row)

            self.last_data_rows = data_rows
            self.populate_results_table(data_rows)
            QMessageBox.information(self, "Done", "Calculation complete. Results are listed in the table.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{e}")

    # ---------------- Exporting ----------------
    def on_export_report(self):
        if not self.last_data_rows:
            QMessageBox.warning(self, "Export", "Please run the metrics first.")
            return
        try:
            self.save_results_to_file(self.last_data_rows)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def save_results_to_file(self, data_rows: list[dict]):
        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.ui.rdb_export_txt.isChecked():
            txt_path, _ = QFileDialog.getSaveFileName(
                self, "Save TXT Report", f"metrics_{filename_ts}.txt", "Text Files (*.txt)"
            )
            if not txt_path:
                return
            self.save_txt_table(data_rows, txt_path, ts_str)
            QMessageBox.information(self, "Saved", f"TXT file saved to:\n{txt_path}")

        elif self.ui.rdb_export_pdf.isChecked():
            pdf_path, _ = QFileDialog.getSaveFileName(
                self, "Save PDF Report", f"metrics_{filename_ts}.pdf", "PDF Files (*.pdf)"
            )
            if not pdf_path:
                return
            self.save_pdf_table(data_rows, pdf_path, ts_str)
            QMessageBox.information(self, "Saved", f"PDF file saved to:\n{pdf_path}")

        else:
            QMessageBox.warning(self, "Export Format", "Please select an export format (TXT or PDF).")

    # ---------------- TXT/PDF Helpers ----------------
    def _all_metric_keys(self, data_rows: list[dict]) -> list[str]:
        keys = set()
        for row in data_rows:
            keys |= set((row.get("metrics") or {}).keys())
        return sorted(keys)

    def save_pdf_table(self, data_rows: list[dict], path: str, timestamp: str):
        # Create PDF in Portrait mode
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, "STEGANOGRAPHY METRICS REPORT", ln=True, align="C")
        pdf.set_font("Helvetica", 'I', 9)
        pdf.cell(0, 6, f"Generated on: {timestamp}", ln=True, align="C")
        pdf.ln(8)

        # Create a section for each ID
        for row in data_rows:
            metrics = row.get("metrics", {}) or {}
            pairs   = row.get("pairs", {}) or {}

            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(0, 8, f"ID: {row.get('id','?')}", ln=True)

            # List file information
            audio_ref, audio_cmp = map(lambda p: Path(p).name, pairs.get("audio", ("-", "-")))
            image_ref, image_cmp = map(lambda p: Path(p).name, pairs.get("image", ("-", "-")))
            text_ref,  text_cmp  = map(lambda p: Path(p).name, pairs.get("text", ("-", "-")))

            pdf.set_font("Helvetica", '', 10)
            if audio_ref != "-": pdf.cell(0, 6, f"  Orig_Audio:    {audio_ref}", ln=True)
            if audio_cmp != "-": pdf.cell(0, 6, f"  Stego_Audio:   {audio_cmp}", ln=True)
            if image_ref != "-": pdf.cell(0, 6, f"  Orig_Image:    {image_ref}", ln=True)
            if image_cmp != "-": pdf.cell(0, 6, f"  Extract_Image: {image_cmp}", ln=True)
            if text_ref  != "-": pdf.cell(0, 6, f"  Orig_Text:     {text_ref}", ln=True)
            if text_cmp  != "-": pdf.cell(0, 6, f"  Extract_Text:  {text_cmp}", ln=True)
            pdf.ln(3)

            # 2-column table for metrics
            metric_keys = sorted(metrics.keys())
            if metric_keys:
                pdf.set_fill_color(230, 230, 230)
                pdf.set_draw_color(150, 150, 150)
                pdf.set_font("Helvetica", 'B', 10)
                # Center the table on the page by setting the initial x position
                table_x_start = (pdf.w - 140) / 2
                pdf.set_x(table_x_start)
                pdf.cell(70, 8, "Metric", border=1, fill=True, align='C')
                pdf.cell(70, 8, "Value", border=1, fill=True, align='C')
                pdf.ln()

                pdf.set_font("Helvetica", '', 9)
                for key in metric_keys:
                    metric_label = key.replace("_", " ").title() # e.g., "Audio Mse"
                    pdf.set_x(table_x_start)
                    pdf.cell(70, 8, metric_label, border=1, align='L')
                    pdf.cell(70, 8, fmt_val(metrics.get(key, "")), border=1, align='R')
                    pdf.ln()
            else:
                pdf.set_font("Helvetica", 'I', 10)
                pdf.cell(0, 6, "  (No metrics calculated for this ID)", ln=True)

            # Add a separator line between IDs
            if row != data_rows[-1]:
                pdf.ln(5)
                pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(5)
            
        pdf.output(path)


    def save_txt_table(self, data_rows: list[dict], path: str, timestamp: str):
        lines = []
        lines.append("STEGANOGRAPHY METRICS REPORT")
        lines.append(f"Generated on: {timestamp}")
        lines.append("=" * 80)

        if not data_rows:
            lines.append("No data to report.")
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            return

        # --- Prepare Table Headers and Data ---
        metric_cols = self._all_metric_keys(data_rows)
        file_cols = []
        has_audio = any("audio" in row.get("pairs", {}) for row in data_rows)
        has_image = any("image" in row.get("pairs", {}) for row in data_rows)
        has_text = any("text" in row.get("pairs", {}) for row in data_rows)

        if has_audio: file_cols += ["Orig_Audio", "Stego_Audio"]
        if has_image: file_cols += ["Orig_Image", "Extract_Image"]
        if has_text: file_cols += ["Orig_Text", "Extract_Text"]

        headers = ["ID"] + file_cols + [h.upper() for h in metric_cols]
        
        # --- Collect All Data in a Single List ---
        all_table_data = [headers]
        for row in data_rows:
            row_vals = [str(row.get("id", "?"))]
            pairs = row.get("pairs", {})
            metrics = row.get("metrics", {}) or {}

            if has_audio:
                a_ref, a_cmp = map(lambda p: Path(p).name, pairs.get("audio", ("-", "-")))
                row_vals += [a_ref, a_cmp]
            if has_image:
                i_ref, i_cmp = map(lambda p: Path(p).name, pairs.get("image", ("-", "-")))
                row_vals += [i_ref, i_cmp]
            if has_text:
                t_ref, t_cmp = map(lambda p: Path(p).name, pairs.get("text", ("-", "-")))
                row_vals += [t_ref, t_cmp]
            
            for k in metric_cols:
                row_vals.append(fmt_val(metrics.get(k, "")))
            
            all_table_data.append(row_vals)

        # --- Calculate Column Widths ---
        col_widths = [max(len(str(item)) for item in col) for col in zip(*all_table_data)]

        # --- Build the Table String ---
        # Header
        header_line = " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers)))
        separator_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
        lines.append(header_line)
        lines.append(separator_line)

        # Data Rows
        for r_idx in range(1, len(all_table_data)): # Skip the header row
            row_data = all_table_data[r_idx]
            data_line = " | ".join(str(row_data[i]).ljust(col_widths[i]) for i in range(len(row_data)))
            lines.append(data_line)

        Path(path).write_text("\n".join(lines), encoding="utf-8")

    # ---------------- Table Population ----------------
    def populate_results_table(self, data_rows: list[dict]):
        tbl = self.ui.tbl_results
        if tbl is None:
            return

        # Dynamic column list
        metric_cols = self._all_metric_keys(data_rows)
        file_cols = []

        # Add columns only for the types present
        has_audio = any("audio" in row.get("pairs", {}) for row in data_rows)
        has_image = any("image" in row.get("pairs", {}) for row in data_rows)
        has_text  = any("text"  in row.get("pairs", {}) for row in data_rows)

        if has_audio:
            file_cols += ["Orig_Audio", "Stego_Audio"]
        if has_image:
            file_cols += ["Orig_Image", "Extract_Image"]
        if has_text:
            file_cols += ["Orig_Text", "Extract_Text"]

        headers = ["ID"] + file_cols + [h.upper() for h in metric_cols]

        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(data_rows))

        # Fill rows
        for r, row in enumerate(data_rows):
            row_vals = [str(row.get("id", "?"))]

            pairs = row.get("pairs", {})
            metrics = row.get("metrics", {}) or {}

            if has_audio:
                a_ref, a_cmp = map(lambda p: Path(p).name, pairs.get("audio", ("-", "-")))
                row_vals += [a_ref, a_cmp]
            if has_image:
                i_ref, i_cmp = map(lambda p: Path(p).name, pairs.get("image", ("-", "-")))
                row_vals += [i_ref, i_cmp]
            if has_text:
                t_ref, t_cmp = map(lambda p: Path(p).name, pairs.get("text", ("-", "-")))
                row_vals += [t_ref, t_cmp]

            for k in metric_cols:
                row_vals.append(fmt_val(metrics.get(k, "")))

            for c, txt in enumerate(row_vals):
                it = QTableWidgetItem(txt)
                it.setFlags(it.flags() ^ Qt.ItemIsEditable)
                tbl.setItem(r, c, it)

            tbl.resizeRowToContents(r)

        tbl.resizeColumnsToContents()
        tbl.horizontalHeader().setStretchLastSection(True)


# ------------------------------- Main -------------------------------
def main():
    plt.ioff()
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()