# -*- coding: utf-8 -*-
"""
drug_matcher.py  v3
─────────────────────────────────────────────────────────────
Batch number is now the PRIMARY check.

Priority order:
  1. Batch exact match  → immediate NSQ alert (most reliable)
  2. Name fuzzy match   → NSQ alert with confidence score
  3. Expiry vs today    → EXPIRED flag
  4. Expiry vs DB       → counterfeit warning if mismatch
─────────────────────────────────────────────────────────────
"""

import re
from datetime import datetime
from fuzzywuzzy import fuzz, process
from database import (
    find_by_batch, find_by_name, get_all_drug_names,
    get_stats
)


# ─────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def _parse_month_year(s):
    if not s: return None, None
    s = str(s).strip().lower()
    # Replace common separators with space
    s = re.sub(r'[/.\-,]', ' ', s)
    # Remove common prefix words that might be attached
    s = re.sub(r'\b(exp|expiry|use by|valid till)\b', ' ', s)
    parts = [p for p in s.split() if p]
    if len(parts) >= 2:
        y_str = parts[-1]
        m_str = parts[-2]
        try:
            y = int(y_str)
            if y < 100: y += 2000
            m = None
            if m_str.isdigit():
                m = int(m_str)
            else:
                for k, v in MONTH_MAP.items():
                    if m_str.startswith(k):
                        m = v
                        break
            if m and 1 <= m <= 12:
                return m, y
        except Exception:
            pass
    elif len(parts) == 1 and len(parts[0]) >= 5:
        # e.g. "102026" or "10/26" without spaces
        pass # could add support if needed, but '10/2026' will split due to re.sub
    return None, None

def _parse_expiry(date_str):
    """Parse various dates to datetime of first day of next month."""
    m, y = _parse_month_year(date_str)
    if m and y:
        return datetime(y + (m == 12), (m % 12) + 1, 1)
    return None

def check_expiry(exp_str):
    dt = _parse_expiry(exp_str)
    return dt is not None and dt < datetime.now()

def _norm_date(s):
    m, y = _parse_month_year(s)
    if m and y:
        return f"{m:02d}/{y}"
    return None


# ─────────────────────────────────────────────────────────────
# String Match Helpers
# ─────────────────────────────────────────────────────────────
def clean_name(n):
    n = str(n).lower()
    # Strip punctuation like hyphens or slashes to prevent token splitting issues
    n = re.sub(r'[^\w\s]', ' ', n)

    # Remove common pharma suffixes/words that cause mismatch
    stopwords = [
        'tablet', 'capsule', 'syrup', 'injection', 'suspension', 'ointment', 
        'cream', 'mg', 'ml', 'gm', 'mcg', 'drop', 'solution', 'gel', 'lotion', 
        'powder', 'spray', 'ip', 'bp', 'usp', 'hcl', 'hydrochloride'
    ]
    for w in stopwords:
        n = re.sub(rf'\b{w}s?\b', '', n)
    
    # Remove multiple spaces
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def custom_scorer(s1, s2):
    # Combined score: token_set_ratio is good for subset matches, 
    # token_sort_ratio ensures we don't over-value small single-word matches.
    set_score = fuzz.token_set_ratio(s1, s2)
    sort_score = fuzz.token_sort_ratio(s1, s2)
    return int((set_score + sort_score) / 2)


# ─────────────────────────────────────────────────────────────
# Build result dict from a DB row
# ─────────────────────────────────────────────────────────────
def _row_to_detail(row: dict) -> dict:
    return {
        "matched_name":  row.get("drug_name"),
        "batch_in_db":   row.get("batch_no"),
        "mfg_in_db":     row.get("mfg_date"),
        "db_expiry":     row.get("expiry_date"),
        "manufacturer":  row.get("manufactured_by"),
        "nsq_reason":    row.get("nsq_result"),
        "lab":           row.get("lab"),
        "alert_month":   row.get("alert_month"),
    }


