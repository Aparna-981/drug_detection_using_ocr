# Drug Detection Using OCR
## Complete Setup Guide — PaddleOCR Edition
### Step-by-step for Beginners

---

## 📁 Project Folder Structure

```
drug_detection_using_ocr/
│
├── backend/                          ← Python server (runs on your PC)
│   ├── main.py                       ← FastAPI server (start this first)
│   ├── ocr_engine.py                 ← PaddleOCR image processing
│   ├── drug_matcher.py               ← NSQ database lookup + fuzzy match
│   ├── pdf_converter.py              ← Monthly PDF → CSV converter
│   └── requirements.txt              ← All Python packages needed
│
├── flutter_app/                      ← Mobile app
│   ├── pubspec.yaml                  ← Flutter packages list
│   └── lib/
│       ├── main.dart                 ← App entry point
│       ├── services/
│       │   └── api_service.dart      ← Communicates with backend
│       └── screens/
│           ├── home_screen.dart      ← Main menu
│           ├── scan_screen.dart      ← Camera scanning screen
│           ├── result_screen.dart    ← Shows NSQ result
│           ├── manual_screen.dart    ← Manual drug name entry
│           └── admin_screen.dart     ← Upload new NSQ PDF
│
└── SETUP_GUIDE.md                    ← This file
```

---

# PART 1 — Setting Up the Python Backend

## Step 1: Install Python

1. Go to: **https://python.org/downloads**
2. Download **Python 3.10** or **Python 3.11**
3. Run the installer
4. ✅ IMPORTANT: Check **"Add Python to PATH"** before clicking Install
5. Click Install Now

Verify installation — open Command Prompt and type:
```
python --version
```
You should see something like: `Python 3.11.5`

---

## Step 2: Install VS Code

1. Go to: **https://code.visualstudio.com**
2. Download and install (all default settings are fine)
3. Open VS Code after installation

---

## Step 3: Open the Backend Folder in VS Code

1. Open VS Code
2. Click **File → Open Folder**
3. Navigate to your project → select the **`backend`** folder
4. Click **Select Folder**

---

## Step 4: Open the Terminal in VS Code

Press **Ctrl + `** (backtick key, top-left of keyboard)

A terminal will open at the bottom of VS Code.

---

## Step 5: Create a Virtual Environment

A virtual environment keeps your project packages separate from the rest of your PC.

Type these commands one by one in the terminal:

```bash
python -m venv venv
```

Then activate it:

**Windows:**
```bash
venv\Scripts\activate
```

**Mac / Linux:**
```bash
source venv/bin/activate
```

✅ You will see **(venv)** appear at the start of the terminal line.
This means the virtual environment is active.

---

## Step 6: Install Python Packages

```bash
pip install -r requirements.txt
```

⏳ This will take **5–10 minutes** to download and install everything.
PaddleOCR needs to download its language models (~100MB) on first run.

---

## Step 7: Start the Backend Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see output like this:
```
📦 No dataset found — loading March 2025 NSQ sample data...
✅ Initial NSQ dataset loaded — 25 drugs from March 2025 alert.
🔄 Loading PaddleOCR model (first run downloads ~100MB)...
✅ PaddleOCR loaded successfully!
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 8: Test the Server

Open your browser and go to:
```
http://localhost:8000/health
```

You should see:
```json
{
  "status": "ok",
  "message": "Drug Detection API (PaddleOCR) is running!",
  "ocr_engine": "PaddleOCR v2.7",
  "dataset_loaded": true,
  "drug_count": 25
}
```

🎉 **Backend is working!**

You can also view the full API documentation at:
```
http://localhost:8000/docs
```

---

## Step 9: (Optional) Enable GPU for Faster OCR

By default the app uses CPU which is perfectly fine.
If your PC has an NVIDIA GPU and you want faster scanning:

**Check if you have an NVIDIA GPU:**
```bash
nvidia-smi
```
If this shows your GPU name → proceed. If error → skip this step.

**Uninstall CPU version and install GPU version:**
```bash
pip uninstall paddlepaddle -y

# For CUDA 11.8:
pip install paddlepaddle-gpu==2.6.1.post118 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html

# For CUDA 12.1:
pip install paddlepaddle-gpu==2.6.1.post121 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
```

