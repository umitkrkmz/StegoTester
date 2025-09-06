# reporting.py
# Contains all logic for generating TXT and PDF reports.

from pathlib import Path
from fpdf import FPDF

# Import the helper function from our new utils module
from utils import fmt_val

def _get_all_metric_keys(data_rows: list[dict]) -> list[str]:
    """Finds all unique metric keys present across all data rows."""
    keys = set()
    for row in data_rows:
        keys |= set((row.get("metrics") or {}).keys())
    return sorted(keys)

def save_pdf_table(data_rows: list[dict], path: str, timestamp: str):
    """Saves the results to a PDF file with a vertical layout for each ID."""
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
    for idx, row in enumerate(data_rows):
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
            table_x_start = (pdf.w - 140) / 2
            pdf.set_x(table_x_start)
            pdf.cell(70, 8, "Metric", border=1, fill=True, align='C')
            pdf.cell(70, 8, "Value", border=1, fill=True, align='C')
            pdf.ln()

            pdf.set_font("Helvetica", '', 9)
            for key in metric_keys:
                metric_label = key.replace("_", " ").title()
                pdf.set_x(table_x_start)
                pdf.cell(70, 8, metric_label, border=1, align='L')
                pdf.cell(70, 8, fmt_val(metrics.get(key, "")), border=1, align='R')
                pdf.ln()
        else:
            pdf.set_font("Helvetica", 'I', 10)
            pdf.cell(0, 6, "  (No metrics calculated for this ID)", ln=True)

        # Add a separator line between IDs
        if idx < len(data_rows) - 1:
            pdf.ln(5)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(5)
            
    pdf.output(path)

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