# ─────────────────────────────────────────────────────────────
# MAIN CHECK
# ─────────────────────────────────────────────────────────────
def check_drug(drug_name=None, batch_no=None, exp_date=None):
    """
    Full cross-check:
      • Batch number → exact DB lookup (HIGHEST PRIORITY)
      • Drug name    → fuzzy match
      • Expiry date  → vs today, vs DB record

    Returns dict with status, message, all detail fields.
    """

    result = {
        # verdict
        "status":               "UNKNOWN",
        "message":              "Drug not found in database. Please verify with a pharmacist.",
        # name match
        "match_score":          0,
        "matched_name":         None,
        # batch match
        "batch_matched":        None,    # True / False / None(not checked)
        "batch_match_note":     None,
        # expiry
        "is_expired":           False,
        "expiry_check": {
            "user_expiry":   exp_date,
            "db_expiry":     None,
            "matches_db":    None,
            "mismatch_note": None,
        },
        # DB detail
        "batch_in_db":    None,
        "mfg_in_db":      None,
        "db_expiry":      None,
        "manufacturer":   None,
        "nsq_reason":     None,
        "lab":            None,
        "alert_month":    None,
        "alerts": []
    }

    # ── 1. Expiry vs today ────────────────────────────────
    is_expired = check_expiry(exp_date)
    result["is_expired"] = is_expired
    if is_expired:
        result["status"]  = "EXPIRED"
        result["message"] = "⛔ This medicine is EXPIRED. Do not consume!"

    # ── 2. BATCH NUMBER CHECK (primary) ──────────────────
    if batch_no and batch_no.strip():
        batch_rows = find_by_batch(batch_no)
        result["batch_matched"] = len(batch_rows) > 0

        if batch_rows:
            row = batch_rows[0]
            detail = _row_to_detail(row)
            result.update(detail)

            # Check for drug name mismatch between extracted name and DB record
            db_name = row.get("drug_name")
            if drug_name and db_name:
                score = custom_scorer(clean_name(drug_name), clean_name(db_name))
                result["match_score"] = score
                if score < 65:
                    result["alerts"].append(f"⚠️ Drug name mismatch: extracted '{drug_name}' vs NSQ record '{db_name}' (match: {score}%).")
                else:
                    result["alerts"].append(f"ℹ️ Drug name matches NSQ record '{db_name}' (confidence: {score}%).")

            result["batch_match_note"] = (
                f"Batch '{batch_no}' was found in the NSQ database — "
                f"this specific batch is flagged as Not of Standard Quality."
            )
            result["status"]  = "NSQ"
            result["message"] = (
                f"⚠️ ALERT: Batch number '{batch_no}' is in the NSQ database! "
                f"This medicine is NOT of Standard Quality. Do NOT consume!"
            )

            # Alert if drug name is missing
            if not drug_name or not str(drug_name).strip():
                result["alerts"].append("⚠️ Drug name missing or could not be extracted.")

            # Expiry cross-check vs DB
            _do_expiry_check(result, exp_date, row.get("expiry_date"))
            return result

        else:
            result["batch_match_note"] = (
                f"Batch '{batch_no}' was NOT found in the NSQ database — "
                f"this batch is not individually listed as NSQ."
            )

    # ── 3. NAME FUZZY MATCH (Notification Only) ───────────
    if drug_name and str(drug_name).strip():
        drug_name = str(drug_name).strip()
        all_names = get_all_drug_names()

        if all_names:
            matches = process.extract(
                drug_name, all_names,
                processor=clean_name,
                scorer=custom_scorer, limit=10
            )
            if matches:
                best_name, main_score, *_ = matches[0]
                result["match_score"] = main_score

                matched_records = []
                # Fetch details for all matches that pass the threshold
                for m_name, m_score, *_ in matches:
                    if m_score >= 45:
                        name_rows = find_by_name(m_name)
                        for row in name_rows:
                            detail = _row_to_detail(row)
                            detail["match_score"] = m_score
                            # Add to array of all fetched records
                            matched_records.append(detail)

                if matched_records:
                    result["matched_db_records"] = matched_records
                    # Also populate root level for single checks backward compatibility
                    for k, v in matched_records[0].items():
                        if result.get(k) is None and k != "match_score":
                            result[k] = v

                # Main alert notification based strictly on the highest match
                if main_score >= 65:
                    result["alerts"].append(
                        f"⚠️ Name Notification: '{best_name}' is in the NSQ list "
                        f"(confidence: {main_score}%). Check the database records securely below."
                    )
                elif main_score >= 45:
                    result["alerts"].append(
                        f"ℹ️ Name Notification: Possible match with '{best_name}' "
                        f"(confidence: {main_score}%)."
                    )

    # Alert if drug name is missing
    if not drug_name or not str(drug_name).strip():
        result["alerts"].append("⚠️ Name Notification: Drug name missing or could not be extracted.")
        
    # ── 4. SAFE ───────────────────────────────────────────
    if result["status"] not in ("NSQ", "EXPIRED", "POSSIBLE_MATCH"):
        result["status"]  = "SAFE"
        result["message"] = (
            "✅ Not found in NSQ list. "
            "Appears safe — always verify with a pharmacist."
        )

    return result


# ─────────────────────────────────────────────────────────────
# Expiry cross-check helper
# ─────────────────────────────────────────────────────────────
def _do_expiry_check(result, user_exp, db_exp):
    u = _norm_date(user_exp)
    d = _norm_date(db_exp)
    ec = result["expiry_check"]
    ec["db_expiry"]  = db_exp
    result["db_expiry"] = db_exp

    if u and d:
        ec["matches_db"] = (u == d)
        if not ec["matches_db"]:
            ec["mismatch_note"] = (
                f"Expiry on your package ({u}) differs from the NSQ record ({d}). "
                f"This may indicate a relabelled or counterfeit product."
            )
            if result["status"] == "NSQ":
                result["message"] += (
                    " ⚠️ Expiry date mismatch with NSQ record — "
                    "possible counterfeiting."
                )


# ─────────────────────────────────────────────────────────────
# Re-export get_stats so main.py can import from one place
# ─────────────────────────────────────────────────────────────
def db_stats():
    return get_stats()
