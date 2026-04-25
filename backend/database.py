# -*- coding: utf-8 -*-
"""
database.py
─────────────────────────────────────────────────────────────
SQLite database for NSQ drug records.

Tables:
  nsq_drugs   — one row per NSQ drug record
  uploads     — history of every dataset upload

Why SQLite over CSV:
  • Batch number is indexed → instant O(1) lookup
  • Supports multiple months of data (append, not replace)
  • ACID transactions — no partial writes on crash
  • Easy to query with SQL
─────────────────────────────────────────────────────────────
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = "nsq_database.db"


# ─────────────────────────────────────────────────────────────
# Connection helper
# ─────────────────────────────────────────────────────────────
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row    # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")   # safer concurrent access
    return conn


# ─────────────────────────────────────────────────────────────
# CREATE TABLES
# ─────────────────────────────────────────────────────────────
def init_db():
    """Creates tables if they don't exist yet. Safe to call on every startup."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nsq_drugs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_name       TEXT    NOT NULL,
                batch_no        TEXT,
                mfg_date        TEXT,
                expiry_date     TEXT,
                manufactured_by TEXT,
                nsq_result      TEXT,
                lab             TEXT,
                alert_month     TEXT,       -- e.g. "March-2025"
                inserted_at     TEXT        -- ISO datetime
            );

            -- Fast batch number lookup (most critical check)
            CREATE INDEX IF NOT EXISTS idx_batch
                ON nsq_drugs (batch_no COLLATE NOCASE);

            -- Fast drug name lookup
            CREATE INDEX IF NOT EXISTS idx_name
                ON nsq_drugs (drug_name COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS uploads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT,
                alert_month TEXT,
                drug_count  INTEGER,
                new_count   INTEGER,
                uploaded_at TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL,  -- 'admin' or 'user'
                is_approved   INTEGER NOT NULL DEFAULT 0, -- 0=pending, 1=approved
                created_at    TEXT
            );
        """)
    
    # Create default admin if not exists
    import hashlib
    with _connect() as conn:
        admin = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not admin:
            hpwd = hashlib.sha256("admin123".encode()).hexdigest()
            conn.execute(
                "INSERT INTO users (username, password_hash, role, is_approved, created_at) VALUES (?,?,?,?,?)",
                ("admin", hpwd, "admin", 1, datetime.now().isoformat())
            )
    print("✅ SQLite database ready:", DB_PATH)


# ─────────────────────────────────────────────────────────────
# INSERT records from a list of dicts
# ─────────────────────────────────────────────────────────────
def insert_drugs(records: list[dict], alert_month: str = "") -> dict:
    """
    Inserts a list of drug records into the database.
    Skips duplicates: same drug_name + batch_no combination.
    Returns {"total": N, "new": M}.
    """
    inserted_at = datetime.now().isoformat()
    new_count   = 0
    total       = len(records)

    with _connect() as conn:
        for r in records:
            drug_name = (r.get("drug_name") or r.get("Product/Drug Name") or "").strip()
            batch_no  = (r.get("batch_no")  or r.get("Batch No.")         or "").strip().upper()
            if not drug_name:
                continue

            # Check duplicate (same name + batch)
            existing = conn.execute(
                "SELECT id FROM nsq_drugs WHERE drug_name=? AND batch_no=?",
                (drug_name, batch_no)
            ).fetchone()

            if existing:
                continue    # skip duplicate

            conn.execute(
                """INSERT INTO nsq_drugs
                   (drug_name, batch_no, mfg_date, expiry_date,
                    manufactured_by, nsq_result, lab, alert_month, inserted_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    drug_name,
                    batch_no or None,
                    (r.get("mfg_date") or r.get("Manufacturing Date") or "").strip() or None,
                    (r.get("expiry_date") or r.get("Expiry Date") or "").strip() or None,
                    (r.get("manufactured_by") or r.get("Manufactured By") or "").strip() or None,
                    (r.get("nsq_result") or r.get("NSQ Result") or "").strip() or None,
                    (r.get("lab") or r.get("Reported by Laboratory") or "").strip() or None,
                    alert_month,
                    inserted_at,
                )
            )
            new_count += 1

    return {"total": total, "new": new_count}


# ─────────────────────────────────────────────────────────────
# LOG an upload event
# ─────────────────────────────────────────────────────────────
def log_upload(filename, alert_month, drug_count, new_count):
    with _connect() as conn:
        conn.execute(
            """INSERT INTO uploads (filename, alert_month, drug_count,
               new_count, uploaded_at) VALUES (?,?,?,?,?)""",
            (filename, alert_month, drug_count, new_count,
             datetime.now().isoformat())
        )


