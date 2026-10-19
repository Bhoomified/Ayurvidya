"""End-to-end and unit tests. Fully offline: TF-IDF embedder + MockLLM.

    python -m unittest discover -s tests -v        (or: pytest)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ayurvidya.chatbot import Chatbot  # noqa: E402
from ayurvidya.config import Settings  # noqa: E402
from ayurvidya.evaluation import cvi, retrieval_metrics as rm, stats  # noqa: E402
from ayurvidya.evaluation.rag_judge import faithfulness  # noqa: E402
from ayurvidya.export import export_xlsx  # noqa: E402
from ayurvidya.index import BM25, KnowledgeBase, bm25_tokens  # noqa: E402
from ayurvidya.ingest import build_chunks, load_gold_xlsx, load_mula, load_source_file  # noqa: E402
from ayurvidya.llm import MockLLM  # noqa: E402
from ayurvidya.pipeline import Orchestrator, neighbour_texts  # noqa: E402
from ayurvidya.retrieve import HybridRetriever, rrf  # noqa: E402
from ayurvidya.service import build_app  # noqa: E402
from ayurvidya.steps import STEP_SPECS, sampradanam, v_step2, v_step4  # noqa: E402
from ayurvidya.store import Store  # noqa: E402
from ayurvidya.text import (aksharas, count_aksharas, devanagari_to_iast, guess_metre,  # noqa: E402
                            iast_to_devanagari, split_padas, strip_verse_markers, to_devanagari)

MULA = ROOT / "data" / "raw" / "niimh_su_ni_1_mula.json"
GOLD = ROOT / "data" / "gold" / "su_ni_1_gold_1-30.xlsx"

COMMENTARY_FIXTURE = """# source_type: commentary
# work: TEST FIXTURE (not Dalhana)
# chapter: 1
# shloka: 13
वक्त्रसञ्चारीति मुखे सञ्चरणशीलः। देहधृक् देहधारकः।
# shloka: 43
मार्गरोधादिति रक्तेन वायुमार्गावरोधात्।
"""


class TextTests(unittest.TestCase):
    def test_aksharas(self):
        self.assertEqual(aksharas("भगवान्"), ["भ", "ग", "वान्"])
        self.assertEqual(len(aksharas("धन्वन्तरिं")), 4)
        self.assertEqual(count_aksharas("धन्वन्तरिं धर्मभृतां वरिष्ठममृतोद्भवम्"), 16)

    def test_padas_anushtubh(self):
        p = split_padas("धन्वन्तरिं धर्मभृतां वरिष्ठममृतोद्भवम् |\nचरणावुपसङ्गृह्य सुश्रुतः परिपृच्छति ||३||")
        self.assertEqual(p, ["धन्वन्तरिं धर्मभृतां", "वरिष्ठममृतोद्भवम्", "चरणावुपसङ्गृह्य", "सुश्रुतः परिपृच्छति"])

    def test_metre(self):
        sh, _ = load_mula(MULA)
        by = {s.number: s for s in sh}
        self.assertEqual(guess_metre(by["3"].text), "anushtubh")
        self.assertTrue(guess_metre(by["42"].text).startswith("trishtubh"))

    def test_every_padya_verse_gives_4_padas(self):
        sh, _ = load_mula(MULA)
        for s in sh:
            if not s.is_prose:
                self.assertEqual(len(split_padas(s.text)), 4, s.number)

    def test_transliteration_roundtrip(self):
        for w in ["धन्वन्तरिं धर्मभृतां", "वायुरित्यभिशब्दितः", "सोऽन्नं पचति", "कृच्छ्रमूत्रपुरीषत्वम्"]:
            self.assertEqual(iast_to_devanagari(devanagari_to_iast(w)), w)
        self.assertEqual(to_devanagari("vātavyādhinidānaṃ"), "वातव्याधिनिदानं")
        self.assertEqual(to_devanagari("What is Vata?"), "What is Vata?")

    def test_strip_markers(self):
        self.assertEqual(strip_verse_markers("पचति हि ||१६||"), "पचति हि")


class IngestTests(unittest.TestCase):
    def test_mula(self):
        sh, col = load_mula(MULA)
        self.assertEqual(len(sh), 90)                          # 91 verses, 1-2 joined
        self.assertEqual(sh[0].number, "1-2")
        self.assertTrue(sh[0].is_prose)
        self.assertTrue(col.startswith("इति"))
        v10 = next(s for s in sh if s.number == "10")
        self.assertIn("करोत्यकुपितोऽनिलः", v10.text)
        self.assertIn("इन्द्रियार्थोपसम्प्राप्तिं", v10.variant)
        v68 = next(s for s in sh if s.number == "68")
        self.assertNotIn("गर्भिणी", v68.text)
        self.assertIn("गर्भिणी", v68.variant)

    def test_gold(self):
        g = load_gold_xlsx(GOLD)
        self.assertEqual(len(g), 29)
        self.assertEqual(sorted(g["su.ni.1.3"]), [1, 2, 3, 4, 5, 6, 7])

    def test_source_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.txt"
            p.write_text(COMMENTARY_FIXTURE, encoding="utf-8")
            ch = list(load_source_file(p))
            self.assertEqual([c.shloka_ids for c in ch], [["su.ni.1.13"], ["su.ni.1.43"]])
            self.assertEqual(ch[0].source_type, "commentary")


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        sh, _ = load_mula(MULA)
        src = cls.tmp / "fixture.txt"
        src.write_text(COMMENTARY_FIXTURE, encoding="utf-8")
        cls.shlokas = sh
        cls.kb = KnowledgeBase.build(build_chunks(sh, load_gold_xlsx(GOLD), [src]), "tfidf", cls.tmp / "kb")
        cls.r = HybridRetriever(cls.kb)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_rrf(self):
        fused = rrf([[1, 2, 3], [3, 1, 4]], k=60)
        self.assertEqual(fused[0][0], 1)                       # 1/61 + 1/62 beats 3's 1/63 + 1/61
        self.assertAlmostEqual(fused[0][1], 1 / 61 + 1 / 62)

    def test_bm25_sandhi(self):
        bm = BM25([bm25_tokens("वायुरामाशये क्रुद्धः"), bm25_tokens("पित्तं दहति")])
        self.assertEqual(bm.search(bm25_tokens("वायुः"), 2)[0][0], 0)

    def test_sanskrit_query_finds_verse(self):
        for q, n in [("वक्त्रसञ्चारी प्राणः", "13"), ("पक्वाधानालयोऽपानः", "19"), ("gṛdhrasī", "74"),
                     ("शब्दवहं स्रोतो", "83")]:
            hits = self.r.search(q, k=3, source_types=["mula"])
            self.assertIn(f"mula.su.ni.1.{n}", [h.chunk.id for h in hits], q)

    def test_qrels_hybrid_beats_floor(self):
        qrels = [q for q in rm.load_qrels(ROOT / "data/eval/retrieval_qrels.jsonl")
                 if any("ऀ" <= c <= "ॿ" or c in "āīūṛṃḥśṣ" for c in q["query"])]
        rep = rm.evaluate(self.r, qrels, ks=(1, 5), modes=("hybrid",))
        self.assertGreaterEqual(rep["hybrid"]["recall@5"], 0.8)

    def test_context_pins_and_leakage_guard(self):
        hits = self.r.context_for_step("su.ni.1.13", "वक्त्रसञ्चारी", ("mula", "commentary", "gold"), 6, step=4)
        ids = [h.chunk.id for h in hits]
        self.assertEqual(ids[0], "mula.su.ni.1.13")           # pinned first
        self.assertIn("fixture.1", ids)                       # this verse's commentary pinned
        self.assertFalse(any(i.startswith("gold.su.ni.1.13.") for i in ids))   # no answer leakage
        golds = [h.chunk for h in hits if h.chunk.source_type == "gold"]
        self.assertTrue(golds and all(c.meta["step"] == 4 for c in golds))

    def test_persist_and_load(self):
        kb2 = KnowledgeBase.load(self.tmp / "kb")
        self.assertEqual(len(kb2.chunks), len(self.kb.chunks))
        h = HybridRetriever(kb2).search("वक्त्रसञ्चारी", 1, source_types=["mula"])
        self.assertEqual(h[0].chunk.id, "mula.su.ni.1.13")


class StepTests(unittest.TestCase):
    def test_sampradanam(self):
        sh, _ = load_mula(MULA)
        out = sampradanam(sh[1])
        self.assertTrue(out.startswith("1st पाद- धन्वन्तरिं धर्मभृतां"))
        prose = sampradanam(sh[0]).splitlines()
        self.assertEqual(prose[0], "अथातो")
        self.assertEqual(prose[2], "अथातो वातव्याधिनिदानं व्याख्यास्यामः")

    def test_validators(self):
        sh, _ = load_mula(MULA)
        s3 = sh[1]
        good = "\n".join(f"{i}. {w} — सुबन्त — पुं., प्रथमा, एकवचनम्" for i, w in
                         enumerate(["धन्वन्तरिम्", "धर्मभृताम्", "वरिष्ठम्", "अमृतोद्भवम्", "चरणौ", "सुश्रुतः"], 1))
        self.assertEqual(v_step2(good, s3, {}), [])
        self.assertTrue(v_step2("धन्वन्तरिम् is a noun", s3, {}))
        self.assertTrue(v_step4("सुश्रुतः = Sushruta", s3, {}))          # too few pairs, no sentence
        ok4 = "सुश्रुतः = Sushruta | परिपृच्छति = asks\nSushruta asks Dhanvantari."
        self.assertEqual(v_step4(ok4, s3, {}), [])

    def test_gold_rows_pass_validators(self):
        """The hand-made gold table must satisfy the same checks the model must pass."""
        sh, _ = load_mula(MULA)
        by = {s.id: s for s in sh}
        gold = load_gold_xlsx(GOLD)
        for sid, steps in gold.items():
            for n in (3, 4):
                self.assertEqual(STEP_SPECS[n].validator(steps[n], by[sid], {}), [], f"{sid} step {n}")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        sh, _ = load_mula(MULA)
        self.shlokas = sh
        kb = KnowledgeBase.build(build_chunks(sh, load_gold_xlsx(GOLD)), "tfidf", self.tmp / "kb")
        self.store = Store(self.tmp / "db.sqlite3")
        self.store.upsert_chapter("su.ni.1", "sushruta", "nidana", 1, "Vatavyadhi Nidana")
        self.store.upsert_shlokas("su.ni.1", sh)
        self.llm = MockLLM()
        self.orch = Orchestrator(HybridRetriever(kb), self.llm, self.store, ROOT / "prompts", max_retries=2)

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_run_and_cache(self):
        res = self.orch.run_shloka(self.shlokas[1], neighbours=neighbour_texts(self.shlokas, 1))
        self.assertEqual(sorted(res), list(range(1, 8)))
        self.assertTrue(all(r.valid for r in res.values()), {n: r.issues for n, r in res.items()})
        self.assertEqual(len(self.llm.calls), 6)               # step 1 is rule-based
        user4 = self.llm.calls[2][1]
        self.assertIn("OUTPUT OF STEP 2", user4)               # context passing
        self.assertIn("REFERENCES:", user4)
        self.orch.run_shloka(self.shlokas[1])
        self.assertEqual(len(self.llm.calls), 6)               # second run served from cache

    def test_retry_on_invalid_output(self):
        answers = iter(["not the format", "1. धन्वन्तरिम् — सुबन्त — पुं., द्वितीया, एकवचनम्\n"
                        "2. धर्मभृताम् — सुबन्त — पुं., षष्ठी, बहुवचनम्\n3. वरिष्ठम् — सुबन्त — पुं., द्वितीया, एकवचनम्\n"
                        "4. चरणौ — सुबन्त — पुं., द्वितीया, द्विवचनम्\n5. सुश्रुतः — सुबन्त — पुं., प्रथमा, एकवचनम्"])
        self.orch.llm = MockLLM(lambda s, u: next(answers))
        r = self.orch.run_step(STEP_SPECS[2], self.shlokas[1], {})
        self.assertTrue(r.valid)
        self.assertEqual(r.attempts, 2)
        self.assertIn("PROBLEMS", self.orch.llm.calls[1][1])

    def test_export_and_chatbot(self):
        self.orch.run_shloka(self.shlokas[11])                 # verse 13 (index 11)
        out = export_xlsx(self.store, "su.ni.1", self.tmp / "out.xlsx")
        self.assertTrue(out.exists())
        bot = Chatbot(self.orch.retriever, MockLLM(), self.store, ROOT / "prompts")
        a = bot.ask("Which Vayu moves in the mouth?", "su.ni.1.13")
        self.assertTrue(a.grounded)
        self.assertTrue(a.citations)
        with self.assertRaises(KeyError):
            bot.ask("x", "su.ni.1.999")


class AppWiringTests(unittest.TestCase):
    def test_build_app_from_settings(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            sh, _ = load_mula(MULA)
            KnowledgeBase.build(build_chunks(sh), "tfidf", tmp / "kb")
            s = Settings(kb_dir=tmp / "kb", db_path=tmp / "a.sqlite3", llm="mock")
            app = build_app(s)
            self.assertEqual(len(app.kb.chunks), 90)
            app.store.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class EvaluationTests(unittest.TestCase):
    def test_retrieval_metrics(self):
        self.assertEqual(rm.recall_at_k(["a", "b", "c"], {"b", "z"}, 2), 0.5)
        self.assertEqual(rm.mrr(["a", "b"], {"b"}), 0.5)
        self.assertAlmostEqual(rm.ndcg_at_k(["b", "a"], {"b"}, 2), 1.0)

    def test_cvi(self):
        self.assertAlmostEqual(cvi.i_cvi([4, 4, 3, 4, 2, 4]), 5 / 6)
        rep = cvi.cvi_report({"s:1": [4, 4, 4, 4, 4, 4], "s:2": [4, 3, 2, 4, 4, 1]})
        self.assertEqual(rep["s_cvi_ua"], 0.5)
        self.assertAlmostEqual(rep["items"]["s:1"]["kappa"], 1.0)
        # Polit, Beck & Owen (2007) table: 6 experts, 5 agree -> I-CVI .83, k* .82
        self.assertAlmostEqual(cvi.modified_kappa([4, 4, 4, 4, 4, 1]), 0.82, places=2)
        self.assertEqual(cvi.by_step({"a:1": [4, 4], "b:1": [4, 1], "a:2": [1, 1]}), {1: 0.75, 2: 0.0})

    def test_paired_and_sus(self):
        pre = [10, 12, 9, 14, 11, 13, 8, 10, 12, 11]
        post = [14, 15, 13, 16, 15, 17, 12, 13, 16, 14]
        r = stats.paired_test(pre, post)
        self.assertTrue(r["significant"])
        self.assertIn(r["test"], ("paired t-test", "Wilcoxon signed-rank"))
        self.assertEqual(stats.sus_score([5, 1] * 5), 100.0)
        self.assertEqual(stats.sus_score([3] * 10), 50.0)
        self.assertAlmostEqual(stats.normalized_gain(10, 15, 20), 0.5)

    def test_faithfulness_judge(self):
        replies = iter(['["Prana moves in the mouth.", "Prana causes fever."]', "[1, 0]"])
        f = faithfulness(MockLLM(lambda s, u: next(replies)), "answer", ["context"])
        self.assertEqual(f, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
