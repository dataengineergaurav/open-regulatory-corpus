"""Stdlib unittest suite for the corpus statistics asset (no third-party deps)."""
import pathlib
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


if __name__ == "__main__":
    unittest.main()
