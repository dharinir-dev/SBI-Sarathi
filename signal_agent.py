"""
SBI Sarathi Signal Agent.

Loads synthetic customer data and detects financial signals for a customer.
"""

import json
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field


DATA_PATHS = [
    Path(__file__).parent / "data" / "synthetic_customers.json",
    Path(__file__).parent / "synthetic_customers.json",
    Path(__file__).parent / "data" / "customers.json",
]

HOSPITAL_CATEGORIES = {"hospital", "pharmacy"}
SCHOOL_CATEGORIES = {"school_fee", "tuition"}
FOREX_CATEGORIES = {"forex", "travel", "international_transfer"}


class DetectedSignal(BaseModel):
    signal_type: str = Field(..., examples=["salary_spike"])
    confidence: float = Field(..., ge=0, le=1, examples=[0.92])
    reason: str = Field(..., examples=["Salary increased from Rs.65,000 to Rs.95,000"])


class SignalResponse(BaseModel):
    customer_id: str = Field(..., examples=["CUST1001"])
    signals: list[DetectedSignal]


def load_customer_index() -> dict[str, dict[str, Any]]:
    """Load synthetic customers and index them by customer_id."""
    data_path = next((path for path in DATA_PATHS if path.exists()), None)
    if data_path is None:
        expected = ", ".join(str(path) for path in DATA_PATHS)
        raise RuntimeError(f"No customer dataset found. Expected one of: {expected}")

    with data_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    customers = data["customers"] if isinstance(data, dict) and "customers" in data else data
    return {customer["customer_id"]: customer for customer in customers}


def detect_signals(customer: dict[str, Any]) -> list[DetectedSignal]:
    """Run all signal detectors for a customer."""
    signals: list[DetectedSignal] = []
    detectors = [
        detect_salary_spike,
        detect_idle_balance_high,
        detect_recurring_hospital_debit,
        detect_recurring_school_fee,
        detect_forex_transaction_spike,
        detect_large_one_time_credit,
        detect_dormant_high_value,
    ]

    for detector in detectors:
        signal = detector(customer)
        if signal is not None:
            signals.append(signal)

    return sorted(signals, key=lambda signal: signal.confidence, reverse=True)


def detect_signals_for_customer(customer_id: str) -> SignalResponse | None:
    """Load a customer and return detected signals, or None if missing."""
    customer = load_customer_index().get(customer_id)
    if customer is None:
        return None

    return SignalResponse(customer_id=customer_id, signals=detect_signals(customer))


def detect_salary_spike(customer: dict[str, Any]) -> DetectedSignal | None:
    salary_credits = [
        transaction
        for transaction in customer.get("transactions_last_90d", [])
        if transaction.get("type") == "credit" and transaction.get("category") == "salary"
    ]
    salary_credits.sort(key=lambda transaction: transaction.get("date", ""))
    if len(salary_credits) < 2:
        return None

    previous_salary = salary_credits[0]["amount"]
    latest_salary = salary_credits[-1]["amount"]
    if previous_salary <= 0:
        return None

    increase_ratio = latest_salary / previous_salary
    if increase_ratio < 1.35:
        return None

    confidence = min(0.99, 0.72 + (increase_ratio - 1.35) * 0.5)
    return DetectedSignal(
        signal_type="salary_spike",
        confidence=round(confidence, 2),
        reason=(
            f"Salary increased from {format_rupees(previous_salary)} "
            f"to {format_rupees(latest_salary)}"
        ),
    )


def detect_idle_balance_high(customer: dict[str, Any]) -> DetectedSignal | None:
    balances = customer.get("monthly_balance_avg_6m", [])
    if len(balances) < 6:
        return None

    old_average = mean(balances[:3])
    recent_average = mean(balances[3:])
    if old_average <= 0:
        return None

    ratio = recent_average / old_average
    if ratio < 1.8:
        return None

    confidence = min(0.98, 0.7 + (ratio - 1.8) * 0.12)
    return DetectedSignal(
        signal_type="idle_balance_high",
        confidence=round(confidence, 2),
        reason=(
            f"Average balance rose from {format_rupees(round(old_average))} "
            f"to {format_rupees(round(recent_average))}"
        ),
    )


