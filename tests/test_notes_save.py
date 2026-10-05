"""Heir notes saves must never destroy unlock methods or re-key the file.

Regression cover for the original save_notes, which re-sealed with a single
freshly typed passphrase: multi-method envelopes silently collapsed to
passphrase-only, and a typo silently changed the file's passphrase.
"""
import copy
import unittest

from folio_security import seal, open_package, reseal_preserving_methods, validate


def three_method_plan():
    return {"people": {"owner": "Ada"}, "vaults": [{"n": 2, "keys": []}],
            "heirNotes": "", "heirChecklist": {}}


def three_methods():
    return [
        {"kind": "passphrase", "label": "p1", "passphrase": "correct horse battery"},
        {"kind": "passphrase", "label": "p2", "passphrase": "second independent phrase"},
        {"kind": "questions", "label": "q", "questions": ["a?", "b?", "c?"],
         "answers": ["one", "two", "three"]},
    ]


class PreservingResealTests(unittest.TestCase):
    def setUp(self):
        self.env = seal(three_method_plan(), three_methods())
        self.plan, self.dek = open_package(self.env, method_index=0,
                                           credential="correct horse battery",
                                           return_key=True)

    def reseal_with_notes(self, text):
        edited = dict(self.plan)
        edited["heirNotes"] = text
        edited["heirChecklist"] = {"1": True}
        return reseal_preserving_methods(edited, self.env, self.dek)

    def test_every_original_method_still_opens(self):
        new = self.reseal_with_notes("call Bea first")
        creds = ["correct horse battery", "second independent phrase",
                 ["one", "two", "three"]]
        for index, credential in enumerate(creds):
            opened = open_package(new, method_index=index, credential=credential)
            self.assertEqual(opened["heirNotes"], "call Bea first")
            self.assertEqual(opened["heirChecklist"], {"1": True})

    def test_wrong_credentials_still_rejected(self):
        new = self.reseal_with_notes("x")
        with self.assertRaises(ValueError):
            open_package(new, method_index=0, credential="wrong phrase entirely")
        with self.assertRaises(ValueError):
            open_package(new, method_index=2, credential=["one", "two", "WRONG"])

    def test_original_envelope_not_mutated(self):
        snapshot = copy.deepcopy(self.env)
        self.reseal_with_notes("x")
        self.assertEqual(self.env, snapshot)

    def test_reseal_validates_and_fresh_iv(self):
        new = self.reseal_with_notes("x")
        validate(new)
        self.assertEqual(len(new["methods"]), 3)
        self.assertNotEqual(new["iv"], self.env["iv"])
        self.assertEqual(new["methods"], self.env["methods"])

    def test_tampered_data_rejected(self):
        new = self.reseal_with_notes("x")
        new["data"] = new["data"][:-4] + "AAAA"
        with self.assertRaises(ValueError):
            open_package(new, method_index=0, credential="correct horse battery")

    def test_reseal_requires_original_key(self):
        with self.assertRaises(ValueError):
            reseal_preserving_methods(self.plan, self.env, b"\x00" * 32)
        with self.assertRaises(ValueError):
            reseal_preserving_methods(self.plan, self.env, None)


if __name__ == "__main__":
    unittest.main()
