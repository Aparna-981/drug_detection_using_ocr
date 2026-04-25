import os
from pdf_converter import convert_pdf_to_csv
import pandas as pd

PDF_PATH = os.path.join("uploads", "nsq_dataset_upload.pdf")
CSV_PATH = "nsq_debug_output.csv"

if os.path.exists(PDF_PATH):
    print(f"📄 DEBUG: Testing extraction from {PDF_PATH}...")
    # convert_pdf_to_csv now returns a dict
    res = convert_pdf_to_csv(PDF_PATH, CSV_PATH)
    print(f"✅ Result: {res}")
    
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        print(f"📊 Debug CSV rows: {len(df)}")
        print(f"📋 Columns found: {list(df.columns)}")
        print(f"📝 First 3 rows:\n{df.head(3)}")
    else:
        print("❌ Debug CSV was NOT created!")
else:
    print(f"❌ PDF not found: {PDF_PATH}")
