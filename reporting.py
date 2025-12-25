# reporting.py
# Advanced Reporting Module with Executive Summary, Risk Charts, and Professional Styling.
# Updated for v3.1 Hybrid AI Engine

from pathlib import Path
from fpdf import FPDF
import json
import csv
import math
import io
import tempfile
import os
from datetime import datetime

# --- Matplotlib Configuration ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Import helper
from utils import fmt_val

# --- CONSTANTS FOR RISK LEVELS (v3.1 Calibrated) ---
# We observed that AI models could give approximately 60% natural "False Positives" in complex images like "Baboon".
# Therefore, we adjusted the thresholds.
RISK_HIGH_THRESH = 0.80  # 80% and above guaranteed STEGO
RISK_MED_THRESH = 0.50   # 50% - 80% SUSPICIOUS (or very complex tissue)

def get_risk_level(score):
    """Returns (Level Name, Color Tuple RGB) based on score."""
    try:
        s = float(score)
        if s >= RISK_HIGH_THRESH:
            return "CRITICAL / STEGO", (220, 53, 69) # Red
        elif s >= RISK_MED_THRESH:
            return "SUSPICIOUS / COMPLEX", (255, 140, 0) # Dark Orange
        else:
            return "SAFE / CLEAN", (40, 167, 69) # Green
    except:
        return "N/A", (128, 128, 128) # Grey

def generate_risk_pie_chart(data_rows):
    """Generates a Pie Chart showing the distribution of Risk Levels."""
    stats = {"Safe": 0, "Suspicious": 0, "Critical": 0, "N/A": 0}
    
    has_data = False
    for row in data_rows:
        metrics = row.get("metrics", {})
        # Check image or audio detection score
        score = metrics.get("image_ai_detection") or metrics.get("audio_ai_detection")
        
        if score is not None:
            has_data = True
            try:
                s = float(score)
                if s >= RISK_HIGH_THRESH: stats["Critical"] += 1
                elif s >= RISK_MED_THRESH: stats["Suspicious"] += 1
                else: stats["Safe"] += 1
            except:
                stats["N/A"] += 1
        else:
            stats["N/A"] += 1

    if not has_data:
        return None

    # Filter out zero values for cleaner chart
    labels = [k for k, v in stats.items() if v > 0]
    sizes = [stats[k] for k in labels]
    colors = []
    for l in labels:
        if l == "Safe": colors.append('#28a745')
        elif l == "Suspicious": colors.append('#ff8c00')
        elif l == "Critical": colors.append('#dc3545')
        else: colors.append('#6c757d')

    fig, ax = plt.subplots(figsize=(6, 4))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                      startangle=90, colors=colors, textprops=dict(color="black"))
    ax.axis('equal') 
    plt.title("AI Detection Distribution", fontsize=12, fontweight='bold')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'StegoTester v3.1 Analysis Report', 0, 1, 'C') # Version Updated
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")} | Engine: Hybrid AI', 0, 1, 'C')
        self.ln(5)
        self.line(10, 25, 200, 25)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} - StegoTester Pro', 0, 0, 'C')

