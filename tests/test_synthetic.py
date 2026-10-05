import json
import tempfile
import unittest
from pathlib import Path

from folio_synthetic import load_synthetic_plan, open_synthetic_envelope, save_synthetic_plan, seal_synthetic_plan
import folio_security


TEST_PASSPHRASE = "synthetic-only test phrase"
SAMPLE_PLAN = {
    "meta": {"planName": "Example family guide", "owner": "Sample Owner"},
    "vaults": [{"name": "Example wallet", "setupType": "single"}],
}


class SyntheticSaveTest(unittest.TestCase):
    def test_save_encrypts_and_reopens_marked_test_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-test-guide.csp.json"
            save_synthetic_plan(path, SAMPLE_PLAN, TEST_PASSPHRASE)

            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("Example family guide", raw)
            self.assertNotIn("Sample Owner", raw)
            reopened = load_synthetic_plan(path, TEST_PASSPHRASE)

        self.assertTrue(reopened["meta"]["syntheticTest"])
        self.assertEqual(reopened["vaults"][0]["name"], "Example wallet")

    def test_wrong_passphrase_is_rejected(self):
        envelope = seal_synthetic_plan(SAMPLE_PLAN, TEST_PASSPHRASE)
        with self.assertRaises(ValueError):
            open_synthetic_envelope(envelope, "not the test phrase")

    def test_deeply_nested_json_is_a_controlled_open_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested.json"
            path.write_text("[" * 1100 + "0" + "]" * 1100, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "could not be opened"):
                load_synthetic_plan(path, TEST_PASSPHRASE)

    def test_unmarked_guide_is_rejected_in_test_mode(self):
        envelope = folio_security.seal(
            SAMPLE_PLAN,
            [{"kind": "passphrase", "label": "Synthetic test passphrase", "passphrase": TEST_PASSPHRASE}],
        )
        with self.assertRaisesRegex(ValueError, "marked synthetic"):
            open_synthetic_envelope(envelope, TEST_PASSPHRASE)


if __name__ == "__main__":
    unittest.main()
