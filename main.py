# main.py
# This is the main application file. It contains the MainWindow class,
# which orchestrates the UI and connects all the modular components.

import sys
import os
import subprocess
from datetime import datetime
import json
from pathlib import Path

# --- Local Module Imports ---
from ui_form import Ui_MainWindow
from utils import IMG_EXT, AUD_EXT, TXT_EXT, fmt_val, group_files
from dialogs import ImageComparisonDialog
import reporting
from reporting import save_json_table, save_csv_table
from worker import MetricWorker, ReportWorker
from chart_dialog import ChartDialog
from droplist import DropList

# --- Qt Imports ---
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsOpacityEffect,
    QFileDialog, QMessageBox, QTableWidgetItem, QMenu,QListWidgetItem
)

# ---------------- MainWindow ----------------
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.last_data_rows: list[dict] = []
              
        # Hide ProgressBar on startup
        self.ui.progressBar.hide()

        # Disable metric group boxes initially
        self.set_group_state(self.ui.grb_audio_metrics, False)
        self.set_group_state(self.ui.grb_image_metrics, False)
        self.set_group_state(self.ui.grb_text_metrics, False)

        # Connect file drop signals
        self.ui.lst_original.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_stego.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_extract.filesChanged.connect(self.update_metrics_availability)

        # Allow all supported file extensions
        all_exts = IMG_EXT | AUD_EXT | TXT_EXT
        self.ui.lst_original.allowed_ext = all_exts
        self.ui.lst_stego.allowed_ext = all_exts
        self.ui.lst_extract.allowed_ext = all_exts

        # Connect button actions
        self.ui.btn_export_report.clicked.connect(self.on_export_report)
        self.ui.btn_compute.clicked.connect(self.start_metric_calculation)
        self.ui.btn_save_profile.clicked.connect(self.save_profile)
        self.ui.btn_load_profile.clicked.connect(self.load_profile)
        self.ui.btn_generate_chart.clicked.connect(self.on_generate_chart)
        self.ui.btn_add_folder_original.clicked.connect(
            lambda: self.add_files_from_folder(self.ui.lst_original)
        )
        self.ui.btn_add_folder_stego.clicked.connect(
            lambda: self.add_files_from_folder(self.ui.lst_stego)
        )
        self.ui.btn_add_folder_extract.clicked.connect(
            lambda: self.add_files_from_folder(self.ui.lst_extract)
        )
        
        # Connect context menu for the results table
        self.ui.tbl_results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tbl_results.customContextMenuRequested.connect(self.on_results_context_menu)

    #region --- UI helpers ---
    def set_group_state(self, groupbox, enabled: bool, disabled_opacity: float = 0.4):
        """Enables or disables a group box with a visual opacity effect."""
        groupbox.setEnabled(enabled)
        eff = groupbox.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(groupbox)
            groupbox.setGraphicsEffect(eff)
        eff.setOpacity(1.0 if enabled else disabled_opacity)

    def list_file_paths(self, lst) -> list[str]:
        """Retrieves the full file paths from a given QListWidget."""
        out = []
        for i in range(lst.count()):
            it = lst.item(i)
            path_str = it.data(Qt.UserRole) or it.text()
            out.append(str(path_str))
        return out

    def list_file_exts(self, lst) -> set[str]:
        """Returns a set of all unique, lowercase file extensions from a QListWidget."""
        exts = set()
        for i in range(lst.count()):
            it = lst.item(i)
            path_str = it.data(Qt.UserRole) or it.text()
            suffix = Path(path_str).suffix.lower()
            if suffix:
                exts.add(suffix)
        return exts

    def any_ext_in(self, exts: set[str], pool: set[str]) -> bool:
        """Checks if any extension from a given set exists in a pool of allowed extensions."""
        return any(e in pool for e in exts)

    def update_metrics_availability(self):
        """Updates the UI by enabling/disabling metric groups based on loaded file types."""
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
    
    def add_files_from_folder(self, list_widget: DropList):
        """Opens a dialog to select a folder and adds its files to the list widget."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path:
            return

        added_count = 0
        existing_paths = {list_widget.item(i).data(Qt.UserRole) for i in range(list_widget.count())}

        for file_path in Path(folder_path).rglob('*'):
            if file_path.is_file() and (not list_widget.allowed_ext or file_path.suffix.lower() in list_widget.allowed_ext):
                sp = str(file_path)
                if sp not in existing_paths:
                    it = QListWidgetItem(file_path.name)
                    it.setData(Qt.UserRole, sp)
                    list_widget.addItem(it)
                    added_count += 1

        if added_count > 0:
            list_widget.filesChanged.emit() # Trigger update of metric groups
    
    #endregion
    
    #region --- Metric Selection & Profiles ---
    def get_selected_metrics(self) -> dict[str, list[str]]:
        """Gathers the names of all currently checked metrics from the UI."""
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

    def save_profile(self):
        """Opens a save dialog to save the current metric selections to a JSON file."""
        selected_metrics = self.get_selected_metrics()
        filePath, _ = QFileDialog.getSaveFileName(self, "Save Profile", "metric_profile.json", "JSON Files (*.json)")
        if filePath:
            try:
                with open(filePath, 'w', encoding='utf-8') as f:
                    json.dump(selected_metrics, f, indent=4)
                QMessageBox.information(self, "Success", f"Profile saved to:\n{filePath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save profile:\n{e}")
                
    def load_profile(self):
        """Opens a file dialog to load metric selections from a JSON profile."""
        filePath, _ = QFileDialog.getOpenFileName(self, "Load Profile", "", "JSON Files (*.json)")
        if filePath:
            try:
                with open(filePath, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
                self.apply_profile(profile_data)
                QMessageBox.information(self, "Success", "Profile loaded successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not load profile:\n{e}")

    def apply_profile(self, profile: dict):
        """Applies the loaded profile data to the UI checkboxes."""
        audio_metrics = profile.get("audio", [])
        image_metrics = profile.get("image", [])
        text_metrics = profile.get("text", [])
        # --- Audio Checkboxes ---
        self.ui.chk_audio_mse.setChecked("mse" in audio_metrics)
        self.ui.chk_audio_psnr.setChecked("psnr" in audio_metrics)
        self.ui.chk_audio_snr.setChecked("snr" in audio_metrics)
        self.ui.chk_audio_mae.setChecked("mae" in audio_metrics)
        self.ui.chk_audio_lsd.setChecked("lsd" in audio_metrics)
        self.ui.chk_audio_perceptual_score.setChecked("perceptual_score" in audio_metrics)
        self.ui.chk_audio_bitwise_ber.setChecked("bitwise_ber" in audio_metrics)
        self.ui.chk_audio_byte_accuracy.setChecked("byte_accuracy" in audio_metrics)
        self.ui.chk_audio_exact_match.setChecked("exact_match" in audio_metrics)
        # --- Image Checkboxes ---
        self.ui.chk_image_mse.setChecked("mse" in image_metrics)
        self.ui.chk_image_psnr.setChecked("psnr" in image_metrics)
        self.ui.chk_image_ssim.setChecked("ssim" in image_metrics)
        self.ui.chk_image_ber.setChecked("ber" in image_metrics)
        self.ui.chk_image_dssim.setChecked("image_dssim" in image_metrics)
        self.ui.chk_image_lpips.setChecked("image_lpips" in image_metrics)
        self.ui.chk_image_bitwise_ber.setChecked("bitwise_ber" in image_metrics)
        self.ui.chk_image_byte_accuracy.setChecked("byte_accuracy" in image_metrics)
        self.ui.chk_image_exact_match.setChecked("exact_match" in image_metrics)
        # --- Text Checkboxes ---
        self.ui.chk_text_similarity.setChecked("similarity" in text_metrics)
        self.ui.chk_text_levenshtein.setChecked("levenshtein" in text_metrics)
        self.ui.chk_text_jaccard.setChecked("jaccard" in text_metrics)
        self.ui.chk_text_exact_match.setChecked("exact_match" in text_metrics)
        self.ui.chk_text_char_accuracy.setChecked("char_accuracy" in text_metrics)
        self.ui.chk_text_bitwise_ber.setChecked("bitwise_ber" in text_metrics)
    #endregion
    
    #region --- Calculation & Results ---
    def start_metric_calculation(self):
        """Gathers UI settings, groups files, and starts the metric calculation thread."""
        metrics = self.get_selected_metrics()
        if not any(metrics.values()):
            QMessageBox.warning(self, "Warning", "Please select at least one metric.")
            return

        # 1. Get the pattern entered by the user
        pattern = self.ui.txt_file_pattern.text()
        if not pattern: # Eğer boşsa, placeholder'daki varsayılanı kullan
            pattern = self.ui.txt_file_pattern.placeholderText()

        # 2. Get file lists
        originals = self.list_file_paths(self.ui.lst_original)
        stegos = self.list_file_paths(self.ui.lst_stego)
        extracts = self.list_file_paths(self.ui.lst_extract)
        
        # 3. Group files (with the new utils function)
        try:
            refs, groups = group_files(originals, stegos, extracts, pattern)
            if not groups:
                QMessageBox.information(self, "No Matches", "No file groups could be matched with the current pattern.")
                return
        except Exception as e:
            QMessageBox.critical(self, "File Matching Error", f"Could not group files.\nPlease check the matching pattern and file names.\n\nError: {e}")
            return

        # 4. Prepare the interface and start the Worker
        self.ui.btn_compute.setEnabled(False)
        self.ui.btn_generate_chart.setEnabled(False)
        self.ui.progressBar.show()
        self.ui.progressBar.setValue(0)

        self.thread = QThread()
        # We are now sending ready-made groups to Worker
        self.worker = MetricWorker(refs, groups, metrics)
        self.worker.moveToThread(self.thread)
        
        # Signal connections
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_calculation_finished)
        self.worker.error.connect(self.on_calculation_error)
        self.worker.progress.connect(self.ui.progressBar.setValue)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_calculation_finished(self, data_rows):
        """Slot executed when the MetricWorker finishes successfully."""
        self.ui.progressBar.hide()
        
        # Enable buttons after calculation is complete
        self.ui.btn_compute.setEnabled(True)
        self.ui.btn_generate_chart.setEnabled(True)
        
        
        self.last_data_rows = data_rows
        self.populate_results_table(data_rows)
        QMessageBox.information(self, "Done", "Calculation complete.")

    def on_calculation_error(self, error_message):
        """Slot executed when the MetricWorker encounters an error."""
        self.ui.progressBar.hide()
        self.ui.btn_compute.setEnabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")

    def populate_results_table(self, data_rows: list[dict]):
        """Fills the results table in the UI with the calculated data."""
        tbl = self.ui.tbl_results
        tbl.setRowCount(0) # Clear previous results
        if not data_rows: return

        metric_cols = reporting._get_all_metric_keys(data_rows)
        file_cols = []
        has_audio = any("audio" in row.get("pairs", {}) for row in data_rows)
        has_image = any("image" in row.get("pairs", {}) for row in data_rows)
        has_text  = any("text"  in row.get("pairs", {}) for row in data_rows)

        if has_audio: file_cols += ["Orig_Audio", "Stego_Audio"]
        if has_image: file_cols += ["Orig_Image", "Extract_Image"]
        if has_text: file_cols += ["Orig_Text", "Extract_Text"]

        headers = ["ID"] + file_cols + [h.upper() for h in metric_cols]
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setRowCount(len(data_rows))

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
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                tbl.setItem(r, c, it)
        tbl.resizeColumnsToContents()
        tbl.horizontalHeader().setStretchLastSection(True)
         
    def on_generate_chart(self):
        """Opens the chart dialog to visualize the results."""
        if not self.last_data_rows:
            QMessageBox.warning(self, "Generate Chart", "Please compute metrics first.")
            return
        
        # Create and show the chart dialog
        dialog = ChartDialog(self.last_data_rows, self)
        dialog.exec()
    #endregion
    
    #region --- Interactive Table & Exporting ---
    def on_export_report(self):
        """Opens a save dialog and starts the report generation in a background thread."""
        if not self.last_data_rows:
            QMessageBox.warning(self, "Export", "Please run the metrics first.")
            return

        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        file_filter = "PDF Files (*.pdf);;Text Files (*.txt);;JSON Files (*.json);;CSV Files (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Save Report", f"metrics_{filename_ts}", file_filter)

        if not path: return # User canceled

        # Lock the interface and start the progress bar in "indefinite" mode
        self.ui.centralwidget.setEnabled(False)
        self.ui.progressBar.setRange(0, 0) # Indefinite mode
        self.ui.progressBar.show()

        # Set up reporting worker and thread
        self.report_thread = QThread()
        self.report_worker = ReportWorker(self.last_data_rows, path, ts_str)
        self.report_worker.moveToThread(self.report_thread)

        # connect signals
        self.report_thread.started.connect(self.report_worker.run)
        self.report_worker.finished.connect(self.on_report_finished)
        self.report_worker.error.connect(self.on_report_error)

        # Cleaning
        self.report_worker.finished.connect(self.report_thread.quit)
        self.report_worker.finished.connect(self.report_worker.deleteLater)
        self.report_thread.finished.connect(self.report_thread.deleteLater)

        self.report_thread.start()
    
    
    def on_report_finished(self, path):
        """Slot executed when the ReportWorker finishes successfully."""
        self.ui.centralwidget.setEnabled(True) # unlock interface
        
        # Hide progress bar and return to normal mode
        self.ui.progressBar.hide()
        self.ui.progressBar.setRange(0, 100) 
    
        QMessageBox.information(self, "Saved", f"Report file saved to:\n{path}")

    def on_report_error(self, error_message):
        """Slot executed when the ReportWorker encounters an error."""
        self.ui.centralwidget.setEnabled(True) # unlock interface
        
        # Hide progress bar and return to normal mode
        self.ui.progressBar.hide()
        self.ui.progressBar.setRange(0, 100)
        
        QMessageBox.critical(self, "Export Error", str(error_message))
            
    def open_file_explorer(self, path):
        """Opens the system's file explorer to the specified file's containing folder."""
        folder = os.path.dirname(path)
        if sys.platform == 'win32': os.startfile(folder)
        elif sys.platform == 'darwin': subprocess.run(['open', folder])
        else: subprocess.run(['xdg-open', folder])

    def on_results_context_menu(self, pos):
        """Handles the right-click event on the results table to show a context-sensitive menu."""
        tbl = self.ui.tbl_results
        item = tbl.itemAt(pos)
        if not item: return

        row_index, column_index = item.row(), item.column()
        header_text = tbl.horizontalHeaderItem(column_index).text()
        if row_index >= len(self.last_data_rows): return

        row_data = self.last_data_rows[row_index]
        pairs = row_data.get("pairs", {})
        clicked_file_path, file_type = None, None
        
        if header_text == "Orig_Audio" and "audio" in pairs: clicked_file_path, file_type = pairs["audio"][0], "audio"
        elif header_text == "Stego_Audio" and "audio" in pairs: clicked_file_path, file_type = pairs["audio"][1], "audio"
        elif header_text == "Orig_Image" and "image" in pairs: clicked_file_path, file_type = pairs["image"][0], "image"
        elif header_text == "Extract_Image" and "image" in pairs: clicked_file_path, file_type = pairs["image"][1], "image"
        elif header_text == "Orig_Text" and "text" in pairs: clicked_file_path, file_type = pairs["text"][0], "text"
        elif header_text == "Extract_Text" and "text" in pairs: clicked_file_path, file_type = pairs["text"][1], "text"
        
        menu = QMenu(self)
        action_open_loc, action_view_image, action_compare_img, action_listen_audio = None, None, None, None

        if clicked_file_path:
            file_name = Path(clicked_file_path).name
            action_open_loc = menu.addAction(f"'{file_name}' Konumunu Aç")
        if file_type == "image":
            file_name = Path(clicked_file_path).name
            action_view_image = menu.addAction(f"'{file_name}' Görüntüle")
            action_compare_img = menu.addAction("Resimleri Karşılaştır")
        if file_type == "audio":
            file_name = Path(clicked_file_path).name
            action_listen_audio = menu.addAction(f"'{file_name}' Dinle")

        if not menu.actions(): return
        action = menu.exec(tbl.viewport().mapToGlobal(pos))
        if action is None: return
        
        if action == action_open_loc: self.open_file_explorer(clicked_file_path)
        elif action == action_view_image:
            if sys.platform == 'win32': os.startfile(clicked_file_path)
            elif sys.platform == 'darwin': subprocess.run(['open', clicked_file_path])
            else: subprocess.run(['xdg-open', clicked_file_path])
        elif action == action_compare_img:
            orig_img, ext_img = pairs["image"]
            dialog = ImageComparisonDialog(orig_img, ext_img, self)
            dialog.exec()
        elif action == action_listen_audio:
            if sys.platform == 'win32': os.startfile(clicked_file_path)
            elif sys.platform == 'darwin': subprocess.run(['open', clicked_file_path])
            else: subprocess.run(['xdg-open', clicked_file_path])
    #endregion

# ---------------- Main ----------------
def main():
    """Initializes the QApplication, creates the main window, and starts the event loop."""
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

# Ensures the main function is called only when the script is executed directly.
if __name__ == "__main__":
    main()