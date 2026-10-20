"""Vaishnavi's Stage 4 tests: chrF score and the paced AI wrapper.   python -m unittest tests.test_quality"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ayurvidya.evaluation.similarity import chrf  # noqa: E402
from ayurvidya.llm import MockLLM  # noqa: E402


class QualityTests(unittest.TestCase):
    def test_chrf(self):
        ref = "वायुः स्वयम्भूः भगवान्"
        self.assertEqual(chrf(ref, ref), 100.0)
        self.assertEqual(chrf("", ref), 0.0)
        self.assertEqual(chrf("xyz", ref), 0.0)
        close, far = chrf("वायुः स्वयंभूः भगवान्", ref), chrf("प्राणः", ref)
        self.assertGreater(close, 60)
        self.assertLess(far, close)
        self.assertEqual(chrf("a | b ||", "a । b ॥"), 100.0)   # danda styles count as the same

    def test_paced_llm(self):
        from generate_all import PacedLLM
        llm = PacedLLM(MockLLM(lambda s, u: "ok"), pause=0.2)
        self.assertEqual(llm.name, "mock")                    # cache key unchanged
        t0 = time.time()
        llm.complete("s", "u")
        llm.complete("s", "u")
        self.assertGreaterEqual(time.time() - t0, 0.19)
        self.assertEqual(llm.calls, 2)

    def test_english_check(self):
        from ayurvidya.steps import english_issue
        self.assertEqual(english_issue("Sushruta asks about the सुश्रुतः seat of वायु [R1].", "x"), [])
        self.assertTrue(english_issue("अस्मिन् अध्याये सुश्रुतः वायोः जिज्ञासाम् करोति [R1]।", "x"))

        
if __name__ == "__main__":
    unittest.main(verbosity=2)