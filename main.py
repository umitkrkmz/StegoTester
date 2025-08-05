import sys
from pathlib import Path
from datetime import datetime

import matplotlib.pyplot as plt
from fpdf import FPDF

from stegobench.metrics.audio.objective import audio_mse, audio_psnr, audio_snr
from stegobench.metrics.image.objective import image_mse, image_psnr, image_ssim, image_ber
from stegobench.metrics.text.objective import text_similarity, text_levenshtein, text_jaccard

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsOpacityEffect,
    QFileDialog, QMessageBox, QTableWidgetItem,
)

from ui_form import Ui_MainWindow

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
AUD_EXT = {".wav"}
TXT_EXT = {".txt", ".bin"}

def fmt_val(v) -> str:
    """Format metric values: 'inf' if infinite, int as-is, float with adaptive precision."""
    try:
        if v == float("inf"):
            return "inf"
    except Exception:
        pass

    if isinstance(v, int):
        return str(v)

    try:
        fval = float(v)
        if abs(fval) < 1e-4:
            return f"{fval:.4e}"  # scientific display
        return f"{fval:.4f}"      # normal display
    except Exception:
        return str(v)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.last_data_rows: list[dict] = []

        # Initially disable metric groups until a compatible file is present
        self.set_group_state(self.ui.grb_audio_metrics, False)
        self.set_group_state(self.ui.grb_image_metrics, False)
        self.set_group_state(self.ui.grb_text_metrics,  False)

        # Update metric availability when file lists change
        self.ui.lst_original.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_stego.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_extract.filesChanged.connect(self.update_metrics_availability)

        # Allow all relevant extensions in all lists
        self.ui.lst_original.allowed_ext = IMG_EXT | AUD_EXT | TXT_EXT
        self.ui.lst_stego.allowed_ext    = IMG_EXT | AUD_EXT | TXT_EXT
        self.ui.lst_extract.allowed_ext  = IMG_EXT | AUD_EXT | TXT_EXT

        # ----------------------- Actions -----------------------
        self.ui.btn_export_report.clicked.connect(self.on_export_report)
        self.ui.btn_compute.clicked.connect(self.run_metrics)

    def set_group_state(self, groupbox, enabled: bool, disabled_opacity: float = 0.4):
        """Enable/disable a group box and visually dim it when disabled."""
        groupbox.setEnabled(enabled)
        eff = groupbox.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(groupbox)
            groupbox.setGraphicsEffect(eff)
        eff.setOpacity(1.0 if enabled else disabled_opacity)
    
    
    def list_file_exts(self, lst) -> set[str]:
        """Collect (lowercased) file extensions from a custom list widget."""
        exts = set()
        for i in range(lst.count()):
            it = lst.item(i)
            path_str = it.data(Qt.UserRole) or it.text()
            suffix = Path(path_str).suffix.lower()
            if suffix:
                exts.add(suffix)
        return exts

    @staticmethod
    def any_ext_in(exts: set[str], pool: set[str]) -> bool:
        return any(e in pool for e in exts)

    def update_metrics_availability(self):
        """Toggle metric sections based on whether at least one compatible file exists."""
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
        self.set_group_state(self.ui.grb_text_metrics,  has_txt)

        
        
    def get_selected_metrics(self) -> dict[str, list[str]]:
        """Return selected metrics per data type, based on UI checkboxes."""
        selected = {"audio": [], "image": [], "text": []}

        # Audio
        if self.ui.chk_audio_mse.isChecked():  selected["audio"].append("mse")
        if self.ui.chk_audio_psnr.isChecked(): selected["audio"].append("psnr")
        if self.ui.chk_audio_snr.isChecked():  selected["audio"].append("snr")

        # Image
        if self.ui.chk_image_mse.isChecked():  selected["image"].append("mse")
        if self.ui.chk_image_psnr.isChecked(): selected["image"].append("psnr")
        if self.ui.chk_image_ssim.isChecked(): selected["image"].append("ssim")
        if self.ui.chk_image_ber.isChecked():  selected["image"].append("ber")

        # Text
        if self.ui.chk_text_similarity.isChecked():  selected["text"].append("similarity")
        if self.ui.chk_text_levenshtein.isChecked(): selected["text"].append("levenshtein")
        if self.ui.chk_text_jaccard.isChecked():     selected["text"].append("jaccard")

        return selected


    def get_file_by_ext(self, lst, ext_list: set[str]) -> str | None:
        """Return the first file path from a list whose extension is in ext_list."""
        for i in range(lst.count()):
            item = lst.item(i)
            path = Path(item.data(Qt.UserRole) or item.text())
            if path.suffix.lower() in ext_list:
                return str(path)
        return None

    
    def run_metrics(self):
        metrics = self.get_selected_metrics()
        if not any(metrics.values()):
            QMessageBox.warning(self, "Warning", "Please select at least one metric to compute.")
            return

        orig_audio = self.get_file_by_ext(self.ui.lst_original, AUD_EXT)
        orig_img   = self.get_file_by_ext(self.ui.lst_original, IMG_EXT)
        orig_txt   = self.get_file_by_ext(self.ui.lst_original, TXT_EXT)

        stego   = self.get_file_by_ext(self.ui.lst_stego,  AUD_EXT | IMG_EXT | TXT_EXT)
        extract = self.get_file_by_ext(self.ui.lst_extract, IMG_EXT | TXT_EXT | AUD_EXT)

        data_rows: list[dict] = []
        try:
            row = {"id": 1, "metrics": {}, "pairs": {}}  # pairs[dtype] = (ref, cmp)

            # ------------ Audio ------------
            if metrics["audio"]:
                ref_audio = orig_audio
                cmp_audio = (
                    stego if (stego and Path(stego).suffix in AUD_EXT)
                    else (extract if (extract and Path(extract).suffix in AUD_EXT) else None)
                )
                if ref_audio and cmp_audio:
                    row["pairs"]["audio"] = (ref_audio, cmp_audio)
                    for met in metrics["audio"]:
                        match met:
                            case "mse":  row["metrics"]["audio_mse"]  = audio_mse(ref_audio, cmp_audio)
                            case "psnr": row["metrics"]["audio_psnr"] = audio_psnr(ref_audio, cmp_audio)
                            case "snr":  row["metrics"]["audio_snr"]  = audio_snr(ref_audio, cmp_audio)

            # ------------ Image ------------
            if metrics["image"]:
                ref_img = orig_img
                cmp_img = (
                    extract if (extract and Path(extract).suffix in IMG_EXT)
                    else (stego if (stego and Path(stego).suffix in IMG_EXT) else None)
                )
                if ref_img and cmp_img:
                    row["pairs"]["image"] = (ref_img, cmp_img)
                    for met in metrics["image"]:
                        match met:
                            case "mse":  row["metrics"]["image_mse"]  = image_mse(ref_img, cmp_img)
                            case "psnr": row["metrics"]["image_psnr"] = image_psnr(ref_img, cmp_img)
                            case "ssim": row["metrics"]["image_ssim"] = image_ssim(ref_img, cmp_img)
                            case "ber":  row["metrics"]["image_ber"]  = image_ber(ref_img, cmp_img)

            # ------------ Text ------------
            if metrics["text"] and orig_txt and extract and Path(extract).suffix in TXT_EXT:
                row["pairs"]["text"] = (orig_txt, extract)
                t1 = Path(orig_txt).read_text(encoding="utf-8", errors="ignore")
                t2 = Path(extract).read_text(encoding="utf-8", errors="ignore")
                for met in metrics["text"]:
                    match met:
                        case "similarity":  row["metrics"]["text_similarity"]  = text_similarity(t1, t2)
                        case "levenshtein": row["metrics"]["text_levenshtein"] = text_levenshtein(t1, t2)
                        case "jaccard":     row["metrics"]["text_jaccard"]     = text_jaccard(t1, t2)

            data_rows.append(row)

            # Show in-app; export only when user asks
            self.last_data_rows = data_rows
            self.populate_results_table(data_rows)
            QMessageBox.information(
                self, "Done",
                "Computation finished. Results are listed in the table.\nUse 'Export Report' to save TXT/PDF."
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{e}")


    def on_export_report(self):
        if not self.last_data_rows:
            QMessageBox.warning(self, "Export", "Please compute metrics first.")
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
            QMessageBox.information(self, "Saved", f"TXT file saved:\n{txt_path}")

        elif self.ui.rdb_export_pdf.isChecked():
            pdf_path, _ = QFileDialog.getSaveFileName(
                self, "Save PDF Report", f"metrics_{filename_ts}.pdf", "PDF Files (*.pdf)"
            )
            if not pdf_path:
                return
            self.save_pdf_table(data_rows, pdf_path, ts_str)
            QMessageBox.information(self, "Saved", f"PDF file saved:\n{pdf_path}")

        else:
            QMessageBox.warning(self, "Export Format", "Please select an export format (TXT or PDF).")



#region Report Exporters
    def save_pdf_table(self, data_rows: list[dict], path: str, timestamp: str):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Helvetica", 'B', 16)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "STEGANOGRAPHY METRICS REPORT", ln=True, align='L')

        pdf.set_xy(160, 10)
        pdf.set_font("Helvetica", 'I', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(40, 10, f"Generated on: {timestamp}", ln=1)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(10)

        for row in data_rows:
            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(0, 8, f"ID: {row.get('id','?')}", ln=1)

            metrics = row.get("metrics", {}) or {}
            pairs   = row.get("pairs", {}) or {}

            for dtype in ("audio", "image", "text"):
                if dtype not in pairs:
                    continue

                ref_path, cmp_path = pairs[dtype]
                rel_keys = [k for k in metrics if k.startswith(f"{dtype}_")]

                # Section header
                pdf.set_font("Helvetica", 'B', 11)
                pdf.cell(0, 6, f"[{dtype.upper()} METRICS]", ln=1)

                # File names
                pdf.set_font("Helvetica", '', 10)
                pdf.cell(0, 6, f"Original: {Path(ref_path).name}", ln=1)
                pdf.cell(0, 6, f"Compare:  {Path(cmp_path).name}", ln=1)

                if rel_keys:
                    pdf.set_fill_color(230, 230, 230)
                    pdf.set_draw_color(150, 150, 150)
                    pdf.set_font("Helvetica", 'B', 10)
                    for key in rel_keys:
                        pdf.cell(40, 8, key.replace(f"{dtype}_", "").upper(), border=1, fill=True, align='C')
                    pdf.ln()

                    pdf.set_font("Helvetica", '', 10)
                    for key in rel_keys:
                        pdf.cell(40, 8, fmt_val(metrics[key]), border=1, align='C')
                    pdf.ln(10)
                else:
                    pdf.set_font("Helvetica", 'I', 10)
                    pdf.set_text_color(120, 120, 120)
                    pdf.cell(0, 6, "No metrics for this row.", ln=1)
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(4)

            pdf.ln(5)

        pdf.output(path)
    
    def save_txt_table(self, data_rows: list[dict], path: str, timestamp: str):
        lines = []
        lines.append("STEGANOGRAPHY METRICS REPORT")
        lines.append(f"Generated on: {timestamp}")
        lines.append("=" * 60)

        for row in data_rows:
            lines.append(f"\nID: {row.get('id','?')}")
            metrics = row.get("metrics", {}) or {}
            pairs   = row.get("pairs", {}) or {}

            for dtype in ("audio", "image", "text"):
                if dtype not in pairs:
                    continue

                ref_path, cmp_path = pairs[dtype]
                title = f"{dtype.upper()} METRICS"
                lines.append(f"\n{'=' * (22)} {title} {'=' * (60 - 23 - len(title))}")
                lines.append(f"Original: {Path(ref_path).name}")
                lines.append(f"Compare:  {Path(cmp_path).name}")

                rel_keys = [k for k in metrics if k.startswith(f"{dtype}_")]
                if rel_keys:
                    lines.append("| Metric   | Value         |")
                    lines.append("|----------|---------------|")
                    for key in rel_keys:
                        label = key.replace(f"{dtype}_", "").upper().ljust(8)
                        value = fmt_val(metrics[key]).ljust(13)
                        lines.append(f"| {label} | {value} |")
                else:
                    lines.append("(No metrics for this row)")

        Path(path).write_text("\n".join(lines), encoding="utf-8")

#endregion


    def populate_results_table(self, data_rows: list[dict]):
        tbl = self.ui.tbl_results
        if tbl is None:
            return

        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["ID", "Type", "Original", "Compare", "Metrics"])
        tbl.setRowCount(0)

        # Flatten by dtype
        flat_rows = []
        for row in data_rows:
            for dtype in ("audio", "image", "text"):
                if dtype in row.get("pairs", {}):
                    ref_path, cmp_path = row["pairs"][dtype]
                    metrics = row.get("metrics", {}) or {}
                    rel = {k: v for k, v in metrics.items() if k.startswith(f"{dtype}_")}
                    flat_rows.append({
                        "id": row.get("id", 1),
                        "dtype": dtype.upper(),
                        "ref": Path(ref_path).name,
                        "cmp": Path(cmp_path).name,
                        "metrics": rel
                    })

        tbl.setRowCount(len(flat_rows))

        for r, fr in enumerate(flat_rows):
            metrics_lines = [
                f"{k.split('_', 1)[1].upper()}: {fmt_val(v)}"
                for k, v in fr["metrics"].items()
            ]
            metrics_text = "\n".join(metrics_lines) if metrics_lines else "(no metrics)"

            cells = [
                QTableWidgetItem(str(fr["id"])),
                QTableWidgetItem(fr["dtype"]),
                QTableWidgetItem(fr["ref"]),
                QTableWidgetItem(fr["cmp"]),
                QTableWidgetItem(metrics_text),
            ]
            for c, it in enumerate(cells):
                it.setFlags(it.flags() ^ Qt.ItemIsEditable)  # read-only
                tbl.setItem(r, c, it)

            # Let rows grow to fit multiline metric text
            tbl.resizeRowToContents(r)


            
# -------------------------------------- Main --------------------------------------
def main():
    plt.ioff()  # disable interactive Matplotlib windows
    app = QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()