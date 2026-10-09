"""Stdlib unittest suite for the corpus statistics asset (no third-party deps)."""
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, "scripts")

import build_stats as bs


class TestBuildStats(unittest.TestCase):
    def test_collect_has_five_tables(self):
        self.assertEqual(
            set(bs.collect()),
            {"corpus_stats", "gaps", "domains", "top_documents", "paywalled"},
        )

    def test_collect_is_deterministic(self):
        self.assertEqual(bs.collect(), bs.collect())

    def test_write_roundtrips_and_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as d:
            bs.write(pathlib.Path(d))
            first = {p.name: p.read_bytes() for p in pathlib.Path(d).glob("*.csv")}
            bs.write(pathlib.Path(d))
            second = {p.name: p.read_bytes() for p in pathlib.Path(d).glob("*.csv")}
        self.assertEqual(first, second)
        self.assertEqual(set(first), {f"{k}.csv" for k in bs.COLUMNS})

    def test_corpus_stats_row_keys_match_columns(self):
        row = bs.collect()["corpus_stats"][0]
        self.assertEqual(list(row), bs.COLUMNS["corpus_stats"])


class TestCorpusStatsValues(unittest.TestCase):
    def test_values_pins_formats(self):
        import corpus_stats as cs
        v = cs.values()
        self.assertEqual(v["chunks"], "2,041")
        self.assertEqual(v["tokens"], "~1,029,983")
        self.assertEqual(v["raw_mib"], "46 MB")
        self.assertEqual(v["top3_share"], "~45%")
        self.assertEqual(v["chunk_pdf"], "1,292")

    def test_values_raises_on_missing_dir(self):
        import corpus_stats as cs
        with tempfile.TemporaryDirectory() as d:
            saved = cs.DATA_DIR
            cs.DATA_DIR = pathlib.Path(d)
            try:
                with self.assertRaises((FileNotFoundError, KeyError)):
                    cs.values()
            finally:
                cs.DATA_DIR = saved


class TestRenderers(unittest.TestCase):
    def test_renderers_registered_and_nonempty(self):
        import corpus_stats as cs
        self.assertEqual(
            set(cs.RENDERERS),
            {"headline", "stats_bullets", "gaps_table", "domains_table", "top_documents"},
        )
        for fn in cs.RENDERERS.values():
            self.assertTrue(fn().strip())

    def test_gaps_table_groups_by_cause_and_orders_deterministically(self):
        import corpus_stats as cs
        t = cs.gaps_table()
        self.assertTrue(t.splitlines()[0].startswith("**5** of the 38"), t.splitlines()[0])
        self.assertIn("| Framework | Why it's empty |", t)
        self.assertEqual(cs.gaps_table(), t)

    def test_gaps_table_handles_empty(self):
        import corpus_stats as cs
        saved = cs.load
        cs.load = lambda: {"corpus_stats": saved()["corpus_stats"], "gaps": []}
        try:
            self.assertIn("0", cs.gaps_table().splitlines()[0])
        finally:
            cs.load = saved


class TestStatsAssetIntegrity(unittest.TestCase):
    def test_load_raises_when_a_csv_is_missing(self):
        import corpus_stats as cs
        with tempfile.TemporaryDirectory() as d:
            for name in ("corpus_stats", "domains", "top_documents", "paywalled"):
                shutil.copy(cs.DATA_DIR / f"{name}.csv", pathlib.Path(d))
            saved = cs.DATA_DIR
            cs.DATA_DIR = pathlib.Path(d)
            try:
                with self.assertRaises(FileNotFoundError):
                    cs.load()  # gaps.csv is absent -> must raise, never silently empty
            finally:
                cs.DATA_DIR = saved


class TestVerifyStats(unittest.TestCase):
    def test_stats_totals_match_artifacts(self):
        import verify_stats as vs
        self.assertEqual(vs.check(), [])


if __name__ == "__main__":
    unittest.main()
