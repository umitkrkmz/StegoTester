# utils.py
import re
from pathlib import Path
from collections import defaultdict

# --- Constants ---
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif", ".webp"}
AUD_EXT = {".wav", ".flac"}
TXT_EXT = {".txt", ".bin", ".log"}

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

def _create_regex_from_pattern(pattern: str) -> re.Pattern:
    """Converts a user-friendly pattern like 'pre_{ID}_{KEYWORD}.ext' into a regex."""
    if not pattern: # Use default if pattern is empty
        pattern = "stego_{ID}_..._{KEYWORD}"
        
    # Convert user-friendly tags to regex groups
    escaped_pattern = re.escape(pattern)
    regex_pattern = escaped_pattern.replace(r'\{ID\}', r'(\d+)')
    regex_pattern = regex_pattern.replace(r'\{KEYWORD\}', r'(\w+)')
    regex_pattern = regex_pattern.replace(r'\{EXT\}', r'\.\w+')
    regex_pattern = regex_pattern.replace(r'\.\.\.', r'.*?') # for wildcard '...'
    
    # Ensure we match from the beginning of the string
    return re.compile(f"^{regex_pattern}$")

def group_files(originals, stegos, extracts, pattern):
    """Groups files based on a DYNAMIC user-defined naming pattern."""
    refs = {"image": {}, "audio": {}, "text": {}}
    groups = defaultdict(lambda: {"stego": [], "extract": []})
    
    # Store original files by keyword (this logic remains the same)
    for f in originals:
        p = Path(f)
        suf = p.suffix.lower()
        name_stem = p.stem.lower() # use lowercase for matching
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
            
    # Match stego and extract files using the DYNAMIC PATTERN
    # Assumes the user pattern is for stego files. We derive the extract pattern.
    stego_regex = _create_regex_from_pattern(pattern)
    extract_pattern_str = pattern.replace("stego", "extract", 1)
    extract_regex = _create_regex_from_pattern(extract_pattern_str)

    # We can't be sure which group is ID and which is KEYWORD, so we try to find both
    for f_list, f_regex in [(stegos, stego_regex), (extracts, extract_regex)]:
        list_key = "stego" if f_list is stegos else "extract"
        for f in f_list:
            match = f_regex.match(Path(f).name)
            if match and match.groups():
                # Assume the first numerical group is the ID
                potential_id = None
                for group in match.groups():
                    if group.isdigit():
                        potential_id = int(group)
                        break
                if potential_id is not None:
                    groups[potential_id][list_key].append(f)
                
    return refs, groups