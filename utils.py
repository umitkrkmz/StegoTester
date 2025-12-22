# utils.py
import re
from pathlib import Path
from collections import defaultdict
from PIL import Image
import imagehash
import numpy as np
import soundfile as sf
from scipy.spatial.distance import cosine
import math

# --- Constants ---
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif", ".webp"}
AUD_EXT = {".wav", ".flac", ".mp3"}
TXT_EXT = {".txt", ".bin", ".log"}
STOP_WORDS = {"orig", "original", "stego", "extract", "audio", "image", "text", "file", "output", "test", "tonal", "speech", "melodik", "noise"}

# --- Helper Functions ---
def fmt_val(v) -> str:
    try:
        if v == float("inf"): return "inf"
    except: pass
    if isinstance(v, int): return str(v)
    try:
        fval = float(v)
        if fval == 0.0: return "0"
        if abs(fval) < 1e-4: return f"{fval:.4e}"
        return f"{fval:.4f}"
    except: return str(v)

# --- AI / STATISTICAL DETECTION ENGINES ---

def calculate_image_stego_prob(ref_path, cmp_path):
    """
    Resimler için Fark Analizi:
    Orijinal ve Aday resim arasındaki farkı (residual) analiz eder.
    Eğer fark yoksa (MSE=0) -> %0.
    Eğer fark çok rastgele ise -> Yüksek İhtimal.
    """
    try:
        # 1. Open the images
        img_ref = Image.open(ref_path).convert('RGB')
        img_cmp = Image.open(cmp_path).convert('RGB')
        
        # Size control
        if img_ref.size != img_cmp.size:
            return 1.0 # If the dimensions are different, it has definitely been tampered with.
            
        arr_ref = np.array(img_ref, dtype=np.int16)
        arr_cmp = np.array(img_cmp, dtype=np.int16)
        
        # 2. Calculate the Difference (Residual)
        diff = np.abs(arr_ref - arr_cmp)
        
        # If there is no difference, it is clean.
        if np.sum(diff) == 0:
            return 0.00
            
        # 3. Look only at LSB differences (Bitwise XOR is also logical, but difference is sufficient) 
        # Calculate the entropy of the pixels where the difference exists
        flat_diff = diff.flatten()
        non_zero_diff = flat_diff[flat_diff > 0]
        
        if len(non_zero_diff) == 0: 
            return 0.0
            
        # Histogram and Entropy
        counts = np.bincount(non_zero_diff)
        probs = counts / len(non_zero_diff)
        entropy = -np.sum([p * math.log2(p) for p in probs if p > 0])
        
        # Interpretation:
        # A difference with high entropy indicates encrypted data.
        # The maximum entropy is 8 for 8-bit, but stego differences are generally low.
        # Let's generate a score between 0 and 1 using a simple sigmoid function.
        # Let's assume the threshold value is 0.5.
        score = 1.0 / (1.0 + math.exp(-(entropy - 0.5) * 2))
        
        return round(score, 4)

    except Exception as e:
        print(f"Image detection error: {e}")
        return 0.0

def calculate_audio_stego_prob(ref_path, cmp_path):
    """
    Precise Difference Analysis for Audio:
    Vector/Spread Spectrum methods create very little difference in amplitude,
    but affect the overall file. Therefore, we will look at the 'Spread Rate'.
    """
    try:
        # Read the audio (raw data in int16 format)
        y_ref, sr_ref = sf.read(ref_path, dtype='int16')
        y_cmp, sr_cmp = sf.read(cmp_path, dtype='int16')
        
        # Equalize the lengths
        min_len = min(len(y_ref), len(y_cmp))
        y_ref = y_ref[:min_len]
        y_cmp = y_cmp[:min_len]
        
        # If it's stereo, then flatten it.
        if y_ref.ndim > 1: y_ref = y_ref.flatten()
        if y_cmp.ndim > 1: y_cmp = y_cmp.flatten()
        
        # Calculate the absolute difference.
        diff = np.abs(y_ref - y_cmp)
        
        # If there is no difference (If the files are the same)
        if np.sum(diff) == 0:
            return 0.00
            
        # --- LOGIC: COVERAGE DENSITY ---
        # Vector steganography does not increase amplitude, it increases the number of changing samples.
        
        # 1. How many samples have been changed?
        non_zero_count = np.count_nonzero(diff)
        total_samples = len(diff)
        
        # 2. Change Rate
        change_rate = non_zero_count / total_samples
        
        # 3. Scoring (Sensitivity Adjustment)
        # If more than 5% of the sound has changed, it is definitely stego. 
        # Therefore, we multiply the ratio by 20 (0.05 * 20 = 1.0)
        # So even a 1% change raises suspicion of 0.20 (20%).
        prob = min(change_rate * 20.0, 1.0)
        
        # If the rate of change is very low but the amplitude difference is high (Classic LSB)
        # Let's not miss that either:
        max_diff = np.max(diff)
        if max_diff > 0 and prob < 0.1:
             # At least there's a change, let's give it a 0.1 so the user notices.
             prob = max(prob, 0.1)

        return round(prob, 4)
        
    except Exception as e:
        print(f"Audio detection error: {e}")
        return 0.0

