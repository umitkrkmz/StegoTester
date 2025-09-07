# chart_dialog.py
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QComboBox
)
# For Matplotlib integration
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class MplCanvas(FigureCanvas):
    """A basic canvas widget for a Matplotlib figure."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class ChartDialog(QDialog):
    """A dialog window containing a Matplotlib plot to visualize results."""
    def __init__(self, data_rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Metric Visualization")
        self.setMinimumSize(800, 600)
        self.data = data_rows

        # Main layout
        layout = QVBoxLayout(self)

        # Matplotlib canvas for the plot
        self.canvas = MplCanvas(self, width=8, height=6, dpi=100)
        
        # ComboBox for metric selection
        self.metric_selector = QComboBox()
        
        # Add widgets to the layout
        layout.addWidget(self.metric_selector)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # Populate the ComboBox and connect its signal
        self.populate_metrics()
        self.metric_selector.currentTextChanged.connect(self.update_plot)

        # Draw the initial plot
        self.update_plot()

    def get_available_metrics(self):
        """Finds all calculated metric keys."""
        keys = set()
        for row in self.data:
            keys.update((row.get("metrics") or {}).keys())
        return sorted(list(keys))

    def populate_metrics(self):
        """Populates the ComboBox for metric selection."""
        metrics = self.get_available_metrics()
        self.metric_selector.addItems(metrics)

    def update_plot(self):
        """Updates the plot according to the selected metric."""
        selected_metric = self.metric_selector.currentText()
        if not selected_metric or not self.data:
            return

        # Prepare data for the plot
        labels = []  # X-axis labels (IDs)
        values = []  # Y-axis values

        for row in self.data:
            metric_val = row.get("metrics", {}).get(selected_metric)
            if metric_val is not None:
                try:
                    # Only add numeric values to the plot
                    values.append(float(metric_val))
                    labels.append(f"ID {row.get('id', '?')}")
                except (ValueError, TypeError):
                    # Skip non-numeric values (e.g., True/False)
                    continue

        # Clear the current plot
        self.canvas.axes.cla()
        
        if not values:
            self.canvas.axes.text(0.5, 0.5, 'No numeric data to display for this metric.', 
                                  horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return

        # Draw the new bar chart
        self.canvas.axes.bar(labels, values)
        self.canvas.axes.set_title(f"Comparison for: {selected_metric}")
        self.canvas.axes.set_ylabel("Value")
        self.canvas.axes.set_xlabel("Test ID")
        self.canvas.figure.tight_layout() # Adjust layout
        
        # Redraw the canvas
        self.canvas.draw()