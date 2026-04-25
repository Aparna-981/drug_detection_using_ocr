# -*- coding: utf-8 -*-
"""
Verification Script — OCR Accuracy Improvements
Tests the internal logic of ocr_engine.py (Character correction, Voting, etc.)
"""

import sys
import os
import unittest

# Add current dir to path to import ocr_engine
sys.path.append(os.getcwd())

from ocr_engine import (
    _smart_correct_batch, 
    _smart_correct_date, 
    _get_brand_relevance_score
)

class TestOCRAccuracy(unittest.TestCase):

    def test_batch_correction(self):
        """Test if common OCR mistakes in batch numbers are corrected."""
        # 0 vs O
        self.assertEqual(_smart_correct_batch("B0O123"), "B00123")
        # 1 vs I
        self.assertEqual(_smart_correct_batch("BATCHI23"), "BATCH123")
        # Z vs 2
        self.assertEqual(_smart_correct_batch("LOTZ42"), "LOT242")
        # Mixed (if mostly digits)
        self.assertEqual(_smart_correct_batch("S5Z0O"), "55200")
        # Should NOT correct if mostly letters (could be a valid brand)
        self.assertEqual(_smart_correct_batch("DOLO"), "DOLO")

    def test_date_correction(self):
        """Test if common OCR mistakes in dates are corrected."""
        self.assertEqual(_smart_correct_date("IO/ZOZ6"), "10/2026")
        self.assertEqual(_smart_correct_date("SEP/I9"), "sep/19")
        self.assertEqual(_smart_correct_date("05/202s"), "05/2025")

    def test_brand_relevance_score(self):
        """Test if pharmaceutical names get a boost."""
        parac_score = _get_brand_relevance_score("Paracetamol")
        random_score = _get_brand_relevance_score("XYZ Business")
        
        self.assertGreater(parac_score, random_score, "Paracetamol should have higher relevance than generic text")
        
        # Test prefixes
        amoxi_score = _get_brand_relevance_score("Amoxicillin")
        self.assertGreater(amoxi_score, 1.0)
        
        # Test penalty for long text
        long_text_score = _get_brand_relevance_score("THIS IS A VERY LONG TEXT THAT SHOULD NOT BE A BRAND NAME")
        self.assertLess(long_text_score, 1.3)

if __name__ == "__main__":
    unittest.main()