def detect_recurring_hospital_debit(customer: dict[str, Any]) -> DetectedSignal | None:
    medical_debits = matching_debits(customer, HOSPITAL_CATEGORIES)
    if len(medical_debits) < 2 or "health_insurance" in customer.get("existing_products", []):
        return None

    total = sum(transaction["amount"] for transaction in medical_debits)
    confidence = min(0.96, 0.72 + len(medical_debits) * 0.06)
    return DetectedSignal(
        signal_type="recurring_hospital_debit",
        confidence=round(confidence, 2),
        reason=f"{len(medical_debits)} medical debits totaling {format_rupees(total)} were found",
    )


def detect_recurring_school_fee(customer: dict[str, Any]) -> DetectedSignal | None:
    school_debits = matching_debits(customer, SCHOOL_CATEGORIES)
    if len(school_debits) < 2 or "child_education_plan" in customer.get("existing_products", []):
        return None

    total = sum(transaction["amount"] for transaction in school_debits)
    confidence = min(0.95, 0.72 + len(school_debits) * 0.07)
    return DetectedSignal(
        signal_type="recurring_school_fee",
        confidence=round(confidence, 2),
        reason=f"{len(school_debits)} school fee debits totaling {format_rupees(total)} were found",
    )


def detect_forex_transaction_spike(customer: dict[str, Any]) -> DetectedSignal | None:
    forex_debits = matching_debits(customer, FOREX_CATEGORIES)
    if len(forex_debits) < 3:
        return None

    total = sum(transaction["amount"] for transaction in forex_debits)
    confidence = min(0.97, 0.74 + len(forex_debits) * 0.04)
    return DetectedSignal(
        signal_type="forex_transaction_spike",
        confidence=round(confidence, 2),
        reason=f"{len(forex_debits)} international or forex debits totaling {format_rupees(total)} were found",
    )


def detect_large_one_time_credit(customer: dict[str, Any]) -> DetectedSignal | None:
    large_credits = [
        transaction
        for transaction in customer.get("transactions_last_90d", [])
        if (
            transaction.get("type") == "credit"
            and transaction.get("category") != "salary"
            and transaction.get("amount", 0) >= 200000
        )
    ]
    if not large_credits:
        return None

    largest = max(large_credits, key=lambda transaction: transaction["amount"])
    confidence = min(0.99, 0.76 + largest["amount"] / 3000000)
    return DetectedSignal(
        signal_type="large_one_time_credit",
        confidence=round(confidence, 2),
        reason=(
            f"Large {largest.get('category', 'credit')} credit of "
            f"{format_rupees(largest['amount'])} was received"
        ),
    )


def detect_dormant_high_value(customer: dict[str, Any]) -> DetectedSignal | None:
    transactions = customer.get("transactions_last_90d", [])
    balances = customer.get("monthly_balance_avg_6m", [])
    if transactions or not balances:
        return None

    average_balance = mean(balances)
    if average_balance < 150000:
        return None

    confidence = min(0.97, 0.78 + average_balance / 2000000)
    return DetectedSignal(
        signal_type="dormant_high_value",
        confidence=round(confidence, 2),
        reason=f"No transactions in the last 90 days with average balance of {format_rupees(round(average_balance))}",
    )


def matching_debits(customer: dict[str, Any], categories: set[str]) -> list[dict[str, Any]]:
    return [
        transaction
        for transaction in customer.get("transactions_last_90d", [])
        if transaction.get("type") == "debit" and transaction.get("category") in categories
    ]


def format_rupees(amount: int | float) -> str:
    return f"Rs.{int(round(amount)):,}"
