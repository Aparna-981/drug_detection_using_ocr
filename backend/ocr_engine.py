# -*- coding: utf-8 -*-
"""
ocr_engine.py  v4  —  Spatial-Pairing Edition
══════════════════════════════════════════════════════════════
ROOT CAUSE OF PREVIOUS FAILURES:
  PaddleOCR returns each text block as a SEPARATE result with
  its own bounding box.  On a medicine label this means:

      Line A:  "Batch No."   at  x=20,  y=140
      Line B:  "SP240165"    at  x=120, y=140   ← same row!
      Line C:  "Mfg Date"    at  x=20,  y=165
      Line D:  "06/2024"     at  x=120, y=165   ← same row!

  The old code joined ALL text into one string and ran regex on it.
  That works when label+value are on one line, but breaks when OCR
  puts them in separate boxes (very common on medicine strips).

SOLUTION — SPATIAL PAIRING:
  1. Sort all OCR boxes into rows (group by Y coordinate within ±15px).
  2. Within each row, sort left → right.
  3. Identify LABEL tokens (contain keywords like "batch", "mfg", "exp").
  4. The VALUE is the next token(s) in the same row, OR in the row below.
  5. Medicine name = the TALLEST (largest h_px) text block in the
     top 55% of the image that isn't a label/stopword.

PREPROCESSING:
  Tries 4 strategies and picks the one producing most text lines:
    • standard   — CLAHE + denoise + sharpen
    • thresh     — adaptive threshold (white background strips)
    • foil       — strong LAB contrast (metallic blister packs)
    • upscaled   — 2× upscale on original (catches small text)
══════════════════════════════════════════════════════════════
"""

import cv2
import re
import numpy as np
import os
from paddleocr import PaddleOCR

# ── PaddleOCR singleton ──────────────────────────────────────
print("[OCR] Loading PaddleOCR (v4 spatial engine)...")
_ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en',
    use_gpu=False,          # flip to True if paddlepaddle-gpu installed
    show_log=False,
    det_db_thresh=0.25,     # lower = detect smaller/faded text
    det_db_box_thresh=0.4,
    rec_batch_num=8,
)
print("[OCR] PaddleOCR ready!")


# ══════════════════════════════════════════════════════════════
# SECTION 1 — PREPROCESSING
# ══════════════════════════════════════════════════════════════

def _upscale(img, min_w=1000):
    h, w = img.shape[:2]
    if w < min_w:
        s   = min_w / w
        img = cv2.resize(img, (int(w*s), int(h*s)),
                         interpolation=cv2.INTER_CUBIC)
    return img


def _pre_standard(img):
    g  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cl = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)
    dn = cv2.fastNlMeansDenoising(cl, h=9)
    sh = cv2.filter2D(dn, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]]))
    return cv2.cvtColor(sh, cv2.COLOR_GRAY2BGR)


def _pre_thresh(img):
    g  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bl = cv2.GaussianBlur(g, (3, 3), 0)
    th = cv2.adaptiveThreshold(
        bl, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 25, 8)
    return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)


def _pre_foil(img):
    """Strong contrast for metallic / foil blister packs."""
    lab     = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l       = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _pre_upscale2x(img):
    """2× upscale — helps with very small text."""
    h, w = img.shape[:2]
    big  = cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
    g    = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    cl   = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)
    return cv2.cvtColor(cl, cv2.COLOR_GRAY2BGR)


# ══════════════════════════════════════════════════════════════
# SECTION 2 — RAW OCR PASS
# ══════════════════════════════════════════════════════════════

def _run_ocr(img_path: str) -> list[dict]:
    """
    Returns list of dicts, one per detected text region:
      text, conf, x, y, w, h_px
    Only keeps results with confidence > 0.38.
    """
    raw = _ocr.ocr(img_path, cls=True)
    out = []
    if not raw or not raw[0]:
        return out
    for line in raw[0]:
        if line is None:
            continue
        bbox, (text, conf) = line
        text = text.strip()
        if not text or conf < 0.38:
            continue
        try:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            x      = min(xs)
            y      = min(ys)
            w      = max(xs) - x
            h_px   = max(ys) - y
            y_ctr  = (min(ys) + max(ys)) / 2
            x_ctr  = (min(xs) + max(xs)) / 2
        except Exception:
            x = y = w = h_px = y_ctr = x_ctr = 0
        out.append({
            "text":  text,
            "conf":  conf,
            "x":     x,
            "y":     y,
            "w":     w,
            "h_px":  h_px,
            "y_ctr": y_ctr,
            "x_ctr": x_ctr,
        })
    return out


# ══════════════════════════════════════════════════════════════
# SECTION 3 — SPATIAL ROW GROUPING
# ══════════════════════════════════════════════════════════════

