"""
Sample tests for the Qualification Agent.

Run with: python -m unittest test_qualification.py
"""

import unittest

from fastapi.testclient import TestClient

import qualification_agent
from app import app
from qualification_agent import load_customer_index, train_model


class QualificationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_qualify_returns_score_and_recommendation(self):
        response = self.client.get("/qualify/CUST1001")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["customer_id"], "CUST1001")
        self.assertGreaterEqual(body["propensity_score"], 0)
        self.assertLessEqual(body["propensity_score"], 1)
        self.assertIn(body["suitability"], {"PASS", "FAIL"})
        self.assertTrue(body["recommended_product"])

    def test_qualify_returns_404_for_unknown_customer(self):
        response = self.client.get("/qualify/UNKNOWN")

        self.assertEqual(response.status_code, 404)


class QualificationModelTests(unittest.TestCase):
    def test_train_model_can_score_customer_features(self):
        customers = load_customer_index()
        model = train_model(customers)
        customer = customers["CUST1001"]
        row = qualification_agent.build_feature_row(customer, customer["life_event_signals"][0])

        score = model.predict_proba([row])[0][1]

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)


if __name__ == "__main__":
    unittest.main()
