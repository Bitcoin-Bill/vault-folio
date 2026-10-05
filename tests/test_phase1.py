import unittest
from folio_phase1 import _Interview, apply_answer, build_plan, interview_questions, new_state, rejects_secret


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
        self.assertIn("backup_where", [item[0] for item in interview_questions(state)])
        apply_answer(state, "backup_where", "home safe")
        apply_answer(state, "delayed", "no")
        apply_answer(state, "another", "no")
        apply_answer(state, "contact", "Executor")
        apply_answer(state, "test_spend", "no")
        plan = build_plan(state)
        self.assertEqual(plan["vaults"][0]["setupType"], "single")
        self.assertEqual(plan["vaults"][0]["m"], 1)
        self.assertEqual(plan["vaults"][0]["keys"][0]["locations"], "home safe")
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

    def test_explicit_seed_and_key_labels_are_refused(self):
        for text in ("seed: example", "seed_words are here", "private-key text", "recovery words here"):
            with self.subTest(text=text):
                self.assertTrue(rejects_secret(text))

    def test_another_wallet_keeps_the_previous_wallet(self):
        state = new_state()
        state["draft"] = {"structure": "single", "name": "First wallet", "backup_copies": "one"}
        self.assertIsNone(apply_answer(state, "another", "yes"))
        self.assertEqual(state["wallets"], [{"structure": "single", "name": "First wallet", "backup_copies": "one"}])
        self.assertEqual(state["draft"], {})

    def test_back_from_first_question_cancels_to_home(self):
        called = []
        interview = object.__new__(_Interview)
        interview.history = []
        interview.on_cancel = lambda: called.append(True)
        interview.back()
        self.assertEqual(called, [True])

    def test_back_restores_previous_answer(self):
        interview = object.__new__(_Interview)
        interview.history = [(new_state(), 1, "Ada")]
        interview.on_cancel = lambda: self.fail("should restore history")
        interview.render = lambda: None
        interview.back()
        self.assertEqual(interview.index, 1)
        self.assertEqual(interview.restore_value, "Ada")

    def test_finished_setup_moves_to_people_questions(self):
        state = new_state()
        apply_answer(state, "structure", "single")
        apply_answer(state, "name", "Savings")
        apply_answer(state, "backup_copies", "one")
        apply_answer(state, "delayed", "no")
        apply_answer(state, "another", "no")
        keys = [item[0] for item in interview_questions(state)]
        self.assertEqual(keys[0], "contact")
        self.assertEqual(keys[-1], "test_spend")
        self.assertNotIn("structure", keys)

    def test_provider_delay_is_not_called_an_onchain_timelock(self):
        state = new_state()
        apply_answer(state, "structure", "single")
        apply_answer(state, "name", "Savings")
        apply_answer(state, "backup_copies", "one")
        apply_answer(state, "delayed", "yes")
        apply_answer(state, "delayed_kind", "provider")
        apply_answer(state, "another", "no")
        plan = build_plan(state)
        self.assertNotIn("On-chain timelock", plan["inheritance"]["mechanism"])
        self.assertEqual(plan["recoveryPaths"][0]["mechanism"], "Provider-enforced off-chain delay")

    def test_threshold_can_be_unknown(self):
        state = new_state()
        self.assertIsNone(apply_answer(state, "structure", "multi"))
        self.assertIsNone(apply_answer(state, "n", "3"))
        self.assertIsNone(apply_answer(state, "m", "unsure"))
        self.assertEqual(state["draft"]["m"], "unsure")


if __name__ == "__main__":
    unittest.main()
