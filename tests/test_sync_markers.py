"""Stdlib unittest suite for the unified sync marker engine."""
import sys
import unittest

sys.path.insert(0, "scripts")


class TestSyncMarkers(unittest.TestCase):
    def test_inline_and_block_resolve(self):
        import sync_published as sp
        text = ("a <!-- sync:chunks -->0<!-- /sync:chunks --> b\n"
                "<!-- sync:gaps_table -->x<!-- /sync:gaps_table -->")
        out, unknown = sp.sync_markers(text)
        self.assertEqual(unknown, [])
        self.assertIn("<!-- sync:chunks -->2,041<!-- /sync:chunks -->", out)
        self.assertIn("<!-- sync:gaps_table -->", out)
        self.assertNotIn("-->x<!--", out)

    def test_unknown_name_is_reported_not_silently_kept(self):
        import sync_published as sp
        out, unknown = sp.sync_markers("<!-- sync:nope -->1<!-- /sync:nope -->")
        self.assertEqual(unknown, ["nope"])
        self.assertIn("<!-- sync:nope -->1<!-- /sync:nope -->", out)

    def test_idempotent(self):
        import sync_published as sp
        once, _ = sp.sync_markers("<!-- sync:docs -->0<!-- /sync:docs -->")
        twice, _ = sp.sync_markers(once)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
