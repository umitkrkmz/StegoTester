# utils.py
import re
import math
from pathlib import Path
from collections import defaultdict
import numpy as np
import soundfile as sf
import imagehash
from PIL import Image
from scipy.spatial.distance import cosine

# --- AI Feature Extraction Imports ---
import cv2
import pandas as pd
import librosa
from scipy.stats import entropy, skew, kurtosis

# --- Constants ---
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif", ".webp"}
AUD_EXT = {".wav", ".flac", ".mp3"}
TXT_EXT = {".txt", ".bin", ".log"}
STOP_WORDS = {"orig", "original", "stego", "extract", "audio", "image", "text", "file", "output", "test"}

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

# --- AI FEATURE EXTRACTION ENGINES ---

def extract_image_features(img_path):
    """
    Extracts features from a trained Image model (RandomForest/GBM). 
    Columns: ['img_mean', 'img_std', 'img_lsb_entropy', 'img_apd_mean', 'img_edge_density', 'img_skew']
    """
    try:
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None: return None
        
        # 1. Basic Statistics
        img_mean = np.mean(img)
        img_std = np.std(img)
        img_skew = skew(img.flatten())
        
        # 2. LSB Analysis (Entropy)
        lsb = img & 1
        counts = np.bincount(lsb.flatten(), minlength=2)
        prob = counts / (np.sum(counts) + 1e-10)
        lsb_ent = entropy(prob, base=2)
        
        # 3. APD (Adjacent Pixel Difference)
        diff_h = np.abs(img[:, :-1] - img[:, 1:])
        diff_v = np.abs(img[:-1, :] - img[1:, :])
        apd = (np.mean(diff_h) + np.mean(diff_v)) / 2.0
        
        # 4. Edge Density
        edges = cv2.Canny(img, 100, 200)
        edge_dens = np.mean(edges) / 255.0
        
        # DataFrame format
        features = pd.DataFrame([{
            'img_mean': img_mean,
            'img_std': img_std,
            'img_lsb_entropy': lsb_ent,
            'img_apd_mean': apd,
            'img_edge_density': edge_dens,
            'img_skew': img_skew
        }])
        return features
    except Exception as e:
        print(f"Image Feature Error: {e}")
        return None

def extract_audio_features(aud_path):
    """
    Extracts features for the trained audio model.
    Columns: ['aud_lsb_entropy', 'aud_lsb_corr', 'aud_lsb_trans', 'aud_kurtosis',
        'aud_spec_flatness', 'aud_mfcc_mean', 'aud_spec_cent_mean', 'aud_rms_mean']
    """
    try:
        # --- PART 1: RAW BIT ANALYSIS ---
        data_int, samplerate = sf.read(str(aud_path), dtype='int16')
        if len(data_int.shape) > 1:
            data_int = np.mean(data_int, axis=1).astype(np.int16)
            
        lsb = data_int & 1
        
        # LSB Correlation
        lsb_corr = 0
        if len(lsb) > 1:
            c = np.corrcoef(lsb[:-1], lsb[1:])[0, 1]
            lsb_corr = 0 if np.isnan(c) else c
            
        # Transition Rate
        trans = np.sum(np.abs(np.diff(lsb))) / len(lsb)
        
        # LSB Entropy
        counts = np.bincount(lsb.flatten(), minlength=2)
        prob = counts / (np.sum(counts) + 1e-10)
        lsb_ent = entropy(prob, base=2)
        
        aud_kurtosis = kurtosis(data_int)
        
        # --- PART 2: SPECTRAL ANALYSIS (Librosa) ---
        y, sr = librosa.load(str(aud_path), sr=22050)
        if len(y) < 512: y = np.pad(y, (0, 512 - len(y)))
        
        mfcc = np.mean(librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13))
        flat = np.mean(librosa.feature.spectral_flatness(y=y))
        cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        rms = np.mean(librosa.feature.rms(y=y))
        
        features = pd.DataFrame([{
            'aud_lsb_entropy': lsb_ent,
            'aud_lsb_corr': lsb_corr,
            'aud_lsb_trans': trans,
            'aud_kurtosis': aud_kurtosis,
            'aud_spec_flatness': flat,
            'aud_mfcc_mean': mfcc,
            'aud_spec_cent_mean': cent,
            'aud_rms_mean': rms
        }])
        return features
    except Exception as e:
        print(f"Audio Feature Error: {e}")
        return None

def calculate_gatekeeper_score(aud_path):
    """
    Quick mathematical check (Gatekeeper).
    Calculates Audio LSB Transition Rate.
    """
    try:
        data_int, _ = sf.read(str(aud_path), dtype='int16')
        if len(data_int.shape) > 1: data_int = data_int[:, 0] # Sadece ilk kanal
        lsb = data_int & 1
        # Calculate transition rate
        trans_rate = np.sum(np.abs(np.diff(lsb))) / (len(lsb) - 1)
        return trans_rate
    except:
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