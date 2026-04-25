# -*- coding: utf-8 -*-
import sys
import os

# Assuming running from 'backend' directory
sys.path.append('.')

from excel_converter import convert_excel_to_db
from database import get_stats, init_db

def test_excel():
    init_db() # ensure tables exist in local nsq_database.db
    test_file = 'test_drugs.xlsx'
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        return

    stats_before = get_stats()
    print(f"Initial drug count: {stats_before['total_drugs']}")

    res = convert_excel_to_db(test_file)
    
    if res:
        print(f"✅ Success: {res['new_count']} new drugs added.")
        stats_after = get_stats()
        print(f"Final drug count: {stats_after['total_drugs']}")
    else:
        print("❌ Excel conversion failed.")

if __name__ == "__main__":
    test_excel()