def _group_into_rows(tokens: list[dict], row_tol_px: float = 18) -> list[list[dict]]:
    """
    Groups OCR tokens into horizontal rows.
    Two tokens are in the same row if their Y-centres are within row_tol_px.
    Returns list of rows; each row is sorted left→right.
    """
    if not tokens:
        return []

    sorted_tok = sorted(tokens, key=lambda t: t["y_ctr"])
    rows       = []
    cur_row    = [sorted_tok[0]]
    cur_y      = sorted_tok[0]["y_ctr"]

    for tok in sorted_tok[1:]:
        if abs(tok["y_ctr"] - cur_y) <= row_tol_px:
            cur_row.append(tok)
        else:
            rows.append(sorted(cur_row, key=lambda t: t["x_ctr"]))
            cur_row = [tok]
            cur_y   = tok["y_ctr"]

    if cur_row:
        rows.append(sorted(cur_row, key=lambda t: t["x_ctr"]))

    return rows


# ══════════════════════════════════════════════════════════════
# SECTION 4 — LABEL CLASSIFIERS
# ══════════════════════════════════════════════════════════════

def _is_batch_label(t: str) -> bool:
    t = t.lower().strip().rstrip('.:')
    return bool(re.search(
        r'\b(batch\s*no?|b\.?\s*no?|lot\s*no?|batch\s*number|batch)\b', t
    ))

def _is_mfg_label(t: str) -> bool:
    t = t.lower().strip().rstrip('.:')
    return bool(re.search(
        r'\b(mfg\.?\s*date|mfd\.?\s*date|date\s*of\s*mfg|mfg|mfd|d\.o\.m|dom|'
        r'manufacturing\s*date|manufacture\s*date|manuf)\b', t
    ))

def _is_exp_label(t: str) -> bool:
    t = t.lower().strip().rstrip('.:')
    return bool(re.search(
        r'\b(exp(?:iry)?\.?\s*date|date\s*of\s*exp|use\s*before|use\s*by|'
        r'best\s*before|expiration|exp\.?|d\.o\.e|doe)\b', t
    ))

def _is_mfr_label(t: str) -> bool:
    t = t.lower().strip().rstrip('.:')
    return bool(re.search(
        r'\b(manufactured\s*by|mfg\.?\s*by|mfd\.?\s*by|mfr\.?\s*by|'
        r'marketed\s*by|mkd\.?\s*by|manufactured\s*&\s*marketed)\b', t
    ))

_DATE_PTRN = r'(?:\d{1,2}[/\-]\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s/.\-]+\d{2,4})'

def _is_date(t: str) -> bool:
    t = t.strip().lower()
    # Handle common OCR glitches like 'IO' for '10' or 'ZOZ6' for '2026'
    t = t.replace('o', '0').replace('i', '1').replace('l', '1').replace('z', '2').replace('s', '5')
    return bool(re.fullmatch(_DATE_PTRN, t))

def _smart_correct_batch(t: str) -> str:
    """Fixes common OCR swaps in batch numbers with context-aware rules."""
    if not t: return ""
    t = t.strip().upper()
    
    # 1. Swap S -> 5 and Z -> 2 ONLY if the string is mostly digits
    # (Typical for batch numbers that are purely numeric or numeric-heavy)
    digit_count = sum(c.isdigit() for c in t)
    total_len   = len(t)
    
    if digit_count >= total_len / 2:
        t = t.replace('Z', '2').replace('S', '5')
    
    # 2. Selective O -> 0 and I -> 1 correction (only when surrounded by digits)
    t = re.sub(r'(?<=\d)O(?=\d)', '0', t)
    t = re.sub(r'(?<=\d)O$', '0', t)
    t = re.sub(r'^O(?=\d)', '0', t)
    
    t = re.sub(r'(?<=\d)I(?=\d)', '1', t)
    t = re.sub(r'(?<=\d)I$', '1', t)
    t = re.sub(r'^I(?=\d)', '1', t)
    
    # 3. Strip trailing labels that OCR might have merged (e.g., "4C10415MFD" -> "4C10415")
    t = re.sub(r'(?:MFG|MFD|EXP|DATE|LOT|USE|BEFORE|BNO|BN|BTCH)$', '', t)
    
    return t.strip()

