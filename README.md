# Drug Detection Using OCR 💊🔍

A professional, mobile-first solution for verifying drug safety and authenticity. This system uses **PaddleOCR** to extract medicine details (Name, Batch No, MFG/EXP dates) from images and matches them against the official **CDSCO Not of Standard Quality (NSQ)** database.

---

## 🌟 Key Features

- **Advanced OCR Scanning**: High-accuracy text extraction from medicine packaging using a 3-stage PaddleOCR pipeline.
- **NSQ Database Matching**: Real-time fuzzy matching against the latest CDSCO monthly alerts.
- **Smart Expiry Detection**: Automatically flags medicines that have passed their expiration date.
- **Admin Dashboard**: Easy monthly dataset updates via PDF or Excel uploads.
- **Manual Verification**: Backup manual entry for low-visibility packaging.
- **High Performance**: Pre-processing (CLAHE, denoising) for reliable scanning even in poor lighting.

---

## 🛠️ Technology Stack

- **Frontend**: Flutter (Android/iOS)
- **Backend**: Python FastAPI
- **OCR Engine**: PaddleOCR v2.7 (CPU/GPU supported)
- **Database**: SQLite
- **Algorithms**: FuzzyWuzzy (string matching), OpenCV (image processing)

---

## 📁 Project Structure

```text
drug_detection_using_ocr/
├── backend/                # Python FastAPI Server
│   ├── main.py             # API Entry Point
│   ├── ocr_engine.py       # PaddleOCR Implementation
│   ├── drug_matcher.py     # Fuzzy Search Logic
│   └── excel_converter.py  # Dataset Processing
├── flutter_app/            # Cross-platform Mobile App
│   ├── lib/
│   │   ├── screens/        # UI Components
│   │   └── services/       # API Integration
│   └── pubspec.yaml        # Flutter Dependencies
└── SETUP_GUIDE.md          # Comprehensive Setup Instructions
```

---
## Demo Video




https://github.com/user-attachments/assets/3b3c5283-4fd4-4e86-a95e-fa82b12320ad







## 🚀 Quick Start

For detailed step-by-step instructions, please refer to the [**Complete Setup Guide**](./SETUP_GUIDE.md).

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Flutter Setup
```bash
cd flutter_app
flutter pub get
flutter run
```

---

## 📊 How it Works

1. **User captures image** of the medicine box.
2. **Backend processes image** using OpenCV to improve clarity.
3. **PaddleOCR extracts text** regions and reads labels.
4. **Fuzzy Matcher** compares extracted text with the SQLite database of flagged drugs.
5. **App displays result**:
   - 🔴 **NSQ**: Found in the flagged list.
   - 🟠 **Expired**: Date check failed.
   - 🟡 **Possible Match**: Low-confidence match found.
   - 🟢 **Safe**: No records found.

---

