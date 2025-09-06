# dialogs.py
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel

class ImageComparisonDialog(QDialog):
    """A simple dialog to display two images side-by-side."""
    def __init__(self, img_path1, img_path2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Comparison")
        self.setMinimumSize(800, 400)

        layout = QHBoxLayout(self)
        label1 = QLabel("Loading Image 1...")
        label2 = QLabel("Loading Image 2...")
        
        pixmap1 = QPixmap(img_path1)
        pixmap2 = QPixmap(img_path2)
        
        label1.setPixmap(pixmap1.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        label2.setPixmap(pixmap2.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        layout.addWidget(label1)
        layout.addWidget(label2)
        self.setLayout(layout)