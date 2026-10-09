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


if __name__ == "__main__":
    unittest.main()