# ─────────────────────────────────────────────────────────────
# LOOKUP BY BATCH NUMBER (primary check — most reliable)
# ─────────────────────────────────────────────────────────────
def find_by_batch(batch_no: str) -> list[dict]:
    """
    Returns all NSQ records matching the batch number (case-insensitive).
    Empty list if not found.
    """
    if not batch_no:
        return []
    # Normalise: strip spaces and dashes for comparison
    norm = batch_no.strip().upper().replace(" ", "").replace("-", "")
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM nsq_drugs
               WHERE REPLACE(REPLACE(UPPER(batch_no),' ',''),'-','') = ?""",
            (norm,)
        ).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# FETCH ALL DRUG NAMES (for fuzzy matching)
# ─────────────────────────────────────────────────────────────
def get_all_drug_names() -> list[str]:
    """Returns list of all unique drug names for fuzzy matching."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT drug_name FROM nsq_drugs ORDER BY drug_name"
        ).fetchall()
    return [r["drug_name"] for r in rows]


# ─────────────────────────────────────────────────────────────
# FETCH RECORDS BY DRUG NAME (exact)
# ─────────────────────────────────────────────────────────────
def find_by_name(drug_name: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM nsq_drugs WHERE drug_name = ? COLLATE NOCASE",
            (drug_name,)
        ).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# USER AUTHENTICATION
# ─────────────────────────────────────────────────────────────
import hashlib

def create_user(username, password) -> bool:
    """Registers a new user as pending approval."""
    hpwd = hashlib.sha256(password.encode()).hexdigest()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, is_approved, created_at) VALUES (?,?,?,?,?)",
                (username, hpwd, "user", 0, datetime.now().isoformat())
            )
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password) -> dict:
    """Returns user dict if valid, else None."""
    hpwd = hashlib.sha256(password.encode()).hexdigest()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, hpwd)
        ).fetchone()
    return dict(row) if row else None

def get_pending_users() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, username, created_at FROM users WHERE is_approved = 0").fetchall()
    return [dict(r) for r in rows]

def approve_user(user_id: int):
    with _connect() as conn:
        conn.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))

def reject_user(user_id: int):
    with _connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