def save_pdf_table(data_rows: list[dict], path: str, timestamp: str):
    """
    Generates a Professional PDF Report with Executive Summary and Risk Analysis.
    """
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: EXECUTIVE SUMMARY ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Executive Summary", ln=True)
    pdf.ln(5)
    
    # 1. Embed Risk Chart (Pie Chart)
    pie_buf = generate_risk_pie_chart(data_rows)
    if pie_buf:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(pie_buf.read())
            tmp_path = tmp.name
        
        # Center image
        x_pos = (pdf.w - 120) / 2
        pdf.image(tmp_path, x=x_pos, w=120)
        pdf.ln(5)
        os.unlink(tmp_path)
    
    # 2. General Stats Table
    total_tests = len(data_rows)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, f"Total Tests Conducted: {total_tests}", ln=True, align='C')
    pdf.ln(5)
    
    # 3. Methodology Note (New in v3.1)
    pdf.set_font("Arial", 'I', 9)
    pdf.multi_cell(0, 5, "Methodology Note: This report uses a Hybrid Detection Engine. "
                         "Audio files are first screened by a mathematical 'Gatekeeper' (LSB Transition Rate). "
                         "Files passing this check, and all images, are analyzed by trained Machine Learning models. "
                         "Scores between 0.50-0.80 may indicate high textural complexity rather than hidden data.")
    pdf.ln(10)

    # --- PAGE 2+: DETAILED FINDINGS ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Detailed Test Results", ln=True)
    pdf.ln(5)

    for row in data_rows:
        test_id = row.get('id', '?')
        metrics = row.get("metrics", {}) or {}
        pairs = row.get("pairs", {}) or {}
        
        # Determine Risk Level for this specific row
        ai_score = metrics.get("image_ai_detection") or metrics.get("audio_ai_detection")
        risk_label, risk_color = get_risk_level(ai_score) if ai_score is not None else ("NOT ANALYZED", (100,100,100))

        # --- Test Card Header ---
        pdf.set_fill_color(240, 240, 240)
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(pdf.get_x(), pdf.get_y(), 190, 8, 'F')
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(20, 8, f"ID: {test_id}", border=0)
        
        # Draw Risk Badge
        pdf.set_font("Arial", 'B', 10)
        pdf.set_text_color(*risk_color)
        
        # Format Score Percentage
        score_str = f"({float(ai_score)*100:.1f}%)" if ai_score is not None else ""
        pdf.cell(0, 8, f"VERDICT: {risk_label} {score_str}", border=0, align='R', ln=True)
        pdf.set_text_color(0, 0, 0) # Reset to black
        
        # --- File Info Section ---
        pdf.set_font("Arial", '', 9)
        
        type_prefix = ""
        # Audio
        if "audio" in pairs:
            type_prefix = "audio"
            orig = Path(pairs["audio"][0]).name
            cand = Path(pairs["audio"][1]).name
            pdf.cell(95, 6, f"Orig: {orig[:40]}", border='B')
            pdf.cell(95, 6, f"Cand: {cand[:40]}", border='B', ln=True)
        # Image
        elif "image" in pairs:
            type_prefix = "image"
            orig = Path(pairs["image"][0]).name
            cand = Path(pairs["image"][1]).name
            pdf.cell(95, 6, f"Orig: {orig[:40]}", border='B')
            pdf.cell(95, 6, f"Cand: {cand[:40]}", border='B', ln=True)
        # Text
        elif "text" in pairs:
            type_prefix = "text"
            orig = Path(pairs["text"][0]).name
            cand = Path(pairs["text"][1]).name
            pdf.cell(95, 6, f"Orig: {orig[:40]}", border='B')
            pdf.cell(95, 6, f"Cand: {cand[:40]}", border='B', ln=True)

        pdf.ln(2)

        # --- Metrics Grid ---
        metric_keys = sorted(metrics.keys())
        col_width = 63
        
        pdf.set_font("Courier", '', 8) # Monospace
        
        count = 0
        for key in metric_keys:
            # Skip explicit AI keys in the grid as they are in the header, 
            # BUT keep them if you want to see the raw number.
            clean_key = key.replace("audio_", "").replace("image_", "").replace("text_", "").upper()
            
            # Highlight AI Detection in bold
            is_ai = "ai_detection" in key
            if is_ai: pdf.set_font("Courier", 'B', 8)
            
            val = fmt_val(metrics[key])
            pdf.cell(col_width, 5, f"{clean_key}: {val}", border=0)
            
            if is_ai: pdf.set_font("Courier", '', 8)
            
            count += 1
            if count % 3 == 0:
                pdf.ln()
        
        if count % 3 != 0: pdf.ln()
        
        pdf.ln(5) # Space between rows
        
        # Page break check
        if pdf.get_y() > 250:
            pdf.add_page()

    pdf.output(path)

# --- Standard Exports ---
def _get_all_metric_keys(data_rows: list[dict]) -> list[str]:
    keys = set()
    for row in data_rows: keys |= set((row.get("metrics") or {}).keys())
    return sorted(keys)

def save_txt_table(data_rows, path, timestamp):
    lines = [f"STEGANOGRAPHY REPORT v3.1 - {timestamp}", "="*60]
    for row in data_rows:
        lines.append(f"ID: {row.get('id')}")
        for k,v in row.get("metrics", {}).items(): lines.append(f"  {k}: {fmt_val(v)}")
        lines.append("-" * 20)
    Path(path).write_text("\n".join(lines), encoding="utf-8")

def save_json_table(data_rows, path, timestamp):
    def convert_infinities(obj):
        if isinstance(obj, dict): return {k: convert_infinities(v) for k, v in obj.items()}
        elif isinstance(obj, list): return [convert_infinities(elem) for elem in obj]
        elif isinstance(obj, float) and math.isinf(obj): return "Infinity" if obj > 0 else "-Infinity"
        else: return obj
    data = {"meta": {"timestamp": timestamp, "version": "3.1"}, "results": convert_infinities(data_rows)}
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def save_csv_table(data_rows, path, timestamp):
    if not data_rows: return
    metric_cols = _get_all_metric_keys(data_rows)
    headers = ["ID"] + [h.upper() for h in metric_cols]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in data_rows:
            vals = [str(row.get("id"))]
            for k in metric_cols: vals.append(fmt_val(row.get("metrics", {}).get(k, "")))
            writer.writerow(vals)