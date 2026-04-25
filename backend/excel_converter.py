# -*- coding: utf-8 -*-
"""
excel_converter.py
─────────────────────────────────────────────────────────────
Converts Excel (XLSX, XLS) NSQ Alert sheets → inserts records into SQLite.
Reuses the same mapping logic as pdf_converter.py for consistency.
─────────────────────────────────────────────────────────────
"""

import pandas as pd
import re
import os
from database import insert_drugs, log_upload

# Standard column names we normalise everything to (Same as PDF)
COL_MAP = [
    ('Product/Drug Name',      ['name of drug','product/drug','drug name',
                                 'product name','medicine name', 'name of product']),
    ('Batch No.',              ['batch no','lot no','b.no','batch number']),
    ('Manufacturing Date',     ['date of manufacture','mfg date',
                                 'manufacturing date','manufacture date','d.o.m']),
    ('Expiry Date',            ['date of expiry','expiry date',
                                 'exp date','date of exp','d.o.e']),
    ('Manufactured By',        ['manufactured by','name of manufacturer',
                                 'manufacturer','mfg by']),
    ('NSQ Result',             ['reason for failure','reasons for failure',
                                 'nsq result','defect', 'standard not met', 'nsq']),
    ('Reported by Laboratory', ['reported by','drawn by','laboratory',
                                 'lab name','cdl','rdtl', 'reporting source']),
    ('Alert Month',            ['reporting month & year', 'alert month', 'month']),
    ('S.No',                   ['s.no','sr.no','sl.no','serial no','s no']),
]

def _detect_alert_month(filename: str) -> str:
    """Try to guess the alert month from the filename."""
    m = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_]*(\d{4})',
                  filename, re.I)
    if m:
        return f"{m.group(1).capitalize()}-{m.group(2)}"
    return "Unknown"

def _map_excel_cols(df_cols):
    """Map raw Excel column headers → standard names."""
    mapping = {}
    for std, keywords in COL_MAP:
        for col in df_cols:
            if col in mapping: continue
            cl = str(col).lower().strip()
            if any(k in cl for k in keywords):
                mapping[col] = std
                break
    return mapping

def convert_excel_to_db(file_path: str) -> dict | None:
    """
    Reads NSQ Alert Excel and inserts records into SQLite.
    Returns result dict on success, None on failure.
    """
    alert_month = _detect_alert_month(os.path.basename(file_path))
    
    print(f"📊 Processing Excel: {file_path} (alert_month={alert_month})")
    
    try:
        # Load the excel file
        ext = os.path.splitext(file_path)[1].lower()
        engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
        
        df = pd.read_excel(file_path, engine=engine)
        
        if df.empty:
            print("❌ Excel file is empty.")
            return None
            
        # 1. Clean columns (strip whitespace, ensure string)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Map columns
        col_map = _map_excel_cols(df.columns)
        
        # 3. Check if we found the core columns
        if 'Product/Drug Name' not in col_map.values():
            # If standard headers not in header row, maybe they are in the first few rows?
            # CDs often have titles at the top. Let's try to find a row that looks like a header.
            found_header = False
            for i in range(min(10, len(df))):
                row_vals = [str(v).lower() for v in df.iloc[i].values]
                if any(kw in " ".join(row_vals) for kw in ['drug name','product','batch','s.no']):
                    # Use this row as header
                    df.columns = [str(v).strip() for v in df.iloc[i].values]
                    df = df.iloc[i+1:].reset_index(drop=True)
                    col_map = _map_excel_cols(df.columns)
                    found_header = True
                    break
            
            if not found_header:
                print("❌ Could not identify column headers in Excel.")
                return None

        # 4. Convert rows to list of dicts for insert_drugs
        records = []
        for _, row in df.iterrows():
            rec = {}
            for col, std in col_map.items():
                val = str(row[col]).strip() if pd.notnull(row[col]) else ""
                if val.lower() == 'nan': val = ""
                rec[std] = val
            
            # Simple validation: must have a drug name
            dn = rec.get("Product/Drug Name", "").strip()
            if not dn or dn.lower() in ("nan", "product name", "drug name"):
                continue
                
            # Map standard keys to what insert_drugs expects
            rec_dict = {
                "drug_name":       dn,
                "batch_no":        rec.get("Batch No.", ""),
                "mfg_date":        rec.get("Manufacturing Date", ""),
                "expiry_date":     rec.get("Expiry Date", ""),
                "manufactured_by": rec.get("Manufactured By", ""),
                "nsq_result":      rec.get("NSQ Result", ""),
                "lab":             rec.get("Reported by Laboratory", ""),
            }
            # Temporary storage for alert month from column
            if rec.get("Alert Month"):
                rec_dict["_alert_month"] = rec["Alert Month"]
            
            records.append(rec_dict)

        if not records:
            print("❌ No valid records extracted from Excel.")
            return None

        # Try to get alert_month from the data if 'Alert Month' column was found
        # (just use the first record's value as they should all be the same for one upload)
        if records and records[0].get("_alert_month"):
            alert_month = records[0]["_alert_month"]
            # Clean up the temp key
            for r in records: r.pop("_alert_month", None)

        # 5. Insert and Log
        result = insert_drugs(records, alert_month=alert_month)
        log_upload(
            filename    = os.path.basename(file_path),
            alert_month = alert_month,
            drug_count  = result["total"],
            new_count   = result["new"],
        )

        print(f"✅ Excel processed: {result['total']} records, {result['new']} new.")
        return {
            "count": result["total"], 
            "new_count": result["new"],
            "alert_month": alert_month
        }

    except Exception as e:
        import traceback
        print(f"❌ Excel processing error: {e}")
        traceback.print_exc()
        return None
