import unittest
from folio_phase1 import apply_answer, build_plan, interview_questions, new_state, rejects_secret


class Phase1Test(unittest.TestCase):
    def test_single_key_skips_threshold_and_stores_no_seed(self):
        state = new_state()
        apply_answer(state, "plan_name", "Family map")
        apply_answer(state, "owner", "Ada")
        apply_answer(state, "structure", "single")
        keys = [item[0] for item in interview_questions(state)]
        self.assertIn("backup_copies", keys)
        self.assertNotIn("n", keys)
        self.assertNotIn("m", keys)
        apply_answer(state, "name", "Savings")
        apply_answer(state, "backup_copies", "one")
        apply_answer(state, "delayed", "no")
        apply_answer(state, "another", "no")
        apply_answer(state, "contact", "Executor")
        apply_answer(state, "test_spend", "no")
        plan = build_plan(state)
        self.assertEqual(plan["vaults"][0]["setupType"], "single")
        self.assertEqual(plan["vaults"][0]["m"], 1)
        self.assertNotIn("seed", plan["vaults"][0])

    def test_unsure_does_not_invent_a_signing_rule(self):
        state = new_state()
        apply_answer(state, "structure", "unsure")
        apply_answer(state, "name", "Unknown wallet")
        apply_answer(state, "delayed", "unsure")
        apply_answer(state, "another", "no")
        plan = build_plan(state)
        self.assertEqual(plan["vaults"][0]["setupType"], "unknown")
        self.assertEqual(plan["vaults"][0]["m"], "")

    def test_seed_list_is_refused(self):
        self.assertTrue(rejects_secret("abandon ability able about above absent absorb abstract absurd abuse access accident"))
        self.assertFalse(rejects_secret("bank box"))


if __name__ == "__main__":
    unittest.main()
