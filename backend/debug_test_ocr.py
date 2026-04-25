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
        # 0 vs O (only corrected when numeric context exists)
        self.assertEqual(_smart_correct_batch("B0O123"), "B00123")
        # 1 vs I (not corrected if alpha context)
        self.assertEqual(_smart_correct_batch("BATCHI23"), "BATCHI23")
        # Z vs 2 (always corrected if digits exist)
        self.assertEqual(_smart_correct_batch("LOTZ42"), "LOT242")
        # DOLO (no digits, no change)
        self.assertEqual(_smart_correct_batch("DOLO"), "DOLO")

    def test_date_correction(self):
        """Test if common OCR mistakes in dates are corrected."""
        try:
            val = _smart_correct_date("IO/ZOZ6")
            print(f"IO/ZOZ6 -> {val}")
            self.assertEqual(val, "10/2026")
        except Exception as e:
            print(f"Date test failed: {e}")
            raise

    def test_brand_relevance_score(self):
        """Test if pharmaceutical names get a boost."""
        try:
            parac_score = _get_brand_relevance_score("Paracetamol")
            random_score = _get_brand_relevance_score("XYZ Business")
            print(f"Paracetamol: {parac_score}, XYZ: {random_score}")
            self.assertGreater(parac_score, random_score)
        except Exception as e:
            print(f"Score test failed: {e}")
            raise

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOCRAccuracy)
    unittest.TextTestRunner(verbosity=2).run(suite)
