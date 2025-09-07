# reporting.py
# This module contains all logic related to generating user-facing reports.
# It handles the creation of TXT, PDF, JSON, and CSV files, and also includes
# helper functions for creating matplotlib visualizations to be embedded in PDFs.

from pathlib import Path
from fpdf import FPDF
import json
import csv
import math
import io
import tempfile
import os

# --- Matplotlib Configuration ---
# This is the definitive fix for all backend-related errors ('startwish', etc.)
# It forces Matplotlib to use a non-GUI backend.
# MUST be done before importing pyplot.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Import the helper function from our new utils module
from utils import fmt_val

def generate_metric_plot(data_rows: list[dict], metric_key: str):
    """
    Creates a bar chart for the given metric and returns it as an in-memory PNG buffer.
    """
    labels, values = [], []
    for row in data_rows:
        metric_val = row.get("metrics", {}).get(metric_key)
        if metric_val is not None:
            try:
                values.append(float(metric_val))
                labels.append(f"ID {row.get('id', '?')}")
            except (ValueError, TypeError):
                continue
    
    if not values:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(labels, values)
    ax.set_title(f"Comparison for: {metric_key}", fontsize=14)
    ax.set_ylabel("Value", fontsize=10)
    ax.set_xlabel("Test ID", fontsize=10)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def save_pdf_table(data_rows: list[dict], path: str, timestamp: str):
    """Saves the results to a professional, multi-page PDF report."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- PART 1: DETAILED PAGES FOR EACH ID ---
    for row in data_rows:
        pdf.add_page()
        # ... (ID, File Info, and Metric Table for each ID) ...
        # This part remains the same as the previous version.
        # (The full code is included below for completeness)
        metrics = row.get("metrics", {}) or {}
        pairs   = row.get("pairs", {}) or {}
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, f"Detailed Report for Test ID: {row.get('id','?')}", ln=True)
        pdf.ln(5)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 8, "File Information", ln=True)
        audio_ref, audio_cmp = map(lambda p: Path(p).name, pairs.get("audio", ("-", "-")))
        image_ref, image_cmp = map(lambda p: Path(p).name, pairs.get("image", ("-", "-")))
        text_ref,  text_cmp  = map(lambda p: Path(p).name, pairs.get("text", ("-", "-")))
        pdf.set_font("Helvetica", '', 10)
        if audio_ref != "-": pdf.cell(0, 6, f"  Original Audio:   {audio_ref}", ln=True)
        if audio_cmp != "-": pdf.cell(0, 6, f"  Stego Audio:      {audio_cmp}", ln=True)
        if image_ref != "-": pdf.cell(0, 6, f"  Original Image:   {image_ref}", ln=True)
        if image_cmp != "-": pdf.cell(0, 6, f"  Extracted Image:  {image_cmp}", ln=True)
        if text_ref  != "-": pdf.cell(0, 6, f"  Original Text:    {text_ref}", ln=True)
        if text_cmp  != "-": pdf.cell(0, 6, f"  Extracted Text:   {text_cmp}", ln=True)
        pdf.ln(8)
        metric_keys = sorted(metrics.keys())
        if metric_keys:
            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(0, 8, "Metric Results", ln=True)
            pdf.set_fill_color(230, 230, 230)
            pdf.set_draw_color(150, 150, 150)
            pdf.set_font("Helvetica", 'B', 10)
            available_width = pdf.w - pdf.l_margin - pdf.r_margin
            metric_col_width = available_width * 0.7
            value_col_width = available_width * 0.3
            pdf.cell(metric_col_width, 8, "Metric", border=1, fill=True, align='C')
            pdf.cell(value_col_width, 8, "Value", border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font("Helvetica", '', 9)
            for key in metric_keys:
                metric_label = key.replace("_", " ").title()
                pdf.cell(metric_col_width, 8, f"  {metric_label}", border=1, align='L')
                pdf.cell(value_col_width, 8, fmt_val(metrics.get(key, "")), border=1, align='R')
                pdf.ln()
        else:
            pdf.set_font("Helvetica", 'I', 10)
            pdf.cell(0, 6, "(No metrics calculated for this ID)", ln=True)

    # --- PART 2: SUMMARY VISUALIZATIONS ---
    all_metrics = _get_all_metric_keys(data_rows)
    if all_metrics:
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, "Summary Visualizations", ln=True, align="C")
        pdf.ln(10)

        MAX_IDS_PER_CHART = 15 
        for metric_key in all_metrics:
            for i in range(0, len(data_rows), MAX_IDS_PER_CHART):
                chunk_data = data_rows[i:i + MAX_IDS_PER_CHART]
                plot_buffer = generate_metric_plot(chunk_data, metric_key)
                
                if plot_buffer:
                    # This is the definitive fix for 'startswith' and 'rfind' errors.
                    # We save the plot to a temporary file and pass the file path to fpdf.
                    temp_img_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                            temp_img.write(plot_buffer.read())
                            temp_img_path = temp_img.name
                        
                        pdf.set_font("Helvetica", 'B', 12)
                        chart_title = f"Chart for {metric_key}"
                        if len(data_rows) > MAX_IDS_PER_CHART:
                            start_id = chunk_data[0].get('id', '?')
                            end_id = chunk_data[-1].get('id', '?')
                            chart_title += f" (IDs {start_id}-{end_id})"
                        
                        pdf.cell(0, 10, chart_title, ln=True)
                        
                        img_width = pdf.w - pdf.l_margin - pdf.r_margin
                        pdf.image(temp_img_path, w=img_width) # Pass the file path
                        pdf.ln(10)
                        
                    finally:
                        if temp_img_path and os.path.exists(temp_img_path):
                            os.unlink(temp_img_path) # Clean up the temporary file
            
    pdf.output(path)

# Add other reporting functions back in
def _get_all_metric_keys(data_rows: list[dict]) -> list[str]:
    keys = set()
    for row in data_rows:
        keys |= set((row.get("metrics") or {}).keys())
    return sorted(keys)
    
    
def save_txt_table(data_rows: list[dict], path: str, timestamp: str):
    """Saves the results to a plain text file with an aligned table."""
    lines = []
    lines.append("STEGANOGRAPHY METRICS REPORT")
    lines.append(f"Generated on: {timestamp}")
    lines.append("=" * 80)

    if not data_rows:
        lines.append("No data to report.")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        return

    # --- Prepare Table Headers and Data ---
    metric_cols = _get_all_metric_keys(data_rows)
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
    
    
def save_json_table(data_rows: list[dict], path: str, timestamp: str):
    def convert_infinities(obj):
        if isinstance(obj, dict): return {k: convert_infinities(v) for k, v in obj.items()}
        elif isinstance(obj, list): return [convert_infinities(elem) for elem in obj]
        elif isinstance(obj, float) and math.isinf(obj): return "Infinity" if obj > 0 else "-Infinity"
        else: return obj
    cleaned_data_rows = convert_infinities(data_rows)
    report_data = {"report_info": {"title": "Steganography Metrics Report", "generated_on": timestamp}, "results": cleaned_data_rows}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=4)
        
        

def save_csv_table(data_rows: list[dict], path: str, timestamp: str):
    """Saves the results to a CSV file."""
    if not data_rows:
        return

    # Dynamically specify CSV headers and columns
    metric_cols = _get_all_metric_keys(data_rows)
    file_cols = []
    has_audio = any("audio" in row.get("pairs", {}) for row in data_rows)
    has_image = any("image" in row.get("pairs", {}) for row in data_rows)
    has_text = any("text" in row.get("pairs", {}) for row in data_rows)

    if has_audio: file_cols += ["Orig_Audio", "Stego_Audio"]
    if has_image: file_cols += ["Orig_Image", "Extract_Image"]
    if has_text: file_cols += ["Orig_Text", "Extract_Text"]

    headers = ["ID"] + file_cols + [h.upper() for h in metric_cols]

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers) # Write the title line

        # Write rows of data
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
            
            writer.writerow(row_vals)