# --- Matching & Fingerprinting ---
def calculate_phash(image_path):
    try:
        img = Image.open(image_path)
        return imagehash.phash(img)
    except: return None

def calculate_audio_fingerprint(audio_path, duration=10):
    try:
        y, sr = sf.read(audio_path, start=0, stop=None, always_2d=True)
        max_frames = sr * duration
        if len(y) > max_frames: y = y[:max_frames]
        if y.shape[1] > 1: y = np.mean(y, axis=1)
        else: y = y.flatten()
        spectrum = np.abs(np.fft.rfft(y))
        n_bins = 500
        if len(spectrum) > n_bins:
            sub_arrays = np.array_split(spectrum, n_bins)
            fingerprint = np.array([np.mean(a) for a in sub_arrays])
        else: fingerprint = spectrum
        norm = np.linalg.norm(fingerprint)
        if norm > 0: fingerprint = fingerprint / norm
        return fingerprint
    except: return None
    
def get_tokens(filename: str) -> set:
    stem = Path(filename).stem.lower()
    tokens = set(re.split(r'[_\-\s\.]+', stem))
    clean_tokens = {t for t in tokens if t not in STOP_WORDS and not t.isdigit() and len(t) > 2}
    return clean_tokens

def group_files_smart(originals: list[str], stegos: list[str], extracts: list[str]):
    orig_entries = [] 
    for f in originals:
        path = Path(f)
        orig_entries.append({
            'path': f,
            'name': path.name,
            'tokens': get_tokens(f),
            'type': 'image' if path.suffix.lower() in IMG_EXT else 'audio' if path.suffix.lower() in AUD_EXT else 'text',
            'fingerprint': calculate_phash(f) if path.suffix.lower() in IMG_EXT else calculate_audio_fingerprint(f) if path.suffix.lower() in AUD_EXT else None
        })

    final_refs = {"image": {}, "audio": {}, "text": {}}
    groups = defaultdict(lambda: {"stego": [], "extract": []})
    global_id_counter = 1

    def find_best_original(cand_path):
        cand_p = Path(cand_path)
        cand_suffix = cand_p.suffix.lower()
        cand_type = 'image' if cand_suffix in IMG_EXT else 'audio' if cand_suffix in AUD_EXT else 'text'
        cand_fp = None
        if cand_type == 'image': cand_fp = calculate_phash(cand_path)
        elif cand_type == 'audio': cand_fp = calculate_audio_fingerprint(cand_path)
        best_match = None
        
        if cand_type == 'image' and cand_fp is not None:
            best_diff = 12
            for entry in orig_entries:
                if entry['type'] == 'image' and entry['fingerprint'] is not None:
                    diff = cand_fp - entry['fingerprint']
                    if diff < best_diff:
                        best_diff = diff
                        best_match = entry
        elif cand_type == 'audio' and cand_fp is not None:
            best_score = 0.90
            for entry in orig_entries:
                if entry['type'] == 'audio' and entry['fingerprint'] is not None:
                    dist = cosine(cand_fp, entry['fingerprint'])
                    similarity = 1.0 - dist
                    if similarity > best_score:
                        best_score = similarity
                        best_match = entry
        if not best_match:
            best_overlap = 0
            cand_tokens = get_tokens(cand_path)
            for entry in orig_entries:
                if entry['type'] == cand_type:
                    overlap = len(entry['tokens'] & cand_tokens)
                    if overlap > 0 and overlap > best_overlap:
                        best_overlap = overlap
                        best_match = entry
        return best_match

    for f in stegos:
        match = find_best_original(f)
        if match:
            gid = str(global_id_counter)
            groups[gid]["stego"].append(f)
            final_refs[match['type']][gid] = match['path']
            global_id_counter += 1

    for f in extracts:
        match = find_best_original(f)
        if match:
            gid = str(global_id_counter)
            groups[gid]["extract"].append(f)
            final_refs[match['type']][gid] = match['path']
            global_id_counter += 1
            
    return final_refs, groups