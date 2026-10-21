"""Stage 5 tests: the mobile web app files and the source labels shown under chatbot answers."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ayurvidya.sources import source_label, verse_label  # noqa: E402


class AppTests(unittest.TestCase):
    def test_source_labels(self):
        self.assertEqual(verse_label("su.ni.1.13"), "Su. Ni. 1.13")
        self.assertEqual(source_label("step:su.ni.1.3:5"), "Bhavartha of Su. Ni. 1.3")
        self.assertEqual(source_label("mula.su.ni.1.13"), "Sushruta Samhita, Su. Ni. 1.13")
        self.assertEqual(source_label("unknown.id"), "unknown.id")

    def test_web_files(self):
        web = ROOT / "web"
        for f in ("index.html", "app.js", "style.css", "manifest.webmanifest", "sw.js", "icon.svg"):
            self.assertTrue((web / f).exists(), f)
        manifest = json.loads((web / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        html = (web / "index.html").read_text(encoding="utf-8")
        self.assertIn('src="app.js"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)