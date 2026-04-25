# -*- coding: utf-8 -*-
"""
pdf_converter.py  v3
─────────────────────────────────────────────────────────────
Converts CDSCO NSQ Alert PDF → inserts records into SQLite.
Returns a result dict so main.py can report what was added.
─────────────────────────────────────────────────────────────
"""

import pdfplumber
import re
import os
from database import insert_drugs, log_upload

# Standard column names we normalise everything to
STANDARD_COLS = [
    'S.No', 'Product/Drug Name', 'Batch No.', 'Manufacturing Date',
    'Expiry Date', 'Manufactured By', 'NSQ Result', 'Reported by Laboratory'
]

COL_MAP = [
    ('Product/Drug Name',      ['name of drug','product/drug','drug name',
                                 'product name','medicine name', 'name of product', 'name of sample']),
    ('Batch No.',              ['batch no','lot no','b.no','batch number']),
    ('Manufacturing Date',     ['date of manufacture','mfg date',
                                 'manufacturing date','manufacture date','d.o.m']),
    ('Expiry Date',            ['date of expiry','expiry date',
                                 'exp date','date of exp','d.o.e']),
    ('Manufactured By',        ['manufactured by','name of manufacturer',
                                 'manufacturer','mfg by', 'mfg. details']),
    ('NSQ Result',             ['reason for failure','reasons for failure',
                                 'nsq result','defect','standard not met', 'nsq', 'remarks']),
    ('Reported by Laboratory', ['reported by','drawn by','laboratory',
                                 'lab name','cdl','rdtl', 'reporting source']),
    ('Alert Month',            ['reporting month & year', 'alert month', 'month']),
    ('S.No',                   ['s.no','sr.no','sl.no','serial no','s no', 'si. no']),
]


def _clean(v):
    if v is None: return ""
    return str(v).replace('\n',' ').strip()


def _map_cols(raw_headers):
    """Map raw PDF column headers → standard names."""
    mapping = {}
    used    = set()
    for std, keywords in COL_MAP:
        if std in used: continue
        for h in raw_headers:
            if h in mapping: continue
            hl = h.lower().strip()
            if any(k in hl for k in keywords):
                mapping[h] = std
                used.add(std)
                break
    return mapping


def _detect_alert_month(pdf_path: str) -> str:
    """Try to guess the alert month from the filename."""
    name = os.path.basename(pdf_path)
    m = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_]*(\d{4})',
                  name, re.I)
    if m:
        return f"{m.group(1).capitalize()}-{m.group(2)}"
    return "Unknown"


def convert_pdf_to_csv(pdf_path: str, _unused_csv_path: str = "") -> dict | None:
    """
    Reads NSQ Alert PDF and inserts records into SQLite.
    Returns {"count": total, "new_count": new_rows} on success, None on failure.
    """
    alert_month = _detect_alert_month(pdf_path)
    all_rows    = []
    headers     = None

    print(f"📄 Processing PDF: {pdf_path} (alert_month={alert_month})")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"   📂 PDF Opened: {len(pdf.pages)} pages found.")
            for pn, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                print(f"   📄 Page {pn+1}: Found {len(tables)} tables.")
                for table in tables:
                    if not table: continue
                    print(f"      🔍 Table with {len(table)} rows found.")
                    for row_idx, row in enumerate(table):
                        if not row or not any(c for c in row): continue
                        cleaned = [_clean(c) for c in row]
                        row_text = " ".join(cleaned).lower()
                        
                        if pn == 0 and row_idx < 3:
                            print(f"         Row {row_idx}: {cleaned[:3]}...") # Print first few columns

                        if headers is None and any(
                            kw in row_text for kw in
                            ['drug name','product','batch','s.no','sl.no']
                        ):
                            headers = cleaned
                            print(f"   ✅ Headers found on page {pn+1}: {headers}")
                            continue

                        if headers:
                            all_rows.append(cleaned)

    except Exception as e:
        print(f"❌ PDF read error: {e}")
        return None

    if not all_rows:
        print("❌ No data rows found.")
        return None

    if not headers:
        headers = ['S.No','Product/Drug Name','Batch No.',
                   'Manufacturing Date','Expiry Date',
                   'Manufactured By','NSQ Result','Reported by Laboratory']

    col_count  = len(headers)
    col_map    = _map_cols(headers)
    print(f"   🗺️ Mapped Columns: {col_map}")

    records = []
    for row in all_rows:
        if len(row) < col_count:
            row += [""] * (col_count - len(row))
        row = row[:col_count]
        row_dict = {h: row[i] for i, h in enumerate(headers)}

        drug_name = row_dict.get(
            next((h for h,s in col_map.items() if s=='Product/Drug Name'), ''), ''
        ).strip()
        if not drug_name or drug_name.isdigit():
            continue

        rec_item = {
            "drug_name":      drug_name,
            "batch_no":       row_dict.get(
                next((h for h,s in col_map.items() if s=='Batch No.'), ''), ''
            ).strip(),
            "mfg_date":       row_dict.get(
                next((h for h,s in col_map.items() if s=='Manufacturing Date'), ''), ''
            ).strip(),
            "expiry_date":    row_dict.get(
                next((h for h,s in col_map.items() if s=='Expiry Date'), ''), ''
            ).strip(),
            "manufactured_by": row_dict.get(
                next((h for h,s in col_map.items() if s=='Manufactured By'), ''), ''
            ).strip(),
            "nsq_result":     row_dict.get(
                next((h for h,s in col_map.items() if s=='NSQ Result'), ''), ''
            ).strip(),
            "lab":            row_dict.get(
                next((h for h,s in col_map.items() if s=='Reported by Laboratory'), ''), ''
            ).strip(),
        }
        # Temporary storage for alert month from column
        alert_col = next((h for h,s in col_map.items() if s=='Alert Month'), None)
        if alert_col and row_dict.get(alert_col):
            rec_item["_alert_month"] = row_dict[alert_col]
            
        records.append(rec_item)

    # Try to get alert_month from the data if 'Alert Month' column was found
    if records and records[0].get("_alert_month"):
        alert_month = records[0]["_alert_month"]
        for r in records: r.pop("_alert_month", None)

    if not records:
        print("❌ No valid records extracted.")
        return None

    result = insert_drugs(records, alert_month=alert_month)
    log_upload(
        filename    = os.path.basename(pdf_path),
        alert_month = alert_month,
        drug_count  = result["total"],
        new_count   = result["new"],
    )

    print(f"✅ PDF processed: {result['total']} records, {result['new']} new.")
    return {"count": result["total"], "new_count": result["new"],
            "alert_month": alert_month}
