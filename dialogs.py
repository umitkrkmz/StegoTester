# dialogs.py
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent, QFont
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel

class BeforeAfterWidget(QWidget):
    """
    Comparison widget with Aspect Ratio preservation and Interactive Slider.
    """
    def __init__(self, img_path1, img_path2, parent=None):
        super().__init__(parent)
        # Load images
        self.pixmap1 = QPixmap(img_path1) # Original (Left)
        self.pixmap2 = QPixmap(img_path2) # Candidate (Right)
        
        self.split_pos = 0.5 
        self.is_dragging = False
        
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 0. Clear Background (Dark Grey)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        
        w_widget = self.width()
        h_widget = self.height()
        
        # --- ASPECT RATIO CALCULATION ---
        # Get original image dimensions
        img_w = self.pixmap1.width()
        img_h = self.pixmap1.height()
        
        # Calculate scale factor to fit image within widget without distortion
        scale = min(w_widget / img_w, h_widget / img_h)
        
        # New drawing dimensions
        draw_w = int(img_w * scale)
        draw_h = int(img_h * scale)
        
        # Calculate X and Y offsets to center the image
        offset_x = (w_widget - draw_w) // 2
        offset_y = (h_widget - draw_h) // 2
        
        # The rectangle where the image will be drawn (Target Rect)
        target_rect = QRect(offset_x, offset_y, draw_w, draw_h)
        
        # 1. DRAW LEFT SIDE (Original)
        # Draw scaled version into target_rect
        painter.drawPixmap(target_rect, self.pixmap1)
        
        # 2. DRAW RIGHT SIDE (Candidate - Clipped)
        divider_x = int(w_widget * self.split_pos)
        
        # Clip Rect (Visible Area): From slider line to the right
        painter.setClipRect(divider_x, 0, w_widget - divider_x, h_widget)
        painter.drawPixmap(target_rect, self.pixmap2)
        painter.setClipping(False) # Remove mask
        
        # 3. DRAW SEPARATOR LINE
        # Drawing the line only over the image area looks cleaner
        line_top = offset_y
        line_bottom = offset_y + draw_h
        
        pen = QPen(QColor(255, 255, 255, 200))
        pen.setWidth(2)
        painter.setPen(pen)
        
        # Draw line only on the image, not the full screen
        if divider_x >= offset_x and divider_x <= (offset_x + draw_w):
            painter.drawLine(divider_x, line_top, divider_x, line_bottom)
        else:
             # If line is in the void/padding area, draw it faintly
            pen.setColor(QColor(255, 255, 255, 50))
            painter.setPen(pen)
            painter.drawLine(divider_x, 0, divider_x, h_widget)

        # 4. LABELS
        painter.setPen(QColor(255, 255, 255, 180)) # Slightly transparent white
        font = QFont("Arial", 9) 
        font.setBold(True)
        painter.setFont(font)
        
        # Place text inside the image, in the corners
        if divider_x > offset_x + 60: 
            painter.drawText(offset_x + 10, offset_y + 20, "Original")
            
        if w_widget - divider_x > (w_widget - (offset_x + draw_w)) + 70:
            # Align to right corner
            text_x = offset_x + draw_w - 70
            painter.drawText(text_x, offset_y + 20, "Candidate")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.update_split(event.pos().x())

    def mouseMoveEvent(self, event: QMouseEvent):
        w = self.width()
        divider_x = int(w * self.split_pos)
        
        # Change cursor if mouse is near the line
        if abs(event.pos().x() - divider_x) < 20 or self.is_dragging:
            self.setCursor(Qt.SplitHCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
            
        if self.is_dragging:
            self.update_split(event.pos().x())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False

    def update_split(self, x_pos):
        x_pos = max(0, min(x_pos, self.width()))
        self.split_pos = x_pos / self.width()
        self.update()


class ImageComparisonDialog(QDialog):
    """
    Window hosting the slider widget.
    """
    def __init__(self, img_path1, img_path2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Comparison (Before / After)")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background-color: #2b2b2b;") # Dialog background
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Info Bar
        lbl_info = QLabel("  ↔️ Drag the slider to compare images (Left: Original | Right: Stego/Extract)")
        lbl_info.setStyleSheet("background-color: #252526; color: #bbb; padding: 10px; border-bottom: 1px solid #3e3e42; font-size: 12px;")
        layout.addWidget(lbl_info)
        
        # Slider Widget
        self.slider_widget = BeforeAfterWidget(img_path1, img_path2)
        layout.addWidget(self.slider_widget)
        
        self.setLayout(layout)