def _smart_correct_date(t: str) -> str:
    """Fixes common OCR swaps in dates while protecting month names."""
    if not t: return ""
    t = t.strip().upper()
    
    # Protect month names by processing only numeric-like parts
    # e.g. "MAY ZOZ5" -> "MAY 2025"
    parts = re.split(r'([\s/\-.\\]+)', t)
    new_parts = []
    
    for p in parts:
        # If part is mostly letters and matches a month pattern, don't correct it
        if re.search(r'[A-Z]{3,}', p) and any(m in p.lower() for m in ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']):
            new_parts.append(p)
            continue
        
        # If part is numeric-like (contains digits or common OCR digit-swaps), correct it
        if re.search(r'[\dIOZSL]', p):
            p = p.replace('O', '0').replace('I', '1').replace('L', '1').replace('Z', '2').replace('S', '5')
        new_parts.append(p)
        
    return "".join(new_parts)

def _conservative_correct_text(text: str) -> str:
    """
    For names and labels. Swaps characters ONLY when context strongly suggests an error.
    e.g. 5YRUP -> SYRUP, but DOLO 650 remains 650.
    """
    if not text: return ""
    
    # Logic: If a number is surrounded by uppercase letters, it's likely a misread letter
    # 5 -> S (if surrounded by letters)
    text = re.sub(r'([A-Z])5([A-Z]?)', r'\1S\2', text)
    text = re.sub(r'^5([A-Z])', r'S\1', text)
    
    # 0 -> O (if surrounded by letters)
    text = re.sub(r'([A-Z])0([A-Z]?)', r'\1O\2', text)
    text = re.sub(r'^0([A-Z])', r'O\1', text)
    
    # 1 -> I or L (if surrounded by letters) - choosing I as more common in pharma
    text = re.sub(r'([A-Z])1([A-Z])', r'\1I\2', text)
    
    # Special cases for pharmaceutical forms
    text = re.sub(r'\b5YRUP\b', 'SYRUP', text, flags=re.I)
    text = re.sub(r'\bTAB1ETS\b', 'TABLETS', text, flags=re.I)
    text = re.sub(r'\bCAP5ULE5\b', 'CAPSULES', text, flags=re.I)
    
    return text.strip()

def _is_batch_value(t: str) -> bool:
    """True if the token looks like a batch/lot number."""
    t = t.strip()
    if len(t) < 3 or len(t) > 20:
        return False
    # Pure year → skip
    if re.fullmatch(r'20\d{2}', t):
        return False
    # Skip common labels misidentified as values
    if t.lower() in {'batch', 'mfg', 'mfd', 'exp', 'date', 'lot'}:
        return False
    return bool(re.fullmatch(
        r'[A-Za-z0-9][\-A-Za-z0-9]{1,18}', t
    ))

_MFR_STOP_WORDS = {
    'batch','mfg','mfd','exp','tel','ph','fax','website','www','drug',
    'schedule','store','keep','composition','warning','caution',
    'marketed','distributed','regd','registered',
}

def _clean_mfr(text: str) -> str:
    """Removes trailing junk from a manufacturer string."""
    # Cut at known stop labels
    text = re.split(
        r'\b(?:batch|mfg|exp|tel\b|ph:|fax|website|www\.|regd|'
        r'drug|schedule|store|keep|caution|warning)\b',
        text, flags=re.I
    )[0].strip()
    # Remove trailing punctuation
    text = text.rstrip('.:,-')
    return text[:120] if len(text) > 5 else ""


# ══════════════════════════════════════════════════════════════
# SECTION 5 — SPATIAL VALUE LOOKUP
# ══════════════════════════════════════════════════════════════

def _next_tokens_in_row(row: list[dict], label_idx: int, max_tokens: int = 4) -> str:
    """Returns text of tokens to the RIGHT of label_idx in the same row."""
    parts = [row[i]["text"] for i in range(label_idx + 1, min(len(row), label_idx + 1 + max_tokens))]
    return " ".join(parts).strip()


def _first_token_in_next_row(rows: list[list[dict]], row_idx: int) -> str:
    """Returns text of first token in the row immediately below."""
    if row_idx + 1 < len(rows) and rows[row_idx + 1]:
        return rows[row_idx + 1][0]["text"].strip()
    return ""


def _tokens_in_next_row(rows: list[list[dict]], row_idx: int, max_tokens: int = 6) -> str:
    """Returns all tokens in the row immediately below as one string."""
    if row_idx + 1 < len(rows):
        return " ".join(t["text"] for t in rows[row_idx + 1][:max_tokens]).strip()
    return ""


# ══════════════════════════════════════════════════════════════
# SECTION 6 — MAIN FIELD EXTRACTION (spatial)
# ══════════════════════════════════════════════════════════════

def _extract_fields_spatial(rows: list[list[dict]]) -> dict:
    """
    Walks rows top-to-bottom, token-by-token.
    When a label token is found, looks right (same row) and below (next row)
    for the value.
    """
    batch = mfg = exp = mfr = None

    for row_i, row in enumerate(rows):
        for tok_i, tok in enumerate(row):
            t = tok["text"]

            # ── BATCH ─────────────────────────────────────
            if batch is None and _is_batch_label(t):
                # Look right on same row first
                right = _next_tokens_in_row(row, tok_i)
                # Filter out other labels from right (even if concatenated without boundary)
                right_clean = re.sub(
                    r'(?:\b|(?<=\d))(?:mfg|mfd|exp|date|use\s*before)\b.*', '', right, flags=re.I
                ).strip()
                if right_clean and _is_batch_value(right_clean.split()[0]):
                    batch = _smart_correct_batch(right_clean.split()[0])
                else:
                    # Try row below
                    below = _first_token_in_next_row(rows, row_i)
                    if below and _is_batch_value(below):
                        batch = _smart_correct_batch(below)

            # ── MFG DATE ──────────────────────────────────
            elif mfg is None and _is_mfg_label(t):
                right = _next_tokens_in_row(row, tok_i)
                dm = re.search(_DATE_PTRN, _smart_correct_date(right), re.I)
                if dm:
                    mfg = dm.group(0)
                else:
                    below = _tokens_in_next_row(rows, row_i)
                    dm2 = re.search(_DATE_PTRN, _smart_correct_date(below), re.I)
                    if dm2:
                        mfg = dm2.group(0)

            # ── EXP DATE ──────────────────────────────────
            elif exp is None and _is_exp_label(t):
                right = _next_tokens_in_row(row, tok_i)
                dm = re.search(_DATE_PTRN, _smart_correct_date(right), re.I)
                if dm:
                    exp = dm.group(0)
                else:
                    below = _tokens_in_next_row(rows, row_i)
                    dm2 = re.search(_DATE_PTRN, _smart_correct_date(below), re.I)
                    if dm2:
                        exp = dm2.group(0)

            # ── MANUFACTURER ──────────────────────────────
            elif mfr is None and _is_mfr_label(t):
                right = _next_tokens_in_row(row, tok_i, max_tokens=10)
                if right and len(right) > 5:
                    mfr = _clean_mfr(right) or None
                if not mfr:
                    # Manufacturer often spans 2-3 rows below the label
                    mfr_parts = []
                    for r in range(row_i + 1, min(row_i + 4, len(rows))):
                        row_text = " ".join(t["text"] for t in rows[r])
                        # Stop if we hit another label row
                        if any(fn(row_text) for fn in [_is_batch_label,
                               _is_mfg_label, _is_exp_label]):
                            break
                        mfr_parts.append(row_text)
                    if mfr_parts:
                        mfr = _conservative_correct_text(_clean_mfr(" ".join(mfr_parts))) or None

    return {"batch": batch, "mfg": mfg, "exp": exp, "manufacturer": mfr}


# ══════════════════════════════════════════════════════════════
# SECTION 7 — FALLBACK REGEX ON FULL TEXT
# ══════════════════════════════════════════════════════════════
# Used when spatial method finds nothing (e.g. label+value on same OCR token)

_FB_BATCH = re.compile(
    r'(?:batch\s*(?:no\.?|number|#)?|b\.?\s*no\.?|lot\s*no\.?)'
    r'[\s:.\-]*([A-Za-z0-9][\-A-Za-z0-9]{1,16})',
    re.I
)
_FB_MFG = re.compile(
    r'(?:mfg\.?\s*(?:date)?|date\s*of\s*mfg\.?|manufactured\s*on|'
    r'd\.?o\.?m\.?|dom\.?)'
    r'[\s:.\-]*(' + _DATE_PTRN + ')',
    re.I
)
_FB_EXP = re.compile(
    r'(?:exp(?:iry)?\.?\s*(?:date)?|date\s*of\s*exp(?:iry)?\.?|'
    r'use\s*before|use\s*by|best\s*before|expiration|d\.?o\.?e\.?)'
    r'[\s:.\-]*(' + _DATE_PTRN + ')',
    re.I
)
_FB_MFR = re.compile(
    r'(?:manufactured\s*by|mfg\.?\s*by|mfd\.?\s*by|marketed\s*by)'
    r'[\s:.\-]*([A-Za-z][^\n]{4,100})',
    re.I
)
_FB_DATE = re.compile(r'\b(' + _DATE_PTRN + r')\b', re.I)



def _fallback_fields(full_text: str, existing: dict) -> dict:
    """
    Fills in any fields still None using regex on the merged full-text string.
    """
    batch = existing.get("batch")
    mfg   = existing.get("mfg")
    exp   = existing.get("exp")
    mfr   = existing.get("manufacturer")

    if not batch:
        m = _FB_BATCH.search(full_text)
        if m:
            cand = _smart_correct_batch(m.group(1))
            if not re.fullmatch(r'20\d{2}', cand):
                batch = cand

    if not mfg:
        m = _FB_MFG.search(full_text)
        if m: mfg = m.group(1).strip()

    if not exp:
        m = _FB_EXP.search(full_text)
        if m: exp = m.group(1).strip()

    if not mfr:
        m = _FB_MFR.search(full_text)
        if m:
            mfr = _conservative_correct_text(_clean_mfr(m.group(1))) or None

    # Last resort: sort all standalone dates by year
    if not mfg or not exp:
        dates = list(dict.fromkeys(_FB_DATE.findall(full_text)))
        def _yr(d):
            # Extract last 2-4 digits for the year
            m = re.search(r'(\d{2,4})$', d.strip())
            if m:
                y = int(m.group(1))
                return y + 2000 if y < 100 else y
            return 0
        if len(dates) >= 2:
            srt = sorted(dates, key=_yr)
            if not mfg: mfg = srt[0]
            if not exp:  exp  = srt[-1]
        elif len(dates) == 1 and not exp:
            exp = dates[0]

    # Last resort batch
    if not batch:
        m2 = re.search(
            r'\b([A-Za-z]{1,4}[\-]?\d{3,}[A-Za-z0-9]*'
            r'|[A-Za-z0-9]{1,4}[\-]\d{2,}[A-Za-z0-9]*)\b',
            full_text
        )
        if m2:
            cand = _smart_correct_batch(m2.group(1))
            if not re.fullmatch(r'20\d{2}', cand):
                batch = cand

    return {"batch": batch, "mfg": mfg, "exp": exp, "manufacturer": mfr}


# ══════════════════════════════════════════════════════════════
# SECTION 8 — DUAL NAME EXTRACTION
# ══════════════════════════════════════════════════════════════
#
# INSIGHT from real medicine labels (India):
#
#  Every label has TWO names:
#
#  1. BRAND NAME  = largest font = what manufacturer calls it
#     e.g. "ADLINE", "Jubira F10", "Dolo 650", "Pantoshang-40"
#     → picked by largest h_px
#
#  2. GENERIC NAME = pharmaceutical classification name
#     always contains: [Drug(s)] + [Dosage Form] + [Pharmapoeia Code]
#     e.g. "Adrenaline Injection IP"
#          "Rosuvastatin and Fenofibrate Tablets IP"
#          "Pantoprazole Gastro-Resistant Tablets IP"
#     → picked by finding the row that contains a dosage-form word
#       AND a pharmacopoeia code (IP/BP/USP)
#
#  For NSQ database matching we need BOTH because:
#    - CDSCO dataset uses generic names → match against generic_name
#    - Some entries use brand names     → also try brand_name
#
# ══════════════════════════════════════════════════════════════

# ── STOPWORDS for brand name extraction ──────────────────────
# These are words that are NEVER the brand name alone.
# NOTE: "and", "with", "for" removed from filler because they
# appear inside generic names like "Rosuvastatin AND Fenofibrate"

# Dosage form words — safe to exclude from brand name
_STOP_FORM = {
    'tablet','tablets','tab','tabs',
    'capsule','capsules','cap','caps',
    'injection','inj','injectable',
    'syrup','solution','sol','suspension','susp',
    'ointment','cream','gel','lotion','drops','spray',
    'granule','granules','sachet','sachets',
    'infusion','implant','patch','inhaler',
    'softgel','softgelatin','linctus','elixir',
    'emulsion','suppository','enema','pessary',
}

# Measurement units
_STOP_UNIT = {
    'mg','ml','mcg','ug','iu','g','kg','gm','gms',
    'mmol','meq','units','unit','ppm','w/v','v/v','w/w',
    'percent','%',
}

# Pharmacopoeia codes
_STOP_CODE = {
    'ip','bp','usp','ep','jp','i.p.','b.p.','u.s.p.','ph.eur','nf',
}

# Regulatory / administrative label text
_STOP_ADMIN = {
    'schedule','h1','otc','rx',
    'approved','licensed','sterile','preservative','free',
    'storage','store','cool','dry','refrigerate',
    'keep','out','reach','children',
    'manufactured','manufacturing','marketed','distributed','division',
    'registered','regd','trademark','tm',
    'warning','caution','note','important',
    'contains','composition','ingredients',
    'dosage','dose','directions','usage',
    'physician','doctor','medical','practitioner',
    'use','before','after','food','water',
    'room','temperature','light','protect','from',
    'net','content','contents','each',
    'colour','color','flavour','flavor',
    'sold','retail','only','not','prescription',
}

# Company / address words
_STOP_COMPANY = {
    'pvt','ltd','inc','llp','corp',
    'pharma','pharmaceuticals','healthcare','biotech',
    'laboratories','lab','labs','lifesciences',
    'india','indian',
    'mfg','mfd','exp','batch','no','lot','date',
    'www','tel','fax','email','website',
    'office','works','plot','sector','phase',
    'road','street','nagar','industrial','area','estate',
    'district','dist','pin','state','country',
}

# Common filler (but NOT "and"/"with" — they appear in generic names)
_STOP_FILLER = {'the','a','an','in','of','to','is','be','as'}

# Combined
_NAME_STOP = (
    _STOP_FORM | _STOP_UNIT | _STOP_CODE |
    _STOP_ADMIN | _STOP_COMPANY | _STOP_FILLER
)

# Dosage form words used positively to DETECT generic name rows
_DOSAGE_FORM_WORDS = {
    'tablet','tablets','capsule','capsules',
    'injection','syrup','solution','suspension',
    'ointment','cream','drops','granule','sachet','infusion',
    'softgel','linctus','elixir','emulsion',
}

# Pharmacopoeia codes used positively to DETECT generic name rows
_PHARMA_CODES = {'ip','bp','usp','ep','jp','i.p.','b.p.','u.s.p.'}

# Common pharmaceutical prefixes/suffixes to boost medicine name detection
_PHARMA_ROOTS = {
    'para','amoxi','cif','ace','clov','panto','ome','levo','cet','aza',
    'mox','glo','flo','bro','dex','pre','sul','met','gli','rosu',
    'fen','tel','aml','met','aten','bis','car','nit','hyd','chl',
    'cil','pril','sartan','olol','pine','statin','zone','mide',
    'vasta','nide','nase','micin','mycin','cillin','vir','oxin',
}


def _is_medicine_label_token(t: str) -> bool:
    """Returns True if this token is a field LABEL (Batch No., Mfg Date etc.)"""
    return any(fn(t) for fn in [_is_batch_label, _is_mfg_label,
                                  _is_exp_label, _is_mfr_label])


# ─────────────────────────────────────────────────────────────
# BRAND NAME — largest valid font token
# ─────────────────────────────────────────────────────────────

def _is_valid_brand_token(tok: dict) -> bool:
    """
    Returns True if this token COULD be the brand name.
    Brand names are typically 1-3 words, mixed case or all caps.

    KEY RULE: If the token contains a DOSAGE FORM word (Tablets, Injection,
    Syrup...) it is a GENERIC name, not a brand name.
    e.g. "Adrenaline Injection IP"            → generic, NOT brand
         "Rosuvastatin and Fenofibrate Tablets IP" → generic, NOT brand
         "ADLINE"                             → brand ✅
         "Jubira F10"                         → brand ✅
         "Dolo 650"                           → brand ✅
    """
    t  = tok["text"].strip()
    tl = t.lower()

    if len(t) < 3:                                              return False
    if re.fullmatch(r'\d+[\.,]?\d*', t):                       return False
    if re.fullmatch(r'\d{1,2}[/\-]\d{2,4}', t):                 return False
    if re.fullmatch(r'[A-Za-z]{0,4}[\-]?\d{3,}[A-Za-z0-9]*', t): return False
    if _is_medicine_label_token(t):                             return False
    if _is_date(t):                                             return False
    if len(t) > 60:                                             return False

    words = tl.split()

    # ── Allow dosage form words in brand names to improve matching ──
    # Previously, this aggressively rejected names containing "Tablet" or "Injection".
    # Since drug_matcher strips these out, it is safe to keep them here.
    # if any(w in _DOSAGE_FORM_WORDS for w in words):
    #     return False


    # ── Reject tokens where all meaningful words are stopwords ───────
    meaningful = [w for w in words
                  if w not in _NAME_STOP
                  and not re.fullmatch(r'\d+[a-z%]*', w)]
    if not meaningful:
        return False

    # Short all-caps abbreviations (IP, BP, MRP) that are in stoplist
    if t.isupper() and len(t) <= 4 and tl in _NAME_STOP:
        return False

    return True

def _get_brand_relevance_score(text: str) -> float:
    """Returns a boost factor based on pharma-like textual features."""
    tl = text.lower()
    score = 1.0
    
    # Boost if contains pharmaceutical roots
    if any(root in tl for root in _PHARMA_ROOTS):
        score += 0.5
        
    # Boost if looks like a brand name (typically 1-2 words, often capitalized)
    words = text.split()
    if 1 <= len(words) <= 2:
        score += 0.3
        
    # Penalty for very long words or names with too many numbers
    if len(text) > 30: score -= 0.5
    if sum(c.isdigit() for c in text) > 4: score -= 0.4
    
    return max(0.1, score)


def _extract_brand_name(tokens: list[dict]) -> str | None:
    """
    Brand name = the LARGEST valid text token on the label.
    Tries adjacent-token combinations for names like "Dolo 650"
    where the number is a separate OCR box.
    """
    candidates = []

    for i, tok in enumerate(tokens):
        if _is_valid_brand_token(tok):
            rel = _get_brand_relevance_score(tok["text"])
            candidates.append((tok["text"], tok["h_px"] * rel))

        # Try combining adjacent tokens on the same row
        if i < len(tokens) - 1:
            nxt      = tokens[i + 1]
            same_row = abs(tok["y_ctr"] - nxt["y_ctr"]) < 22
            if same_row:
                combo    = tok["text"] + " " + nxt["text"]
                h_avg    = (tok["h_px"] + nxt["h_px"]) / 2
                fake_tok = {**tok, "text": combo, "h_px": h_avg}
                if _is_valid_brand_token(fake_tok):
                    rel = _get_brand_relevance_score(combo)
                    candidates.append((combo, h_avg * rel))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[1], reverse=True)
    return _conservative_correct_text(candidates[0][0])


