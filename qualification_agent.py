"""
SBI Sarathi Qualification Agent.

Trains a Logistic Regression propensity model from synthetic customer data and
qualifies customers for the most relevant product.
"""

import pickle
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from signal_agent import detect_signals, load_customer_index
from signal_router import check_suitability


MODEL_PATH = Path(__file__).parent / "propensity_model.pkl"

FEATURE_COLUMNS = [
    "balance_trend",
    "signal_type",
    "existing_product_count",
    "risk_profile",
    "annual_income",
]

RECOMMENDED_PRODUCTS = {
    "salary_spike": "recurring_sip",
    "idle_balance_high": "fixed_deposit_or_sip",
    "recurring_hospital_debit": "health_insurance",
    "recurring_school_fee": "child_education_plan",
    "forex_transaction_spike": "forex_card",
    "large_one_time_credit": "wealth_consultation",
    "dormant_high_value": "fixed_deposit",
}


class QualificationResponse(BaseModel):
    customer_id: str = Field(..., examples=["CUST1001"])
    signal_type: str = Field(..., examples=["salary_spike"])
    propensity_score: float = Field(..., ge=0, le=1, examples=[0.82])
    suitability: str = Field(..., examples=["PASS"])
    recommended_product: str = Field(..., examples=["recurring_sip"])


def qualify_customer(customer_id: str) -> QualificationResponse | None:
    """Return model propensity and qualification decision for a customer."""
    customers = load_customer_index()
    customer = customers.get(customer_id)
    if customer is None:
        return None

    signal_type = choose_signal_type(customer)
    model = load_or_train_model(customers)
    features = build_feature_row(customer, signal_type)
    propensity_score = float(model.predict_proba([features])[0][1])
    suitability = build_suitability(customer, signal_type, propensity_score)

    return QualificationResponse(
        customer_id=customer_id,
        signal_type=signal_type,
        propensity_score=round(propensity_score, 2),
        suitability=suitability,
        recommended_product=RECOMMENDED_PRODUCTS.get(signal_type, "relationship_manager_review"),
    )


def load_or_train_model(customers: dict[str, dict[str, Any]]) -> Pipeline:
    """Load the saved model or train and persist a fresh model."""
    if MODEL_PATH.exists():
        with MODEL_PATH.open("rb") as file:
            return pickle.load(file)

    model = train_model(customers)
    with MODEL_PATH.open("wb") as file:
        pickle.dump(model, file)
    return model


def train_model(customers: dict[str, dict[str, Any]] | None = None) -> Pipeline:
    """Train Logistic Regression on synthetic customer rows."""
    customers = customers or load_customer_index()
    rows: list[dict[str, Any]] = []
    labels: list[int] = []

    for customer in customers.values():
        signal_types = customer.get("life_event_signals") or [
            signal.signal_type for signal in detect_signals(customer)
        ]
        for signal_type in signal_types:
            rows.append(build_feature_row(customer, signal_type))
            labels.append(build_training_label(customer, signal_type))

    if len(set(labels)) < 2:
        raise RuntimeError("Training data must contain both positive and negative examples")

    model = Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=False)),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    model.fit(rows, labels)
    return model


def choose_signal_type(customer: dict[str, Any]) -> str:
    """Pick the strongest available signal for qualification."""
    detected_signals = detect_signals(customer)
    if detected_signals:
        return detected_signals[0].signal_type

    existing_signals = customer.get("life_event_signals") or []
    if existing_signals:
        return existing_signals[0]

    return "idle_balance_high"


def build_feature_row(customer: dict[str, Any], signal_type: str) -> dict[str, Any]:
    return {
        "balance_trend": balance_trend(customer),
        "signal_type": signal_type,
        "existing_product_count": len(customer.get("existing_products", [])),
        "risk_profile": customer.get("risk_profile", "conservative"),
        "annual_income": annual_income(customer),
    }


def build_training_label(customer: dict[str, Any], signal_type: str) -> int:
    """Create synthetic target labels from suitability and financial strength."""
    if check_suitability(customer, signal_type) == "FAIL":
        return 0

    income = annual_income(customer)
    product_count = len(customer.get("existing_products", []))
    trend = balance_trend(customer)
    risk = customer.get("risk_profile", "conservative")

    if signal_type in {"salary_spike", "forex_transaction_spike", "large_one_time_credit"}:
        return int(income >= 600000 and risk in {"moderate", "aggressive"})
    if signal_type in {"idle_balance_high", "dormant_high_value"}:
        return int(trend >= 0.2 or latest_balance(customer) >= 150000)
    if signal_type in {"recurring_hospital_debit", "recurring_school_fee"}:
        return int(income >= 450000 and product_count <= 5)

    return 0


def build_suitability(customer: dict[str, Any], signal_type: str, propensity_score: float) -> str:
    if check_suitability(customer, signal_type) == "FAIL":
        return "FAIL"
    return "PASS" if propensity_score >= 0.5 else "FAIL"


def balance_trend(customer: dict[str, Any]) -> float:
    balances = customer.get("monthly_balance_avg_6m", [])
    if len(balances) < 2:
        return 0.0

    first_half = balances[: len(balances) // 2]
    second_half = balances[len(balances) // 2 :]
    old_average = mean(first_half)
    recent_average = mean(second_half)
    if old_average <= 0:
        return 0.0
    return round((recent_average - old_average) / old_average, 4)


def annual_income(customer: dict[str, Any]) -> int:
    salary_credits = [
        transaction["amount"]
        for transaction in customer.get("transactions_last_90d", [])
        if transaction.get("type") == "credit" and transaction.get("category") == "salary"
    ]
    if salary_credits:
        return int(max(salary_credits) * 12)

    return int(latest_balance(customer) * 0.6)


def latest_balance(customer: dict[str, Any]) -> int:
    balances = customer.get("monthly_balance_avg_6m", [])
    return int(balances[-1]) if balances else 0
