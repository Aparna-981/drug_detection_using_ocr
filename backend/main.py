# -*- coding: utf-8 -*-
"""
main.py  v3
FastAPI backend — Drug Detection System
Uses SQLite database + improved PaddleOCR engine.

Start:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil, os, uuid

from database      import init_db, load_initial_dataset, get_stats, create_user, verify_user, get_pending_users, approve_user, reject_user, search_drugs, get_all_users
from ocr_engine    import extract_text_from_image
from drug_matcher  import check_drug
from pdf_converter import convert_pdf_to_csv
from excel_converter import convert_excel_to_db

app = FastAPI(
    title="Drug Detection API v3",
    description="Smart Banned Drug Detection — SQLite + PaddleOCR",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialise DB on startup
init_db()
load_initial_dataset()


# ─────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    stats = get_stats()
    return {
        "status":      "ok",
        "message":     "Drug Detection API v3 (SQLite + PaddleOCR) running!",
        "ocr_engine":  "PaddleOCR v2.7",
        "drug_count":  stats["total_drugs"],
        "alert_months": stats["alert_months"],
        "dataset_loaded": stats["total_drugs"] > 0,
    }


# ─────────────────────────────────────────────────────────────
# POST /scan
import json
from PIL import Image
import cv2
import zxingcpp
import pyzbar.pyzbar as pyzbar
import re

def parse_raw_barcode(raw: str) -> dict:
    raw = raw.strip()
    batch_no = ""
    exp_date = ""
    drug_name = ""
    manufacturer = ""

    # 1. Try generic JSON (some QRs are just JSON)
    try:
        data = json.loads(raw)
        batch_no = str(data.get("batch", data.get("batch_no", data.get("Batch", ""))))
        exp_date = str(data.get("exp", data.get("expiry", data.get("Expiry", data.get("exp_date", "")))))
        drug_name = str(data.get("name", data.get("drug_name", data.get("drug", data.get("Name", "")))))
        manufacturer = str(data.get("manufacturer", data.get("mfg", data.get("company", data.get("mfg_by", "")))))
    except json.JSONDecodeError:
        pass

    # 2. Try GS1 Parsing
    if not batch_no and "10" in raw:
        clean_raw = raw.replace('\\x1d', '\x1d')
        m17 = re.search(r'17(\d{2})(\d{2})(\d{2})', clean_raw)
        if m17 and not exp_date:
            yy, mm, dd = m17.groups()
            exp_date = f"{mm}/20{yy}"
            
        m10 = re.search(r'10([A-Za-z0-9\-\_\+\.]+?)(?:\x1d|$)', clean_raw)
        if m10 and not batch_no:
            batch_no = m10.group(1)
            
        if not m10:
            m_fallback = re.search(r'17\d{6}.*?10([A-Za-z0-9\-]{3,20})$', clean_raw)
            if m_fallback:
                batch_no = m_fallback.group(1)

    return {
        "batch": batch_no.strip(), 
        "exp": exp_date.strip(), 
        "name": drug_name.strip(),
        "manufacturer": manufacturer.strip(),
        "raw": raw
    }

# ─────────────────────────────────────────────────────────────
@app.post("/scan")
async def scan_medicine(file: UploadFile = File(...)):
    ALLOWED = {"image/jpeg","image/jpg","image/png","image/webp"}
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "Please upload a JPG or PNG image.")

    ext       = os.path.splitext(file.filename or "img.jpg")[1] or ".jpg"
    save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")

    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(500, f"File save failed: {e}")

    try:
        print(f"\n📸 Scanning: {file.filename}")
        
        bc_batch = ""
        bc_exp = ""
        bc_name = ""
        bc_mfg = ""
        bc_raw = ""
        try:
            img_cv = cv2.imread(save_path)
            
            # Convert to grayscale to significantly improve barcode/QR detection contrast
            gray_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

            # 1. Try zxing-cpp first (Excellent for Pharma DataMatrix & QRs)
            zxing_results = zxingcpp.read_barcodes(img_cv)
            if not zxing_results:
                zxing_results = zxingcpp.read_barcodes(gray_img) # fallback to grayscale
            
            if zxing_results:
                bc_raw = zxing_results[0].text
                print(f"   [!] zxing-cpp detected payload: {bc_raw}")
            else:
                # 2. Try OpenCV specialized QR Detector
                detector = cv2.QRCodeDetector()
                data, _, _ = detector.detectAndDecode(img_cv)
                if data:
                    bc_raw = data
                    print(f"   [!] cv2 QRCodeDetector detected payload: {bc_raw}")
                else:
                    # 3. Fallback to pyzbar (Good for generic 1D barcodes)
                    img = Image.open(save_path)
                    decoded = pyzbar.decode(img)
                    if decoded:
                        bc_raw = decoded[0].data.decode('utf-8', errors='ignore')
                        print(f"   [!] pyzbar detected payload: {bc_raw}")

            if bc_raw:
                bc_info = parse_raw_barcode(bc_raw)
                bc_batch = bc_info.get("batch", "")
                bc_exp = bc_info.get("exp", "")
                bc_name = bc_info.get("name", "")
                bc_mfg = bc_info.get("manufacturer", "")
                print(f"   [+] Parsed Barcode -> Batch='{bc_batch}', Exp='{bc_exp}', Name='{bc_name}'")
            else:
                print("   [!] No barcode found in the uploaded image pixels.")
        except Exception as e:
            print(f"   [-] Barcode parsing bypassed: {e}")

        extracted = extract_text_from_image(save_path)

        # Override OCR data with 100% accurate Barcode data if found!
        med_name = bc_name if bc_name else extracted.get("medicine_name")
        exp_date = bc_exp if bc_exp else extracted.get("exp_date")
        batch    = bc_batch if bc_batch else extracted.get("batch")
        mfg      = bc_mfg if bc_mfg else extracted.get("manufacturer")

        drug_result = check_drug(
            drug_name=med_name,
            batch_no=batch,
            exp_date=exp_date,
        )

        return JSONResponse({
            "ocr": {
                "medicine_name": med_name     or "Not detected",
                "mfg_date":      extracted.get("mfg_date")      or "Not detected",
                "exp_date":      exp_date     or "Not detected",
                "batch":         batch        or "Not detected",
                "manufacturer":  mfg          or "Not detected",
                "raw_text":      extracted.get("raw_text","")[:500],
                "word_count":    extracted.get("word_count", 0),
                "barcode_raw":   bc_raw,
            },
            "result": drug_result,
        })
    except Exception as e:
        raise HTTPException(500, f"Processing error: {e}")
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)


# ─────────────────────────────────────────────────────────────
# POST /check-manual
# ─────────────────────────────────────────────────────────────
@app.post("/check-manual")
async def check_manual(
    drug_name: str = Form(...),
    batch_no:  str = Form(default=""),
    exp_date:  str = Form(default=""),
):
    if not drug_name.strip():
        raise HTTPException(400, "Drug name cannot be empty.")

    print(f"\n🔎 Manual: '{drug_name}'  batch='{batch_no}'  exp='{exp_date}'")
    result = check_drug(
        drug_name=drug_name.strip(),
        batch_no=batch_no.strip() or None,
        exp_date=exp_date.strip() or None,
    )
    return JSONResponse({
        "input": {
            "drug_name": drug_name,
            "batch_no":  batch_no  or "Not provided",
            "exp_date":  exp_date  or "Not provided",
        },
        "result": result,
    })


# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# POST /upload-dataset
# ─────────────────────────────────────────────────────────────
@app.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    name_low = (file.filename or "").lower()
    
    if not (name_low.endswith(".pdf") or name_low.endswith(".xlsx") or name_low.endswith(".xls")):
        raise HTTPException(400, "Please upload a PDF or Excel (.xlsx, .xls) file.")

    ext       = os.path.splitext(name_low)[1]
    save_path = os.path.join(UPLOAD_DIR, f"upload_{uuid.uuid4().hex}{ext}")
    
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"📥 Received file: '{file.filename}', detected ext: '{ext}', saved to: {save_path}")
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {e}")

    # Route based on extension
    if ext == ".pdf":
        res = convert_pdf_to_csv(save_path)
        err_msg = "Could not extract tables from this PDF. Please ensure it is a standard CDSCO NSQ Alert PDF."
    else:
        res = convert_excel_to_db(save_path)
        err_msg = "Could not parse this Excel file. Ensure it contains drug data columns (Batch, Name, etc.)."

    # Cleanup temp file
    if os.path.exists(save_path):
        os.remove(save_path)

    if not res:
        return JSONResponse(status_code=422, content={
            "status":  "error",
            "message": err_msg,
        })

    return JSONResponse({
        "status":      "success",
        "message":     f"✅ {res['new_count']} new drugs added "
                       f"({res['count']} total in database).",
        "drug_count":  res["count"],
        "new_count":   res["new_count"],
        "alert_month": res["alert_month"],
    })


# ─────────────────────────────────────────────────────────────
# GET /dataset-info
# ─────────────────────────────────────────────────────────────
@app.get("/dataset-info")
def dataset_info():
    stats = get_stats()
    return {
        "loaded":         stats["total_drugs"] > 0,
        "drug_count":     stats["total_drugs"],
        "alert_months":   stats["alert_months"],
        "recent_uploads": stats["recent_uploads"],
        "sample_drugs":   stats["sample_drugs"],
        "total_users":    stats["total_users"],
    }


# ─────────────────────────────────────────────────────────────
# AUTHENTICATION ENDPOINTS
# ─────────────────────────────────────────────────────────────
@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    res = create_user(username, password)
    if not res:
        raise HTTPException(400, "Username already exists.")
    return {"status": "success", "message": "Registered! Waiting for admin approval."}

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = verify_user(username, password)
    if not user:
        raise HTTPException(401, "Invalid username or password.")
    if user["role"] != "admin" and not user["is_approved"]:
        raise HTTPException(403, "Account pending admin approval.")
    return {
        "status": "success",
        "username": user["username"],
        "role": user["role"]
    }

# ─────────────────────────────────────────────────────────────
# ADMIN USER MANAGEMENT
# ─────────────────────────────────────────────────────────────
@app.get("/admin/users/pending")
def pending_users():
    return get_pending_users()

@app.post("/admin/users/approve/{user_id}")
def do_approve(user_id: int):
    approve_user(user_id)
    return {"status": "success"}

@app.post("/admin/users/reject/{user_id}")
def do_reject(user_id: int):
    reject_user(user_id)
    return {"status": "success"}

@app.get("/admin/users")
def do_get_users():
    return get_all_users()

@app.get("/admin/drugs/search")
def do_search(q: str = ""):
    return search_drugs(q)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