# ─────────────────────────────────────────────────────────────
# GENERIC NAME — the pharmaceutical classification line
# ─────────────────────────────────────────────────────────────
# On every Indian medicine label the generic name follows this pattern:
#   [Active Ingredient(s)] [Dosage Form] [Pharmapoeia Code]
#
# We detect it by finding the ROW (or consecutive rows) that contains
# BOTH a dosage-form word (Tablets/Injection/Syrup...) AND a
# pharmacopoeia code (IP/BP/USP).
#
# Examples:
#   "Adrenaline Injection IP"
#   "Rosuvastatin and Fenofibrate Tablets IP"
#   "Pantoprazole Gastro-Resistant Tablets IP 40 mg"
#   "Vitamin B Complex Syrup"          ← no pharma code, but has dosage form
# ─────────────────────────────────────────────────────────────

def _row_has_dosage_form(row_text: str) -> bool:
    """True if this row contains a dosage form word."""
    tl = row_text.lower()
    return any(w in tl for w in _DOSAGE_FORM_WORDS)


def _row_has_pharma_code(row_text: str) -> bool:
    """True if this row contains a pharmacopoeia code."""
    # Match IP/BP/USP as whole words (not inside longer words)
    return bool(re.search(
        r'\b(ip|bp|usp|ep|jp|i\.p\.|b\.p\.|u\.s\.p\.)\b',
        row_text, re.I
    ))


