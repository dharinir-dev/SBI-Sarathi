"""Unit tests for the Conversation Agent."""

import unittest

from conversation_agent import ConversationRequest, run_conversation_agent


class ConversationAgentTests(unittest.TestCase):
    def test_pass_returns_ask_permission(self):
        req = ConversationRequest(
            customer_name="Priya",
            language_pref="ta",
            triggered_signal="salary_spike",
            recommended_action="suggest_sip",
            suitability_check="PASS",
        )
        result = run_conversation_agent(req)

        self.assertTrue(result.message)
        self.assertEqual(result.intent, "ask_permission")
        self.assertEqual(result.next_step, "wait_for_customer")
        self.assertFalse(result.escalate)

    def test_fail_escalates_to_rm(self):
        req = ConversationRequest(
            customer_name="Priya",
            language_pref="en",
            triggered_signal="salary_spike",
            recommended_action="suggest_sip",
            suitability_check="FAIL",
        )
        result = run_conversation_agent(req)

        self.assertTrue(result.message)
        self.assertEqual(result.intent, "escalate_to_rm")
        self.assertEqual(result.next_step, "wait_for_customer")
        self.assertTrue(result.escalate)

    def test_tamil_opening_uses_customer_name(self):
        req = ConversationRequest(
            customer_name="Priya",
            language_pref="ta",
            triggered_signal="salary_spike",
            recommended_action="suggest_sip",
            suitability_check="PASS",
        )
        result = run_conversation_agent(req)

        self.assertIn("Priya", result.message)


if __name__ == "__main__":
    unittest.main()
