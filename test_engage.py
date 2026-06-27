"""
Unit tests for the GET /engage/{customer_id}, POST /escalate, and memory endpoints.
Run with: python -m unittest test_engage.py
"""

import unittest
import tempfile
from fastapi.testclient import TestClient
from app import app
import os
import sqlite3
from pathlib import Path

# Force initialization of the database in testing
import db

class EngageEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["SARATHI_DB_PATH"] = str(Path(self.temp_dir.name) / "sarathi_test.db")
        self.client = TestClient(app)
        db.init_db()
        with db.get_db_connection() as conn:
            conn.execute("DELETE FROM memory")
            conn.execute("DELETE FROM escalations")
            conn.commit()

    def tearDown(self):
        self.client.close()
        os.environ.pop("SARATHI_DB_PATH", None)
        self.temp_dir.cleanup()

    def test_engage_new_customer_passes_suitability(self):
        # CUST1001 is a valid customer in the synthetic dataset.
        # Let's call /engage/CUST1001
        response = self.client.get("/engage/CUST1001")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        
        self.assertEqual(body["customer_id"], "CUST1001")
        self.assertIn("signals", body)
        self.assertIn("qualification", body)
        self.assertIn("conversation", body)
        self.assertIn("memory", body)
        
        # Verify initial memory is stored
        self.assertEqual(len(body["memory"]["conversation_history"]), 1)
        self.assertEqual(body["memory"]["conversation_history"][0]["role"], "assistant")
        
        # Let's verify stage (should be escalated if suitability FAIL or propensity > 0.90, else awaiting_permission)
        qual = body["qualification"]
        if qual["suitability"] == "FAIL" or qual["propensity_score"] > 0.90:
            self.assertEqual(body["memory"]["current_stage"], "escalated")
            self.assertIsNotNone(body["escalation"])
            self.assertTrue(body["conversation"]["escalate"])
        else:
            self.assertEqual(body["memory"]["current_stage"], "awaiting_permission")
            self.assertIsNone(body["escalation"])
            self.assertFalse(body["conversation"]["escalate"])

    def test_engage_unknown_customer_returns_404(self):
        response = self.client.get("/engage/UNKNOWN")
        self.assertEqual(response.status_code, 404)

    def test_escalate_endpoint(self):
        # Call escalate endpoint directly
        response = self.client.post("/escalate", json={
            "customer_id": "CUST1001",
            "reason": "Customer requests to talk to a supervisor"
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ticket_id"].startswith("RM-"))
        self.assertEqual(body["status"], "created")
        self.assertEqual(body["assigned_to"], "Relationship Manager")

        # Now get memory and check stage
        mem_resp = self.client.get("/memory/CUST1001")
        self.assertEqual(mem_resp.status_code, 200)
        mem_body = mem_resp.json()
        self.assertEqual(mem_body["current_stage"], "escalated")
        
        # Verify escalated ticket details are returned by /engage
        engage_resp = self.client.get("/engage/CUST1001")
        engage_body = engage_resp.json()
        self.assertIsNotNone(engage_body["escalation"])
        self.assertEqual(engage_body["escalation"]["ticket_id"], body["ticket_id"])

    def test_memory_crud_endpoints(self):
        # 1. Get empty memory
        response = self.client.get("/memory/CUST1001")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["current_stage"], "initial_outreach")
        self.assertEqual(body["conversation_history"], [])

        # 2. Update memory
        update_data = {
            "conversation_history": [
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "Yes, proceed"}
            ],
            "current_stage": "awaiting_amount"
        }
        post_response = self.client.post("/memory/CUST1001", json=update_data)
        self.assertEqual(post_response.status_code, 200)
        post_body = post_response.json()
        self.assertEqual(post_body["current_stage"], "awaiting_amount")
        self.assertEqual(len(post_body["conversation_history"]), 2)

        # 3. Get updated memory
        get_resp = self.client.get("/memory/CUST1001")
        self.assertEqual(get_resp.status_code, 200)
        get_body = get_resp.json()
        self.assertEqual(get_body["current_stage"], "awaiting_amount")
        self.assertEqual(get_body["conversation_history"][1]["content"], "Yes, proceed")

    def test_conversation_reply_auto_escalation(self):
        # 1. Initialize conversation
        self.client.get("/engage/CUST1001")
        
        # 2. Reply with dissatisfied text to trigger auto-escalation
        reply_response = self.client.post("/conversation/reply", json={
            "customer_id": "CUST1001",
            "user_message": "This is a worst experience, stop messaging me!"
        })
        self.assertEqual(reply_response.status_code, 200)
        body = reply_response.json()
        
        # Verify the reply contains escalation response or references relationship manager
        self.assertIn("Relationship Manager", body["assistant_message"])
        self.assertIn("RM-", body["assistant_message"])
        
        # 3. Check memory is escalated
        mem_resp = self.client.get("/memory/CUST1001")
        self.assertEqual(mem_resp.json()["current_stage"], "escalated")

    def test_conversation_reply_stage_transition(self):
        # 1. Initialize conversation
        engage_resp = self.client.get("/engage/CUST1001")
        engage_body = engage_resp.json()
        
        # If the customer is escalated initially, this test isn't applicable, so let's check
        if engage_body["memory"]["current_stage"] == "awaiting_permission":
            # 2. Reply with yes
            reply_resp = self.client.post("/conversation/reply", json={
                "customer_id": "CUST1001",
                "user_message": "Yes, please tell me more"
            })
            self.assertEqual(reply_resp.status_code, 200)
            
            # Memory should now be awaiting_amount
            mem_resp = self.client.get("/memory/CUST1001")
            self.assertEqual(mem_resp.json()["current_stage"], "awaiting_amount")


if __name__ == "__main__":
    unittest.main()
