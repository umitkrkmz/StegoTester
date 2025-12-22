# main.py
# Modernized Main Application with Audio AI Detection

import sys
import os
import subprocess
from datetime import datetime
import json
from pathlib import Path

# --- Qt Imports ---
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsOpacityEffect,
    QFileDialog, QMessageBox, QTableWidgetItem, QMenu, 
    QListWidgetItem, QVBoxLayout, QTabWidget, QTableWidget, QHeaderView, QCheckBox
)

# --- Local Module Imports ---
from ui_form import Ui_MainWindow
from utils import IMG_EXT, AUD_EXT, TXT_EXT, fmt_val, group_files_smart
from dialogs import ImageComparisonDialog
import reporting
from reporting import save_json_table, save_csv_table
from worker import MetricWorker, ReportWorker
from chart_dialog import ChartDialog
from droplist import DropList

# ---------------- THEME ENGINE ----------------
def set_scientific_green_theme(app):
    app.setStyle("Fusion")
    dark_bg = QColor("#2b2b2b")
    text_color = QColor("#e0e0e0")
    accent_color = QColor("#4caf50")
    btn_bg = QColor("#3c3f41")
    btn_hover = QColor("#45494b")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, dark_bg)
    palette.setColor(QPalette.WindowText, text_color)
    palette.setColor(QPalette.Base, QColor("#1e1e1e"))
    palette.setColor(QPalette.AlternateBase, dark_bg)
    palette.setColor(QPalette.ToolTipBase, text_color)
    palette.setColor(QPalette.ToolTipText, dark_bg)
    palette.setColor(QPalette.Text, text_color)
    palette.setColor(QPalette.Button, btn_bg)
    palette.setColor(QPalette.ButtonText, text_color)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, accent_color)
    palette.setColor(QPalette.Highlight, accent_color)
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    app.setStyleSheet(f"""
        QMainWindow {{ background-color: {dark_bg.name()}; }}
        QGroupBox {{ border: 1px solid #555; border-radius: 4px; margin-top: 20px; font-weight: bold; color: #a5d6a7; }}
        QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; }}
        QPushButton {{ background-color: {btn_bg.name()}; border: 1px solid #555; border-radius: 3px; padding: 5px; color: #fff; }}
        QPushButton:hover {{ background-color: {btn_hover.name()}; border: 1px solid {accent_color.name()}; }}
        QPushButton:pressed {{ background-color: {accent_color.name()}; color: #000; }}
        QPushButton:disabled {{ background-color: #2b2b2b; color: #777; border: 1px solid #444; }}
        QTabWidget::pane {{ border: 1px solid #444; top: -1px; }}
        QTabBar::tab {{ background: #3c3f41; border: 1px solid #444; padding: 6px 12px; margin-right: 2px; color: #bbb; }}
        QTabBar::tab:selected {{ background: #2b2b2b; border-bottom-color: {accent_color.name()}; color: {accent_color.name()}; font-weight: bold; }}
        QHeaderView::section {{ background-color: #3c3f41; color: #fff; padding: 4px; border: 1px solid #444; }}
        QTableWidget {{ gridline-color: #444; selection-background-color: {accent_color.name()}; selection-color: #000; }}
        QProgressBar {{ border: 1px solid #444; border-radius: 3px; text-align: center; background-color: #1e1e1e; }}
        QProgressBar::chunk {{ background-color: {accent_color.name()}; width: 10px; }}
        QLineEdit, QListWidget {{ border: 1px solid #444; background-color: #1e1e1e; color: #fff; border-radius: 2px; }}
    """)

# ---------------- MainWindow ----------------
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.last_data_rows: list[dict] = []
              
        # 1. UI MODERNIZATION
        self.ui.tbl_results.setVisible(False)
        self.results_layout = QVBoxLayout(self.ui.tab_2)
        self.res_tabs = QTabWidget()
        self.results_layout.addWidget(self.res_tabs)
        
        self.tbl_image = QTableWidget()
        self.tbl_audio = QTableWidget()
        self.tbl_text  = QTableWidget()
        
        self.res_tabs.addTab(self.tbl_image, "Image Results")
        self.res_tabs.addTab(self.tbl_audio, "Audio Results")
        self.res_tabs.addTab(self.tbl_text,  "Text Results")
        
        for t in [self.tbl_image, self.tbl_audio, self.tbl_text]:
            t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            t.setContextMenuPolicy(Qt.CustomContextMenu)
            t.customContextMenuRequested.connect(self.on_results_context_menu)
            font = t.font()
            font.setPointSize(9)
            t.setFont(font)

        
        # 2. INITIAL SETTINGS
        self.ui.progressBar.hide()
        

        self.set_group_state(self.ui.grb_audio_metrics, False)
        self.set_group_state(self.ui.grb_image_metrics, False)
        self.set_group_state(self.ui.grb_text_metrics, False)

        self.ui.lst_original.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_stego.filesChanged.connect(self.update_metrics_availability)
        self.ui.lst_extract.filesChanged.connect(self.update_metrics_availability)

        all_exts = IMG_EXT | AUD_EXT | TXT_EXT
        self.ui.lst_original.allowed_ext = all_exts
        self.ui.lst_stego.allowed_ext = all_exts
        self.ui.lst_extract.allowed_ext = all_exts

        self.ui.btn_export_report.clicked.connect(self.on_export_report)
        self.ui.btn_compute.clicked.connect(self.start_metric_calculation)
        self.ui.btn_save_profile.clicked.connect(self.save_profile)
        self.ui.btn_load_profile.clicked.connect(self.load_profile)
        self.ui.btn_generate_chart.clicked.connect(self.on_generate_chart)
        self.ui.btn_add_folder_original.clicked.connect(lambda: self.add_files_from_folder(self.ui.lst_original))
        self.ui.btn_add_folder_stego.clicked.connect(lambda: self.add_files_from_folder(self.ui.lst_stego))
        self.ui.btn_add_folder_extract.clicked.connect(lambda: self.add_files_from_folder(self.ui.lst_extract))

    #region --- UI helpers ---
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
            if suffix: exts.add(suffix)
        return exts

    def any_ext_in(self, exts: set[str], pool: set[str]) -> bool:
        return any(e in pool for e in exts)

    def update_metrics_availability(self):
        exts_all = (self.list_file_exts(self.ui.lst_original) | self.list_file_exts(self.ui.lst_stego) | self.list_file_exts(self.ui.lst_extract))
        self.set_group_state(self.ui.grb_image_metrics, self.any_ext_in(exts_all, IMG_EXT))
        self.set_group_state(self.ui.grb_audio_metrics, self.any_ext_in(exts_all, AUD_EXT))
        self.set_group_state(self.ui.grb_text_metrics, self.any_ext_in(exts_all, TXT_EXT))
    
    def add_files_from_folder(self, list_widget: DropList):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder_path: return
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
        if added_count > 0: list_widget.filesChanged.emit()
    #endregion
    
    #region --- Metric Selection ---
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
        
        if self.ui.chk_aud_ai.isChecked(): sel["audio"].append("ai_detection") # Audio AI

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
        
        if self.ui.chk_img_ai.isChecked(): sel["image"].append("ai_detection") # Image AI
        
        # Text
        if self.ui.chk_text_similarity.isChecked(): sel["text"].append("similarity")
        if self.ui.chk_text_levenshtein.isChecked(): sel["text"].append("levenshtein")
        if self.ui.chk_text_jaccard.isChecked(): sel["text"].append("jaccard")
        if self.ui.chk_text_exact_match.isChecked(): sel["text"].append("exact_match")
        if self.ui.chk_text_char_accuracy.isChecked(): sel["text"].append("char_accuracy")
        if self.ui.chk_text_bitwise_ber.isChecked(): sel["text"].append("bitwise_ber")
        return sel

    def save_profile(self):
        selected_metrics = self.get_selected_metrics()
        filePath, _ = QFileDialog.getSaveFileName(self, "Save Profile", "metric_profile.json", "JSON Files (*.json)")
        if filePath:
            try:
                with open(filePath, 'w', encoding='utf-8') as f: json.dump(selected_metrics, f, indent=4)
                QMessageBox.information(self, "Success", f"Profile saved to:\n{filePath}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not save profile:\n{e}")
                
    def load_profile(self):
        filePath, _ = QFileDialog.getOpenFileName(self, "Load Profile", "", "JSON Files (*.json)")
        if filePath:
            try:
                with open(filePath, 'r', encoding='utf-8') as f: profile_data = json.load(f)
                self.apply_profile(profile_data)
                QMessageBox.information(self, "Success", "Profile loaded successfully.")
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not load profile:\n{e}")

    def apply_profile(self, profile: dict):
        audio_metrics = profile.get("audio", [])
        image_metrics = profile.get("image", [])
        text_metrics = profile.get("text", [])
        
        self.ui.chk_audio_mse.setChecked("mse" in audio_metrics)
        self.ui.chk_audio_psnr.setChecked("psnr" in audio_metrics)
        self.ui.chk_audio_snr.setChecked("snr" in audio_metrics)
        self.ui.chk_audio_mae.setChecked("mae" in audio_metrics)
        self.ui.chk_audio_lsd.setChecked("lsd" in audio_metrics)
        self.ui.chk_audio_perceptual_score.setChecked("perceptual_score" in audio_metrics)
        self.ui.chk_audio_bitwise_ber.setChecked("bitwise_ber" in audio_metrics)
        self.ui.chk_audio_byte_accuracy.setChecked("byte_accuracy" in audio_metrics)
        self.ui.chk_audio_exact_match.setChecked("exact_match" in audio_metrics)
        self.ui.chk_aud_ai.setChecked("ai_detection" in audio_metrics)
        
        self.ui.chk_image_mse.setChecked("mse" in image_metrics)
        self.ui.chk_image_psnr.setChecked("psnr" in image_metrics)
        self.ui.chk_image_ssim.setChecked("ssim" in image_metrics)
        self.ui.chk_image_ber.setChecked("ber" in image_metrics)
        self.ui.chk_image_dssim.setChecked("image_dssim" in image_metrics)
        self.ui.chk_image_lpips.setChecked("image_lpips" in image_metrics)
        self.ui.chk_image_bitwise_ber.setChecked("bitwise_ber" in image_metrics)
        self.ui.chk_image_byte_accuracy.setChecked("byte_accuracy" in image_metrics)
        self.ui.chk_image_exact_match.setChecked("exact_match" in image_metrics)
        self.ui.chk_img_ai.setChecked("ai_detection" in image_metrics)
        
        self.ui.chk_text_similarity.setChecked("similarity" in text_metrics)
        self.ui.chk_text_levenshtein.setChecked("levenshtein" in text_metrics)
        self.ui.chk_text_jaccard.setChecked("jaccard" in text_metrics)
        self.ui.chk_text_exact_match.setChecked("exact_match" in text_metrics)
        self.ui.chk_text_char_accuracy.setChecked("char_accuracy" in text_metrics)
        self.ui.chk_text_bitwise_ber.setChecked("bitwise_ber" in text_metrics)
    #endregion
    
    #region --- Calculation & Results ---
    def start_metric_calculation(self):
        metrics = self.get_selected_metrics()
        has_any_metric = any(len(v) > 0 for v in metrics.values())
        if not has_any_metric:
            QMessageBox.warning(self, "Warning", "Please select at least one metric.")
            return

        originals = self.list_file_paths(self.ui.lst_original)
        stegos = self.list_file_paths(self.ui.lst_stego)
        extracts = self.list_file_paths(self.ui.lst_extract)
        
        try:
            refs, groups = group_files_smart(originals, stegos, extracts)
            if not groups:
                QMessageBox.information(self, "No Matches", "No matching files found based on content (Hash/Fingerprint) or name.")
                return
        except Exception as e:
            QMessageBox.critical(self, "File Matching Error", f"Could not group files.\n\nError: {e}")
            return

        self.ui.btn_compute.setEnabled(False)
        self.ui.btn_generate_chart.setEnabled(False)
        self.ui.progressBar.show()
        self.ui.progressBar.setValue(0)

        self.thread = QThread()
        self.worker = MetricWorker(refs, groups, metrics)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_calculation_finished)
        self.worker.error.connect(self.on_calculation_error)
        self.worker.progress.connect(self.ui.progressBar.setValue)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_calculation_finished(self, data_rows):
        self.ui.progressBar.hide()
        self.ui.btn_compute.setEnabled(True)
        self.ui.btn_generate_chart.setEnabled(True)
        
        try: data_rows.sort(key=lambda x: int(x['id']))
        except: data_rows.sort(key=lambda x: str(x['id']))

        self.last_data_rows = data_rows
        self.populate_results_table(data_rows)
        self.ui.tabWidget.setCurrentIndex(1)
        QMessageBox.information(self, "Done", "Calculation complete.")

    def on_calculation_error(self, error_message):
        self.ui.progressBar.hide()
        self.ui.btn_compute.setEnabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")

    def populate_results_table(self, data_rows: list[dict]):
        img_rows, aud_rows, txt_rows = [], [], []
        for row in data_rows:
            pairs = row.get("pairs", {})
            if "image" in pairs: img_rows.append(row)
            if "audio" in pairs: aud_rows.append(row)
            if "text"  in pairs: txt_rows.append(row)
                
        self._fill_table(self.tbl_image, img_rows, "image")
        self._fill_table(self.tbl_audio, aud_rows, "audio")
        self._fill_table(self.tbl_text,  txt_rows, "text")

        if img_rows: self.res_tabs.setCurrentIndex(0)
        elif aud_rows: self.res_tabs.setCurrentIndex(1)
        elif txt_rows: self.res_tabs.setCurrentIndex(2)

    def _fill_table(self, table_widget: QTableWidget, rows: list, data_type: str):
        table_widget.setRowCount(0)
        if not rows: return
            
        metric_keys = set()
        for r in rows: metric_keys.update(r.get("metrics", {}).keys())
        
        relevant_metrics = sorted([k for k in metric_keys if k.startswith(f"{data_type}_")])
        headers = ["ID", "Original", "Candidate"] + [m.replace(f"{data_type}_", "").upper() for m in relevant_metrics]
        
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        table_widget.setRowCount(len(rows))
        
        for r_idx, row_data in enumerate(rows):
            table_widget.setItem(r_idx, 0, QTableWidgetItem(str(row_data.get("id", "?"))))
            pairs = row_data.get("pairs", {}).get(data_type, ("-", "-"))
            orig_name = Path(pairs[0]).name
            cand_name = Path(pairs[1]).name
            table_widget.setItem(r_idx, 1, QTableWidgetItem(orig_name))
            table_widget.setItem(r_idx, 2, QTableWidgetItem(cand_name))
            metrics = row_data.get("metrics", {})
            for c_idx, m_key in enumerate(relevant_metrics):
                val = fmt_val(metrics.get(m_key, ""))
                table_widget.setItem(r_idx, 3 + c_idx, QTableWidgetItem(val))
                
        table_widget.resizeColumnsToContents()
         
    def on_generate_chart(self):
        if not self.last_data_rows:
            QMessageBox.warning(self, "Generate Chart", "Please compute metrics first.")
            return
        dialog = ChartDialog(self.last_data_rows, self)
        dialog.exec()
    #endregion
    
    #region --- Exporting ---
    def on_export_report(self):
        if not self.last_data_rows:
            QMessageBox.warning(self, "Export", "Please run the metrics first.")
            return

        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(self, "Save Report", f"metrics_{filename_ts}", "PDF Files (*.pdf);;JSON Files (*.json)")

        if not path: return 
        self.ui.centralwidget.setEnabled(False)
        self.ui.progressBar.show()
        self.report_thread = QThread()
        self.report_worker = ReportWorker(self.last_data_rows, path, ts_str)
        self.report_worker.moveToThread(self.report_thread)
        self.report_thread.started.connect(self.report_worker.run)
        self.report_worker.finished.connect(self.on_report_finished)
        self.report_worker.error.connect(self.on_report_error)
        self.report_worker.finished.connect(self.report_thread.quit)
        self.report_worker.finished.connect(self.report_worker.deleteLater)
        self.report_thread.finished.connect(self.report_thread.deleteLater)
        self.report_thread.start()
    
    def on_report_finished(self, path):
        self.ui.centralwidget.setEnabled(True) 
        self.ui.progressBar.hide()
        QMessageBox.information(self, "Saved", f"Report file saved to:\n{path}")

    def on_report_error(self, error_message):
        self.ui.centralwidget.setEnabled(True) 
        self.ui.progressBar.hide()
        QMessageBox.critical(self, "Export Error", str(error_message))
            
    def on_results_context_menu(self, pos):
        sender_widget = self.sender()
        if not isinstance(sender_widget, QTableWidget): return
        item = sender_widget.itemAt(pos)
        if not item: return
        row_idx = item.row()
        id_item = sender_widget.item(row_idx, 0)
        if not id_item: return
        test_id = id_item.text()
        target_row = next((r for r in self.last_data_rows if str(r['id']) == test_id), None)
        if not target_row: return
        menu = QMenu(self)
        pairs = target_row.get("pairs", {})
        if "image" in pairs:
            act_cmp = menu.addAction("Compare Images (Side-by-Side)")
            act_open_orig = menu.addAction(f"Open Original: {Path(pairs['image'][0]).name}")
            act_open_stego = menu.addAction(f"Open Candidate: {Path(pairs['image'][1]).name}")
            action = menu.exec(sender_widget.viewport().mapToGlobal(pos))
            if action == act_cmp: ImageComparisonDialog(pairs['image'][0], pairs['image'][1], self).exec()
            elif action == act_open_orig: self._open_file(pairs['image'][0])
            elif action == act_open_stego: self._open_file(pairs['image'][1])
        elif "audio" in pairs:
            act_play_orig = menu.addAction(f"Play Original: {Path(pairs['audio'][0]).name}")
            act_play_stego = menu.addAction(f"Play Candidate: {Path(pairs['audio'][1]).name}")
            action = menu.exec(sender_widget.viewport().mapToGlobal(pos))
            if action == act_play_orig: self._open_file(pairs['audio'][0])
            elif action == act_play_stego: self._open_file(pairs['audio'][1])

    def _open_file(self, path):
        if sys.platform == 'win32': os.startfile(path)
        elif sys.platform == 'darwin': subprocess.run(['open', path])
        else: subprocess.run(['xdg-open', path])
    #endregion

# ---------------- Main ----------------
def main():
    app = QApplication(sys.argv)
    set_scientific_green_theme(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()