**Then in `ocr_engine.py`, change one line:**
```python
# Find this:
use_gpu=False,

# Change to:
use_gpu=True,
```

**Verify GPU is active:**
```python
import paddle
print(paddle.device.get_device())
# Should print: gpu:0
```

---

# PART 2 — Setting Up the Flutter App

## Step 10: Install Flutter SDK

1. Go to: **https://docs.flutter.dev/get-started/install/windows**
2. Click **Download Flutter SDK**
3. Extract the downloaded zip to **C:\flutter**
   - Make sure the path is exactly `C:\flutter\bin\flutter.exe`

**Add Flutter to PATH:**
1. Search **"Environment Variables"** in Windows Start menu
2. Click **"Edit the system environment variables"**
3. Click **"Environment Variables"** button
4. Under **"System variables"** find **Path** → click **Edit**
5. Click **New** → type `C:\flutter\bin`
6. Click OK on all windows

**Verify:**
Open a NEW Command Prompt window and type:
```
flutter --version
```
You should see: `Flutter 3.x.x`

---

## Step 11: Install Android Studio

1. Go to: **https://developer.android.com/studio**
2. Download and install Android Studio
3. During setup, select:
   - ✅ Android SDK
   - ✅ Android SDK Platform
   - ✅ Android Virtual Device (AVD)
4. Finish the setup wizard

---

## Step 12: Set Up Flutter in VS Code

1. Open VS Code
2. Click the **Extensions** icon on the left sidebar (or press Ctrl+Shift+X)
3. Search for **"Flutter"** → Install the Flutter extension by Dart Code
4. Search for **"Dart"** → Install the Dart extension by Dart Code

**Run Flutter Doctor to check everything:**

Open a new terminal in VS Code and type:
```bash
flutter doctor
```

You may see some items with ✗. Fix them:

**If "Android toolchain" has issues:**
```bash
flutter doctor --android-licenses
```
Press **y** for every question.

**If "Visual Studio" is missing (Windows only):**
- This is only needed for Windows desktop apps
- For Android development only, you can ignore this

---

## Step 13: Open Flutter Project in VS Code

1. In VS Code → **File → Open Folder**
2. Navigate to your project → select **`flutter_app`** folder
3. Click **Select Folder**
4. A popup may appear asking to run `flutter pub get` → click **Yes**

If no popup, open terminal and run:
```bash
flutter pub get
```

You should see: `Got dependencies!`

---

## Step 14: Configure Your PC's IP Address

This is the most important configuration step.

**Find your PC's IP address:**

Open Command Prompt and type:
```
ipconfig
```

Look for **"IPv4 Address"** under your WiFi adapter.
Example: `192.168.1.5`

**Update the Flutter app:**

1. Open `lib/services/api_service.dart`
2. Find this line near the top:
```dart
const String BASE_URL = "http://10.0.2.2:8000";
```

3. Change it based on how you are testing:

**If using Android Emulator on the same PC:**
```dart
const String BASE_URL = "http://10.0.2.2:8000";
```
Keep it as `10.0.2.2` — this automatically points to your PC's localhost from the emulator.

**If using a real Android phone:**
```dart
const String BASE_URL = "http://192.168.1.5:8000";
```
Replace `192.168.1.5` with YOUR actual PC IP address.

⚠️ Your phone and PC must be connected to the **same WiFi network**.

---

## Step 15: Create an Android Emulator

1. Open **Android Studio**
2. Click **More Actions → Virtual Device Manager**
   (or Tools → Device Manager)
3. Click **Create Device**
4. Select **Pixel 6** → click Next
5. Select **API Level 33** (Android 13)
   - Click the download button next to it if not already downloaded
6. Click Next → Finish
7. Click the **Play (▶)** button to start the emulator

Wait for the emulator to fully boot (shows the Android home screen).

---

## Step 16: Run the Flutter App

Make sure:
- ✅ Python backend is running (Step 7)
- ✅ Android emulator is open OR real phone is connected

In VS Code terminal (inside the flutter_app folder):
```bash
flutter run
```

The app will build and launch on the emulator or phone.
First build takes 2–3 minutes. Subsequent runs are much faster.

---

# PART 3 — Using the App

## How to Scan a Medicine