def get_all_users() -> list[dict]:
    """Retrieve all registered users."""
    with _connect() as conn:
        rows = conn.execute("SELECT id, username, role, is_approved, created_at FROM users ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────
# DATABASE STATS
# ─────────────────────────────────────────────────────────────
def get_stats() -> dict:
    with _connect() as conn:
        total  = conn.execute("SELECT COUNT(*) FROM nsq_drugs").fetchone()[0]
        months = conn.execute(
            "SELECT DISTINCT alert_month FROM nsq_drugs ORDER BY alert_month"
        ).fetchall()
        recent = conn.execute(
            "SELECT filename, alert_month, drug_count, new_count, uploaded_at "
            "FROM uploads ORDER BY id DESC LIMIT 5"
        ).fetchall()
        samples = conn.execute(
            "SELECT drug_name FROM nsq_drugs LIMIT 3"
        ).fetchall()
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return {
        "total_drugs":    total,
        "total_users":    users_count,
        "alert_months":   [r[0] for r in months if r[0]],
        "recent_uploads": [dict(r) for r in recent],
        "sample_drugs":   [r[0] for r in samples],
    }

def search_drugs(query: str) -> list[dict]:
    """Search for drugs by name or batch number."""
    if not query:
        return []
    q = f"%{query.strip().lower()}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM nsq_drugs 
               WHERE drug_name LIKE ? OR batch_no LIKE ? 
               ORDER BY drug_name COLLATE NOCASE""",
            (q, q)
        ).fetchall()
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────
# LOAD INITIAL March-2025 DATASET (runs once on first startup)
# ─────────────────────────────────────────────────────────────
def load_initial_dataset():
    """Inserts March 2025 CDSCO NSQ data if the database is empty."""
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM nsq_drugs").fetchone()[0]
    if count > 0:
        return   # already loaded

    records = [
        {"drug_name": "Amoxicillin Sodium and Clavulanate Potassium (Sterile) 5:1",
         "batch_no": "4032409004", "mfg_date": "09/2024", "expiry_date": "08/2028",
         "manufactured_by": "M/s. Shandong New Time Pharmaceuticals Co. Ltd., China",
         "nsq_result": "Particulate Matter", "lab": "CDL, Kolkata"},
        {"drug_name": "Pantoprazole GastroResistant Tablets IP (Pantoshang-40)",
         "batch_no": "SP240165", "mfg_date": "06/2024", "expiry_date": "05/2026",
         "manufactured_by": "M/s. Shangrila Industries (P) Ltd., East Sikkim",
         "nsq_result": "Dissolution (Buffer Stage)", "lab": "CDL, Kolkata"},
        {"drug_name": "Pantoprazole tablets IP 40 mg",
         "batch_no": "0081", "mfg_date": "05/2024", "expiry_date": "04/2026",
         "manufactured_by": "M/s. Hindustan Antibiotics Ltd., Pimpri, Pune",
         "nsq_result": "Dissolution (Buffer Stage)", "lab": "CDL, Kolkata"},
        {"drug_name": "Adrenaline Bitartrate Injection IP (Reoline Injection)",
         "batch_no": "AD-204", "mfg_date": "11/2024", "expiry_date": "04/2026",
         "manufactured_by": "M/s. Rathi Laboratories (Hindustan) Pvt. Ltd., Patna",
         "nsq_result": "Appearance of solution, Particulate matter and Description",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Bupivacaine Hydrochloride In Dextrose Injection USP",
         "batch_no": "AA4009", "mfg_date": "03/2024", "expiry_date": "02/2026",
         "manufactured_by": "M/s. Aishwarya Healthcare, South Sikkim",
         "nsq_result": "Particulate matter (visible) and Description", "lab": "CDL, Kolkata"},
        {"drug_name": "Montelukast and Levocetirizine Tablet (Dumont-L)",
         "batch_no": "DML 062", "mfg_date": "12/2024", "expiry_date": "11/2027",
         "manufactured_by": "M/s. Hygeia Pharmaceuticals Mfg (P) Ltd., West Bengal",
         "nsq_result": "Dissolution of Levocetirizine Hydrochloride and Montelukast",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Nitrazepam Tablets I.P. 10 mg (Nitravet-10)",
         "batch_no": "AXI23003P", "mfg_date": "09/2023", "expiry_date": "02/2028",
         "manufactured_by": "M/s. Anglo-French Drugs & Industries Limited, Bengaluru",
         "nsq_result": "Spurious - Identification and Assay of Nitrazepam",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Vitamin B Complex Syrup (B-Complex Syrup)",
         "batch_no": "BOB-2440", "mfg_date": "06/2024", "expiry_date": "11/2025",
         "manufactured_by": "M/s. Apple Formulations Pvt. Ltd., Roorkee",
         "nsq_result": "Assay of Vitamin B12", "lab": "CDL, Kolkata"},
        {"drug_name": "Itraconazole Capsules BP 100 mg (Fungis-100)",
         "batch_no": "C4050", "mfg_date": "06/2024", "expiry_date": "05/2026",
         "manufactured_by": "M/s. Merril Pharma Pvt. Ltd., Ahmedabad",
         "nsq_result": "Dissolution", "lab": "CDL, Kolkata"},
        {"drug_name": "Gentamicin Sulphate Injection IP (GENTAMICIN)",
         "batch_no": "GN-37", "mfg_date": "09/2024", "expiry_date": "08/2026",
         "manufactured_by": "M/s. Amba Research Laboratories, Patna",
         "nsq_result": "Sterility, Particulate Matter and Description",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Ceftriaxone and Sulbactam for Injection IP (Cefamed-S)",
         "batch_no": "B4CT05E", "mfg_date": "10/2024", "expiry_date": "09/2026",
         "manufactured_by": "M/s. Lenus Lifecare Pvt. Ltd., Solan, H.P.",
         "nsq_result": "Clarity of Solution, Particulate matter and Description",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Pantoprazole Sodium Gastro-Resistant and Domperidone Capsules IP (Pantoryl-DSR)",
         "batch_no": "MC-24229", "mfg_date": "04/2024", "expiry_date": "03/2026",
         "manufactured_by": "M/s. Matins Healthcare Pvt. Ltd., Haridwar",
         "nsq_result": "Dissolution of Pantoprazole Sodium in Buffer stage",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Dexamethasone Sodium Phosphate Injection IP (Dexagain Injection)",
         "batch_no": "VHI274001", "mfg_date": "12/2024", "expiry_date": "11/2026",
         "manufactured_by": "M/s. Vidit Healthcare, Paonta Sahib, H.P.",
         "nsq_result": "Assay of Dexamethasone Sodium Phosphate",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Calcium Carbonate 500 mg + VIT. D3 250 IU TABLETS IP (CALXIA 500)",
         "batch_no": "GTL1258", "mfg_date": "12/2024", "expiry_date": "11/2026",
         "manufactured_by": "M/s. Gidsha Pharmaceuticals, Dahod, Gujarat",
         "nsq_result": "Dissolution (for Calcium)", "lab": "CDL, Kolkata"},
        {"drug_name": "Alprazolam Tablets I.P. 0.50 mg (Calmpik-05)",
         "batch_no": "AT24266", "mfg_date": "07/2024", "expiry_date": "06/2027",
         "manufactured_by": "M/s. Aarpik Pharmaceuticals Pvt. Ltd., Ahmedabad",
         "nsq_result": "Dissolution", "lab": "RDTL, Guwahati"},
        {"drug_name": "Telmisartan Tablets I.P. (DV-TELMI-40)",
         "batch_no": "GTE2206", "mfg_date": "08/2024", "expiry_date": "07/2026",
         "manufactured_by": "M/s. Digital Vision, Sirmour, H.P.",
         "nsq_result": "Dissolution", "lab": "RDTL, Guwahati"},
        {"drug_name": "Domperidone Suspension IP",
         "batch_no": "DPS3-24-225", "mfg_date": "08/2024", "expiry_date": "07/2026",
         "manufactured_by": "M/s. Ornate Labs Pvt. Ltd., Muzaffarpur",
         "nsq_result": "Total aerobic viable count and Assay of Domperidone",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Atorvastatin Tablets IP (GATOVAS-20)",
         "batch_no": "CT24250423", "mfg_date": "06/2024", "expiry_date": "05/2026",
         "manufactured_by": "M/s. CMG Biotech Pvt. Ltd., Himachal Pradesh",
         "nsq_result": "Related substances", "lab": "CDTL-Mumbai"},
        {"drug_name": "Iron Sucrose Injection USP (I-PIC)",
         "batch_no": "A24105K", "mfg_date": "06/2024", "expiry_date": "05/2026",
         "manufactured_by": "M/s. Pace Biotech, Paonta Sahib, H.P.",
         "nsq_result": "Particulate matter in Injections", "lab": "CDL, Kolkata"},
        {"drug_name": "Sacubitril and Valsartan Tablets 50 mg (SVJAJ 50)",
         "batch_no": "SVA04H24C", "mfg_date": "08/2024", "expiry_date": "07/2026",
         "manufactured_by": "M/s. Bajaj Healthcare Ltd., Vadodara, Gujarat",
         "nsq_result": "Assay of Sacubitril and Valsartan", "lab": "CDTL-Mumbai"},
        {"drug_name": "Rabeprazole Sodium Injection I.P.",
         "batch_no": "MD23H29", "mfg_date": "08/2023", "expiry_date": "07/2025",
         "manufactured_by": "M/s. Martin and Brown Bio-sciences, Baddi, Solan, H.P.",
         "nsq_result": "Particulate matter, Related Substances, Clarity of solution, pH, Assay",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Cholecalciferol Vitamin D3 60000 IU Granule Sachet",
         "batch_no": "TPD24015", "mfg_date": "07/2024", "expiry_date": "06/2026",
         "manufactured_by": "M/s. Affy Parenterals, Baddi, Solan, H.P.",
         "nsq_result": "Assay/content of Cholecalciferol (Vitamin D3)",
         "lab": "CDL, Kolkata"},
        {"drug_name": "Albendazole Tablets I.P. (DV-BEND 400)",
         "batch_no": "GTE1974", "mfg_date": "07/2024", "expiry_date": "06/2026",
         "manufactured_by": "M/s. Digital Vision, Kala-Amb, Sirmour, H.P.",
         "nsq_result": "Dissolution", "lab": "CDTL-Mumbai"},
        {"drug_name": "Gentamicin Sulphate Injection I.P. 30 ml (Gentalab)",
         "batch_no": "OGNI-037", "mfg_date": "07/2024", "expiry_date": "06/2026",
         "manufactured_by": "M/s. Laborate Pharmaceuticals India Ltd., Paonta Sahib, H.P.",
         "nsq_result": "Particulate matter and Description", "lab": "CDL, Kolkata"},
        {"drug_name": "Amoxycillin and Potassium Clavulanate Injection IP",
         "batch_no": "AB193049A", "mfg_date": "05/2023", "expiry_date": "04/2025",
         "manufactured_by": "M/s. ANG Lifesciences India Ltd., Solan, HP",
         "nsq_result": "Assay (Content of Clavulanic Acid)", "lab": "RDTL, Guwahati"},
    ]

    res = insert_drugs(records, alert_month="March-2025")
    print(f"✅ Initial dataset loaded — {res['new']} records inserted.")