def _clean_generic_name(text: str) -> str:
    """
    Cleans up a generic name string:
    - Remove dose amounts that trail at the end (e.g. "... 40 mg")
    - Remove leading/trailing whitespace and punctuation
    - Collapse multiple spaces
    """
    t = text.strip()
    # Remove trailing dosage (e.g. "40 mg", "500 mg", "1 mg/ml")
    t = re.sub(r'\s+\d+[\.,]?\d*\s*(mg|ml|mcg|iu|g|mg/ml|%)[\s,\.]*$',
               '', t, flags=re.I).strip()
    t = re.sub(r'\s+', ' ', t)
    return t[:150]


def _extract_generic_name(rows: list[list[dict]]) -> str | None:
    """
    Finds the generic pharmaceutical name by scanning all rows for one
    that contains a dosage form word (and ideally a pharmacopoeia code).

    Strategy:
      Pass 1 — find row with BOTH dosage form + pharma code  (strongest)
      Pass 2 — find row with ONLY dosage form word           (fallback)

    The generic name is reconstructed from that row's tokens,
    filtering out obvious non-name tokens (pure numbers, units, codes).
    """

    def _row_text(row):
        return " ".join(t["text"] for t in row)

    def _rebuild_generic(row, extra_row=None):
        """
        Rebuild the generic name from a row's tokens.
        Keep: drug ingredient words, dosage form, pharma code.
        Drop: pure numbers (doses), units (mg/ml), MRP/price tokens.
        """
        parts = []
        for tok in row:
            t  = tok["text"].strip()
            tl = t.lower()
            # Drop pure numbers
            if re.fullmatch(r'\d+[\.,]?\d*', t):             continue
            # Drop standalone units
            if tl in _STOP_UNIT:                              continue
            # Drop field labels
            if _is_medicine_label_token(t):                   continue
            # Drop company/admin words
            if tl in (_STOP_ADMIN | _STOP_COMPANY | _STOP_FILLER): continue
            parts.append(t)

        if extra_row:
            for tok in extra_row:
                t  = tok["text"].strip()
                tl = t.lower()
                if re.fullmatch(r'\d+[\.,]?\d*', t):         continue
                if tl in _STOP_UNIT:                          continue
                if _is_medicine_label_token(t):               continue
                if tl in (_STOP_ADMIN | _STOP_COMPANY):       continue
                parts.append(t)

        return _clean_generic_name(" ".join(parts))

    # ── Pass 1: row has BOTH dosage form + pharma code ────
    for i, row in enumerate(rows):
        rt = _row_text(row)
        if _row_has_dosage_form(rt) and _row_has_pharma_code(rt):
            name = _rebuild_generic(row)
            if name and len(name) > 4:
                return _conservative_correct_text(name)

    # ── Pass 2: row has dosage form only ─────────────────
    for i, row in enumerate(rows):
        rt = _row_text(row)
        if _row_has_dosage_form(rt):
            # Sometimes the generic name spans 2 rows when it's long
            # e.g. "Rosuvastatin and Fenofibrate" on row N
            #      "Tablets IP"                   on row N+1
            # Check if the row BELOW also has dosage form or pharma code
            extra = None
            if i + 1 < len(rows):
                rt2 = _row_text(rows[i + 1])
                if _row_has_dosage_form(rt2) or _row_has_pharma_code(rt2):
                    extra = rows[i + 1]
            name = _rebuild_generic(row, extra)
            if name and len(name) > 4:
                return _conservative_correct_text(name)

    return None


