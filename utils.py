# utils.py
import re
from pathlib import Path
from collections import defaultdict

# --- Constants ---
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
AUD_EXT = {".wav"}
TXT_EXT = {".txt", ".bin"}

# --- Helper Functions ---
def fmt_val(v) -> str:
    """Formats numbers nicely for reporting."""
    try:
        if v == float("inf"):
            return "inf"
    except Exception:
        pass
    if isinstance(v, int):
        return str(v)
    try:
        fval = float(v)
        if fval == 0.0:
            return "0"
        if abs(fval) < 1e-4:
            return f"{fval:.4e}"
        return f"{fval:.4f}"
    except Exception:
        return str(v)

def group_files(originals, stegos, extracts):
    """Groups original, stego, and extract files based on a naming convention."""
    refs = {"image": {}, "audio": {}, "text": {}}
    groups = defaultdict(lambda: {"stego": [], "extract": []})

    # Store originals in a dictionary by keyword
    for f in originals:
        p = Path(f)
        suf = p.suffix.lower()
        name_stem = p.stem
        key = None
        if suf in IMG_EXT:
            if name_stem.startswith("orig_image_"): key = name_stem.replace("orig_image_", "")
            elif name_stem.startswith("orig_"): key = name_stem.replace("orig_", "")
            if key: refs["image"][key] = f
        elif suf in AUD_EXT:
            if name_stem.startswith("orig_audio_"): key = name_stem.replace("orig_audio_", "")
            elif name_stem.startswith("orig_"): key = name_stem.replace("orig_", "")
            if key: refs["audio"][key] = f
        elif suf in TXT_EXT:
            if name_stem.startswith("orig_text_"): key = name_stem.replace("orig_text_", "")
            elif name_stem.startswith("orig_"): key = name_stem.replace("orig_", "")
            if key: refs["text"][key] = f

    # Match stego and extract files by ID
    for f in stegos:
        m = re.match(r"stego_(\d+)_", Path(f).name)
        if m: groups[int(m.group(1))]["stego"].append(f)
    for f in extracts:
        m = re.match(r"extract_(\d+)_", Path(f).name)
        if m: groups[int(m.group(1))]["extract"].append(f)
            
    return refs, groups