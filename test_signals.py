"""
Sample tests for the Signal Agent.

Run with: python -m unittest test_signals.py
"""

import unittest

from fastapi.testclient import TestClient

from app import app
from signal_agent import detect_signals


class SignalEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_signals_returns_customer_signals(self):
        response = self.client.get("/signals/CUST1001")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["customer_id"], "CUST1001")
        self.assertIsInstance(body["signals"], list)

    def test_get_signals_returns_404_for_unknown_customer(self):
        response = self.client.get("/signals/UNKNOWN")

        self.assertEqual(response.status_code, 404)


class SignalDetectorTests(unittest.TestCase):
    def test_detects_salary_spike(self):
        customer = base_customer(
            transactions=[
                credit("2026-04-01", "salary", 65000),
                credit("2026-05-01", "salary", 95000),
            ]
        )

        self.assertHasSignal(customer, "salary_spike")

    def test_detects_idle_balance_high(self):
        customer = base_customer(balances=[50000, 52000, 51000, 125000, 132000, 140000])

        self.assertHasSignal(customer, "idle_balance_high")

    def test_detects_recurring_hospital_debit(self):
        customer = base_customer(
            products=["savings_account", "debit_card"],
            transactions=[
                debit("2026-05-01", "hospital", 10000),
                debit("2026-05-20", "pharmacy", 8000),
            ],
        )

        self.assertHasSignal(customer, "recurring_hospital_debit")

    def test_detects_recurring_school_fee(self):
        customer = base_customer(
            products=["savings_account", "debit_card"],
            transactions=[
                debit("2026-05-01", "school_fee", 30000),
                debit("2026-06-01", "tuition", 25000),
            ],
        )

        self.assertHasSignal(customer, "recurring_school_fee")

    def test_detects_forex_transaction_spike(self):
        customer = base_customer(
            transactions=[
                debit("2026-05-01", "forex", 30000),
                debit("2026-05-15", "travel", 40000),
                debit("2026-06-01", "international_transfer", 35000),
            ]
        )

        self.assertHasSignal(customer, "forex_transaction_spike")

    def test_detects_large_one_time_credit(self):
        customer = base_customer(transactions=[credit("2026-06-01", "bonus", 250000)])

        self.assertHasSignal(customer, "large_one_time_credit")

    def test_detects_dormant_high_value(self):
        customer = base_customer(balances=[180000, 175000, 190000, 185000, 188000, 192000])

        self.assertHasSignal(customer, "dormant_high_value")

    def assertHasSignal(self, customer, signal_type):
        signals = detect_signals(customer)
        self.assertIn(signal_type, {signal.signal_type for signal in signals})


def base_customer(products=None, balances=None, transactions=None):
    return {
        "customer_id": "CUSTTEST",
        "existing_products": products or ["savings_account", "debit_card"],
        "monthly_balance_avg_6m": balances or [40000, 42000, 41000, 43000, 44000, 45000],
        "transactions_last_90d": transactions or [],
    }


def credit(date, category, amount):
    return {"date": date, "type": "credit", "category": category, "amount": amount}


def debit(date, category, amount):
    return {"date": date, "type": "debit", "category": category, "amount": amount}


if __name__ == "__main__":
    unittest.main()