# ══════════════════════════════════════════════════════════════
# SECTION 9 — PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════

def extract_text_from_image(image_path: str) -> dict:
    """
    Full OCR pipeline.

    Returns dict with:
      medicine_name   — brand name (largest font)  e.g. "ADLINE"
      generic_name    — generic/INN name            e.g. "Adrenaline Injection IP"
      batch           — batch number                e.g. "L1602423A"
      mfg_date        — manufacturing date          e.g. "10/2024"
      exp_date        — expiry date                 e.g. "09/2026"
      manufacturer    — company name                e.g. "Protech Telelinks"
      raw_text        — full OCR text for debugging
      word_count      — number of OCR tokens found
    """
    tmp_paths = []

    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        img   = _upscale(img, min_w=1000)
        img_h = img.shape[0]

        strategies = [
            ("std",   _pre_standard(img)),
            ("thr",   _pre_thresh(img)),
            ("foil",  _pre_foil(img)),
            ("up2x",  _pre_upscale2x(img)),
        ]

        best_tokens = []
        best_count  = -1
        best_score  = -1

        # Store results for all strategies for voting
        strategy_results = []

        for tag, proc in strategies:
            p = f"{image_path}_{tag}.jpg"
            cv2.imwrite(p, proc, [cv2.IMWRITE_JPEG_QUALITY, 95])
            tmp_paths.append(p)
            tokens = _run_ocr(p)
            
            if tokens:
                avg_conf = sum(t["conf"] for t in tokens) / len(tokens)
                # Weighted score: count (40%) + confidence (60%)
                score = (len(tokens) * 0.4) + (avg_conf * 100 * 0.6)
                
                # Perform extraction on this strategy's tokens
                tokens.sort(key=lambda t: (round(t["y_ctr"] / 12), t["x_ctr"]))
                ft = " ".join(t["text"] for t in tokens)
                rs = _group_into_rows(tokens, row_tol_px=20)
                flds = _extract_fields_spatial(rs)
                flds = _fallback_fields(ft, flds)
                bn = _extract_brand_name(tokens)
                gn = _extract_generic_name(rs)
                
                res = {
                    "tag": tag,
                    "tokens": tokens,
                    "fields": flds,
                    "brand_name": bn,
                    "generic_name": gn,
                    "score": score,
                    "avg_conf": avg_conf
                }
                strategy_results.append(res)

                if score > best_score:
                    best_score = score
                    best_tokens = tokens
                    best_count = len(tokens)

        if not strategy_results:
            return {
                "medicine_name": None, "generic_name": None, "brand_name": None,
                "raw_text": "", "mfg_date": None, "exp_date": None,
                "batch": None, "manufacturer": None,
                "word_count": 0,
                "error": "No text detected. Try better lighting or hold camera steady."
            }

        # ── ENSEMBLE VOTING / CONSENSUS ────────────────────────────
        from collections import Counter

        def get_consensus(key):
            vals = [r["fields"].get(key) for r in strategy_results if r["fields"].get(key)]
            if not vals: return None
            # Return the most frequent value
            return Counter(vals).most_common(1)[0][0]

        voted_batch = get_consensus("batch")
        voted_mfg   = get_consensus("mfg")
        voted_exp   = get_consensus("exp")
        
        # For names, we still prefer the highest scored strategy but can fallback
        best_res = sorted(strategy_results, key=lambda x: x["score"], reverse=True)[0]
        
        brand_name   = best_res["brand_name"]
        generic_name = best_res["generic_name"]
        
        # If best strategy failed on a field but others agreed, use the voted one
        batch = voted_batch or best_res["fields"].get("batch")
        mfg   = voted_mfg   or best_res["fields"].get("mfg")
        exp   = voted_exp   or best_res["fields"].get("exp")
        mfr   = best_res["fields"].get("manufacturer")

        full_text = " ".join(t["text"] for t in best_res["tokens"])
        medicine_name = generic_name or brand_name

        print("\n" + "="*60)
        print("[OCR] ENGINE v6 — ENSEMBLE RESULTS")
        print(f"   Best Strategy: {best_res['tag']} (score: {best_res['score']:.1f})")
        print(f"   Brand name   : {brand_name}")
        print(f"   Generic name : {generic_name}")
        print(f"   Batch No.    : {batch} (Voted: {voted_batch})")
        print(f"   Mfg date     : {mfg} (Voted: {voted_mfg})")
        print(f"   Exp date     : {exp} (Voted: {voted_exp})")
        print(f"   Manufacturer : {mfr}")
        print(f"   Tokens found : {len(best_res['tokens'])}")
        print("="*60)

        return {
            "medicine_name": medicine_name,
            "brand_name":    brand_name,
            "generic_name":  generic_name,
            "raw_text":      full_text[:1000],
            "mfg_date":      mfg,
            "exp_date":      exp,
            "batch":         batch,
            "manufacturer":  mfr,
            "word_count":    len(best_res["tokens"]),
        }

    except Exception as e:
        import traceback
        print(f"❌ OCR error: {e}")
        traceback.print_exc()
        return {
            "medicine_name": None, "generic_name": None, "brand_name": None,
            "raw_text": "", "mfg_date": None, "exp_date": None,
            "batch": None, "manufacturer": None,
            "word_count": 0, "error": str(e)
        }

    finally:
        for p in tmp_paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass