# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 6.7.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QGroupBox, QHeaderView,
    QListWidgetItem, QMainWindow, QPushButton, QRadioButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QWidget)

from droplist import DropList

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(911, 383)
        MainWindow.setStyleSheet(u"")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.grb_original = QGroupBox(self.centralwidget)
        self.grb_original.setObjectName(u"grb_original")
        self.grb_original.setGeometry(QRect(10, 20, 191, 141))
        self.lst_original = DropList(self.grb_original)
        self.lst_original.setObjectName(u"lst_original")
        self.lst_original.setGeometry(QRect(10, 20, 171, 111))
        self.grb_extract = QGroupBox(self.centralwidget)
        self.grb_extract.setObjectName(u"grb_extract")
        self.grb_extract.setGeometry(QRect(410, 20, 191, 141))
        self.lst_extract = DropList(self.grb_extract)
        self.lst_extract.setObjectName(u"lst_extract")
        self.lst_extract.setGeometry(QRect(10, 20, 171, 111))
        self.grb_stego = QGroupBox(self.centralwidget)
        self.grb_stego.setObjectName(u"grb_stego")
        self.grb_stego.setGeometry(QRect(210, 20, 191, 141))
        self.lst_stego = DropList(self.grb_stego)
        self.lst_stego.setObjectName(u"lst_stego")
        self.lst_stego.setGeometry(QRect(10, 20, 171, 111))
        self.grb_audio_metrics = QGroupBox(self.centralwidget)
        self.grb_audio_metrics.setObjectName(u"grb_audio_metrics")
        self.grb_audio_metrics.setGeometry(QRect(760, 20, 131, 141))
        self.chk_audio_mse = QCheckBox(self.grb_audio_metrics)
        self.chk_audio_mse.setObjectName(u"chk_audio_mse")
        self.chk_audio_mse.setGeometry(QRect(10, 20, 81, 21))
        self.chk_audio_psnr = QCheckBox(self.grb_audio_metrics)
        self.chk_audio_psnr.setObjectName(u"chk_audio_psnr")
        self.chk_audio_psnr.setGeometry(QRect(10, 50, 81, 21))
        self.chk_audio_snr = QCheckBox(self.grb_audio_metrics)
        self.chk_audio_snr.setObjectName(u"chk_audio_snr")
        self.chk_audio_snr.setGeometry(QRect(10, 80, 81, 21))
        self.grb_text_metrics = QGroupBox(self.centralwidget)
        self.grb_text_metrics.setObjectName(u"grb_text_metrics")
        self.grb_text_metrics.setGeometry(QRect(610, 20, 141, 141))
        self.chk_text_similarity = QCheckBox(self.grb_text_metrics)
        self.chk_text_similarity.setObjectName(u"chk_text_similarity")
        self.chk_text_similarity.setGeometry(QRect(10, 20, 91, 21))
        self.chk_text_levenshtein = QCheckBox(self.grb_text_metrics)
        self.chk_text_levenshtein.setObjectName(u"chk_text_levenshtein")
        self.chk_text_levenshtein.setGeometry(QRect(10, 50, 91, 21))
        self.chk_text_jaccard = QCheckBox(self.grb_text_metrics)
        self.chk_text_jaccard.setObjectName(u"chk_text_jaccard")
        self.chk_text_jaccard.setGeometry(QRect(10, 80, 81, 21))
        self.grb_image_metrics = QGroupBox(self.centralwidget)
        self.grb_image_metrics.setObjectName(u"grb_image_metrics")
        self.grb_image_metrics.setGeometry(QRect(610, 170, 141, 141))
        self.chk_image_mse = QCheckBox(self.grb_image_metrics)
        self.chk_image_mse.setObjectName(u"chk_image_mse")
        self.chk_image_mse.setGeometry(QRect(10, 20, 81, 21))
        self.chk_image_psnr = QCheckBox(self.grb_image_metrics)
        self.chk_image_psnr.setObjectName(u"chk_image_psnr")
        self.chk_image_psnr.setGeometry(QRect(10, 50, 71, 21))
        self.chk_image_ssim = QCheckBox(self.grb_image_metrics)
        self.chk_image_ssim.setObjectName(u"chk_image_ssim")
        self.chk_image_ssim.setGeometry(QRect(10, 80, 71, 21))
        self.chk_image_ber = QCheckBox(self.grb_image_metrics)
        self.chk_image_ber.setObjectName(u"chk_image_ber")
        self.chk_image_ber.setGeometry(QRect(10, 110, 71, 21))
        self.grb_export_format = QGroupBox(self.centralwidget)
        self.grb_export_format.setObjectName(u"grb_export_format")
        self.grb_export_format.setGeometry(QRect(760, 170, 131, 141))
        self.btn_export_report = QPushButton(self.grb_export_format)
        self.btn_export_report.setObjectName(u"btn_export_report")
        self.btn_export_report.setGeometry(QRect(10, 90, 111, 31))
        self.rdb_export_txt = QRadioButton(self.grb_export_format)
        self.rdb_export_txt.setObjectName(u"rdb_export_txt")
        self.rdb_export_txt.setGeometry(QRect(10, 30, 111, 21))
        self.rdb_export_pdf = QRadioButton(self.grb_export_format)
        self.rdb_export_pdf.setObjectName(u"rdb_export_pdf")
        self.rdb_export_pdf.setGeometry(QRect(10, 60, 89, 21))
        self.grb_results = QGroupBox(self.centralwidget)
        self.grb_results.setObjectName(u"grb_results")
        self.grb_results.setGeometry(QRect(10, 170, 591, 191))
        self.tbl_results = QTableWidget(self.grb_results)
        self.tbl_results.setObjectName(u"tbl_results")
        self.tbl_results.setGeometry(QRect(10, 20, 571, 161))
        self.btn_compute = QPushButton(self.centralwidget)
        self.btn_compute.setObjectName(u"btn_compute")
        self.btn_compute.setGeometry(QRect(690, 320, 141, 31))
        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"StegoTester", None))
        self.grb_original.setTitle(QCoreApplication.translate("MainWindow", u"Original", None))
        self.grb_extract.setTitle(QCoreApplication.translate("MainWindow", u"Extract", None))
        self.grb_stego.setTitle(QCoreApplication.translate("MainWindow", u"Stego", None))
        self.grb_audio_metrics.setTitle(QCoreApplication.translate("MainWindow", u"Audio Metrics", None))
        self.chk_audio_mse.setText(QCoreApplication.translate("MainWindow", u"MSE", None))
        self.chk_audio_psnr.setText(QCoreApplication.translate("MainWindow", u"PSNR", None))
        self.chk_audio_snr.setText(QCoreApplication.translate("MainWindow", u"SNR", None))
        self.grb_text_metrics.setTitle(QCoreApplication.translate("MainWindow", u"Text Metrics", None))
        self.chk_text_similarity.setText(QCoreApplication.translate("MainWindow", u"Similarity", None))
        self.chk_text_levenshtein.setText(QCoreApplication.translate("MainWindow", u"Levenshtein", None))
        self.chk_text_jaccard.setText(QCoreApplication.translate("MainWindow", u"Jaccard", None))
        self.grb_image_metrics.setTitle(QCoreApplication.translate("MainWindow", u"Image Metrics", None))
        self.chk_image_mse.setText(QCoreApplication.translate("MainWindow", u"MSE", None))
        self.chk_image_psnr.setText(QCoreApplication.translate("MainWindow", u"PSNR", None))
        self.chk_image_ssim.setText(QCoreApplication.translate("MainWindow", u"SSIM", None))
        self.chk_image_ber.setText(QCoreApplication.translate("MainWindow", u"BER", None))
        self.grb_export_format.setTitle(QCoreApplication.translate("MainWindow", u"Export format", None))
        self.btn_export_report.setText(QCoreApplication.translate("MainWindow", u"Export Reports", None))
        self.rdb_export_txt.setText(QCoreApplication.translate("MainWindow", u"Text Report (.txt)", None))
        self.rdb_export_pdf.setText(QCoreApplication.translate("MainWindow", u"PDF (.pdf)", None))
        self.grb_results.setTitle(QCoreApplication.translate("MainWindow", u"Results", None))
        self.btn_compute.setText(QCoreApplication.translate("MainWindow", u"Compute", None))
    # retranslateUi