1. Open the app → tap **"Scan Medicine"**
2. Take a photo of the medicine package
   - Place package on flat surface
   - Use good lighting
   - Make sure text is visible and not blurry
3. Tap **"Check Drug Safety"**
4. Wait 2–5 seconds for PaddleOCR to process
5. Result appears:
   - 🔴 **NSQ** → Drug is flagged as Not of Standard Quality
   - 🟠 **Expired** → Medicine expiry date has passed
   - 🟡 **Possible Match** → Low confidence match, verify manually
   - 🟢 **Safe** → Not found in NSQ list

## How to Check Manually

1. Tap **"Manual Entry"**
2. Type the drug name (e.g. `Pantoprazole`)
3. Optionally add batch number and expiry date
4. Tap **"Check Drug Safety"**

## How to Update the NSQ Dataset (Monthly)

Every month CDSCO releases a new NSQ Alert PDF.

1. Go to: **https://cdsco.gov.in**
   → Consumer → Not of Standard Quality Drug
2. Download the latest monthly PDF
3. Open the app → tap **"Update Dataset"** (Admin section)
4. Select the downloaded PDF
5. Tap **"Upload & Update Dataset"**
6. App will auto-convert and reload the database

---

# PART 4 — Running the App Every Day

Every time you want to use the app, follow these steps:

**Step 1 — Start the backend:**
```bash
# Open VS Code terminal in the backend folder
# Activate virtual environment
venv\Scripts\activate

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Step 2 — Start the emulator (if using emulator):**
- Open Android Studio → Device Manager → click Play ▶

**Step 3 — Run the Flutter app:**
```bash
# Open another terminal in the flutter_app folder
flutter run
```

---

# PART 5 — Troubleshooting

## "Cannot connect to server"
- Is the Python backend running? Check the terminal
- Check the IP address in `api_service.dart`
- Is your phone on the same WiFi as your PC?
- Try opening `http://YOUR_PC_IP:8000/health` in your phone browser

## "OCR not detecting medicine name"
- Take the photo in better lighting
- Hold camera steady, avoid blur
- Make sure the drug name text is clearly visible
- Try manual entry as backup

## PaddleOCR first run is very slow
- Normal — it downloads model files (~100MB) on first run
- Second run onwards will be much faster (models are cached)

## "flutter pub get" fails
- Check your internet connection
- Run `flutter doctor` and fix any issues shown

## App shows blank screen or crashes
- Check that the emulator is fully booted (shows home screen)
- Run `flutter clean` then `flutter pub get` then `flutter run`

## "venv\Scripts\activate is not recognized"
- Make sure you are in the backend folder
- Try: `python -m venv venv` first, then activate

## Port 8000 already in use
```bash
# Find what is using port 8000
netstat -ano | findstr :8000

# Kill it (replace PID with the number shown)
taskkill /PID [PID] /F
```

---

# PART 6 — API Endpoints Reference

| Method | URL | What it does |
|--------|-----|--------------|
| GET | `/health` | Check if server is running |
| POST | `/scan` | Upload medicine image for OCR |
| POST | `/check-manual` | Check drug by typed name |
| POST | `/upload-dataset` | Upload new NSQ PDF |
| GET | `/dataset-info` | Get database statistics |

Interactive API docs: **http://localhost:8000/docs**

---

# PART 7 — How the System Works

```
User takes photo
       ↓
Image sent to Python backend
       ↓
OpenCV preprocessing
(grayscale → CLAHE contrast → denoise → sharpen)
       ↓
PaddleOCR — 3-stage pipeline:
  Stage 1: Detect text regions in image
  Stage 2: Correct rotation / angle
  Stage 3: Read and recognise the text
       ↓
Extract: Medicine Name, Batch No., MFG Date, EXP Date
       ↓
Fuzzy match against NSQ database (FuzzyWuzzy)
       ↓
Check if expiry date has passed
       ↓
Return result to Flutter app
       ↓
Display result card:
🔴 NSQ | 🟠 Expired | 🟡 Possible | 🟢 Safe
```

---

*Project: Drug Detection Using OCR*
*OCR Engine: PaddleOCR v2.7 (CPU / GPU)*
*Stack: Flutter + Python FastAPI + PaddleOCR + FuzzyWuzzy*
*Dataset: CDSCO NSQ Monthly Alerts*
