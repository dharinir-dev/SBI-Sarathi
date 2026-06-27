"""
SBI Sarathi — Synthetic Customer Data Generator
Generates 80 customers across 7 signal categories with realistic Indian banking data.
"""

import json
import random
import os
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
# Name pools — region-aware Indian names
# ──────────────────────────────────────────────

FIRST_NAMES_MALE = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Shaurya", "Atharva", "Advait", "Dhruv", "Kabir",
    "Ritvik", "Anirudh", "Rohan", "Karthik", "Suresh", "Rajesh", "Amit",
    "Vikram", "Pranav", "Nikhil", "Deepak", "Sanjay", "Manoj", "Gaurav", "Rahul",
]

FIRST_NAMES_FEMALE = [
    "Priya", "Ananya", "Diya", "Myra", "Sara", "Aadhya", "Isha", "Kavya",
    "Anika", "Riya", "Nisha", "Pooja", "Shreya", "Divya", "Meera",
    "Lakshmi", "Anjali", "Sneha", "Swati", "Neha", "Pallavi", "Rashmi",
    "Tanya", "Simran", "Bhavana", "Harini", "Sowmya", "Revathi", "Janani", "Keerthi",
]

SURNAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Reddy", "Nair",
    "Iyer", "Rao", "Joshi", "Mehta", "Shah", "Pillai", "Menon",
    "Desai", "Bhat", "Kulkarni", "Choudhury", "Banerjee", "Mukherjee", "Das",
    "Agarwal", "Tiwari", "Mishra", "Pandey", "Saxena", "Chauhan", "Yadav", "Srinivasan",
    "Subramaniam", "Naidu", "Hegde", "Kamath", "Patil", "Jain", "Thakur", "Malhotra",
    "Kapoor", "Bose",
]

# ──────────────────────────────────────────────
# City → language/region mapping
# ──────────────────────────────────────────────

CITY_CONFIG = {
    "Chennai":    {"lang": "ta", "region": "south"},
    "Coimbatore": {"lang": "ta", "region": "south"},
    "Kochi":      {"lang": "en", "region": "south"},
    "Bangalore":  {"lang": "en", "region": "south"},
    "Hyderabad":  {"lang": "en", "region": "south"},
    "Mumbai":     {"lang": "en", "region": "west"},
    "Pune":       {"lang": "en", "region": "west"},
    "Ahmedabad":  {"lang": "en", "region": "west"},
    "Delhi":      {"lang": "hi", "region": "north"},
    "Jaipur":     {"lang": "hi", "region": "north"},
    "Lucknow":    {"lang": "hi", "region": "north"},
    "Kolkata":    {"lang": "en", "region": "east"},
}

CITIES = list(CITY_CONFIG.keys())

ACCOUNT_TYPES = ["savings", "current"]
KYC_STATUSES = ["complete", "complete", "complete", "complete", "pending"]  # 80% complete
RISK_PROFILES = ["conservative", "moderate", "aggressive"]

ALL_PRODUCTS = [
    "savings_account", "debit_card", "credit_card", "fd", "rd",
    "sip", "health_insurance", "term_insurance", "child_education_plan", "ppf",
]

TRANSACTION_CATEGORIES = [
    "salary", "rent", "grocery", "emi", "hospital", "school_fee",
    "forex", "investment", "utility", "shopping", "transfer", "refund",
]


def random_name():
    """Generate a random Indian full name."""
    if random.random() < 0.5:
        first = random.choice(FIRST_NAMES_MALE)
    else:
        first = random.choice(FIRST_NAMES_FEMALE)
    last = random.choice(SURNAMES)
    return f"{first} {last}"


def random_products(signal: str) -> list:
    """
    Generate a realistic product list.
    Ensures certain products are ABSENT for specific signals (to create the gap).
    """
    base = ["savings_account", "debit_card"]

    # Add some random extras
    extras_pool = ["credit_card", "fd", "rd", "ppf"]

    # Signal-specific exclusions
    if signal == "idle_balance_high":
        # No SIP or investment products — that's the whole point
        extras_pool = ["credit_card", "fd", "ppf"]
    elif signal == "recurring_hospital_debit":
        # No health insurance
        extras_pool = ["credit_card", "fd", "rd", "sip", "ppf"]
    elif signal == "recurring_school_fee":
        # No child education plan
        extras_pool = ["credit_card", "fd", "rd", "sip", "health_insurance", "ppf"]
    elif signal == "salary_spike":
        extras_pool = ["credit_card", "fd", "ppf"]
    elif signal == "forex_transaction_spike":
        extras_pool = ["credit_card", "fd", "sip", "ppf"]
    elif signal == "large_one_time_credit":
        extras_pool = ["credit_card", "fd", "rd", "sip"]
    elif signal == "dormant_high_value":
        extras_pool = ["credit_card", "fd"]

    num_extras = random.randint(0, min(3, len(extras_pool)))
    extras = random.sample(extras_pool, num_extras)
    return base + extras


def random_date_in_range(start: datetime, end: datetime) -> str:
    """Generate a random date string between start and end."""
    delta = (end - start).days
    random_days = random.randint(0, max(0, delta))
    dt = start + timedelta(days=random_days)
    return dt.strftime("%Y-%m-%d")


def generate_base_transactions(num: int, start_date: datetime, end_date: datetime) -> list:
    """Generate generic filler transactions."""
    txns = []
    categories = ["rent", "grocery", "emi", "utility", "shopping", "transfer"]
    for _ in range(num):
        cat = random.choice(categories)
        amount_ranges = {
            "rent": (8000, 35000),
            "grocery": (1500, 8000),
            "emi": (5000, 25000),
            "utility": (500, 5000),
            "shopping": (1000, 15000),
            "transfer": (2000, 50000),
        }
        lo, hi = amount_ranges[cat]
        txns.append({
            "date": random_date_in_range(start_date, end_date),
            "type": "debit",
            "category": cat,
            "amount": round(random.randint(lo, hi), -2),  # round to nearest 100
        })
    return txns


def generate_salary_transactions(base_salary: int, spike: bool, start_date: datetime) -> list:
    """Generate 3 monthly salary credits. If spike=True, last 2 are 40-80% higher."""
    txns = []
    if spike:
        salaries = [
            base_salary,
            int(base_salary * random.uniform(1.4, 1.8)),
            int(base_salary * random.uniform(1.4, 1.8)),
        ]
    else:
        salaries = [base_salary] * 3

    for i, sal in enumerate(salaries):
        month_offset = i
        dt = start_date + timedelta(days=30 * month_offset)
        txns.append({
            "date": dt.strftime("%Y-%m-%d"),
            "type": "credit",
            "category": "salary",
            "amount": round(sal, -2),
        })
    return txns


# ──────────────────────────────────────────────
# Signal-specific customer generators
# ──────────────────────────────────────────────

# Reference dates
TODAY = datetime(2026, 6, 23)
NINETY_DAYS_AGO = TODAY - timedelta(days=90)


def gen_salary_spike(cid: int) -> dict:
    base_salary = random.randint(30000, 80000)
    balances_old = [random.randint(20000, 60000) for _ in range(4)]
    new_bal = int(base_salary * random.uniform(1.5, 2.0))
    balances = balances_old + [new_bal, new_bal + random.randint(5000, 20000)]

    salary_txns = generate_salary_transactions(base_salary, spike=True, start_date=NINETY_DAYS_AGO)
    filler_txns = generate_base_transactions(random.randint(2, 4), NINETY_DAYS_AGO, TODAY)
    all_txns = sorted(salary_txns + filler_txns, key=lambda t: t["date"])

    return _build_customer(cid, "salary_spike", balances, all_txns)


def gen_idle_balance_high(cid: int) -> dict:
    old_avg = random.randint(30000, 80000)
    balances = [
        random.randint(old_avg - 10000, old_avg + 10000) for _ in range(3)
    ] + [
        random.randint(old_avg * 2, old_avg * 3) for _ in range(3)
    ]

    salary = random.randint(40000, 100000)
    salary_txns = generate_salary_transactions(salary, spike=False, start_date=NINETY_DAYS_AGO)
    filler_txns = generate_base_transactions(random.randint(1, 3), NINETY_DAYS_AGO, TODAY)
    all_txns = sorted(salary_txns + filler_txns, key=lambda t: t["date"])

    return _build_customer(cid, "idle_balance_high", balances, all_txns)


def gen_recurring_hospital_debit(cid: int) -> dict:
    balances = [random.randint(25000, 90000) for _ in range(6)]

    salary = random.randint(35000, 90000)
    salary_txns = generate_salary_transactions(salary, spike=False, start_date=NINETY_DAYS_AGO)

    hospital_txns = []
    for _ in range(random.randint(2, 4)):
        hospital_txns.append({
            "date": random_date_in_range(NINETY_DAYS_AGO, TODAY),
            "type": "debit",
            "category": random.choice(["hospital", "pharmacy"]),
            "amount": round(random.randint(3000, 25000), -2),
        })

    filler_txns = generate_base_transactions(random.randint(1, 3), NINETY_DAYS_AGO, TODAY)
    all_txns = sorted(salary_txns + hospital_txns + filler_txns, key=lambda t: t["date"])

    return _build_customer(cid, "recurring_hospital_debit", balances, all_txns)


def gen_recurring_school_fee(cid: int) -> dict:
    balances = [random.randint(30000, 100000) for _ in range(6)]

    salary = random.randint(40000, 100000)
    salary_txns = generate_salary_transactions(salary, spike=False, start_date=NINETY_DAYS_AGO)

    school_txns = []
    for _ in range(random.randint(2, 3)):
        school_txns.append({
            "date": random_date_in_range(NINETY_DAYS_AGO, TODAY),
            "type": "debit",
            "category": random.choice(["school_fee", "tuition"]),
            "amount": round(random.randint(10000, 60000), -2),
        })

    filler_txns = generate_base_transactions(random.randint(1, 3), NINETY_DAYS_AGO, TODAY)
    all_txns = sorted(salary_txns + school_txns + filler_txns, key=lambda t: t["date"])

    customer = _build_customer(cid, "recurring_school_fee", balances, all_txns)
    customer["age"] = random.randint(30, 48)  # parents with school-age kids
    return customer


def gen_forex_transaction_spike(cid: int) -> dict:
    balances = [random.randint(50000, 200000) for _ in range(6)]

    salary = random.randint(60000, 150000)
    salary_txns = generate_salary_transactions(salary, spike=False, start_date=NINETY_DAYS_AGO)

    forex_txns = []
    for _ in range(random.randint(3, 5)):
        forex_txns.append({
            "date": random_date_in_range(NINETY_DAYS_AGO, TODAY),
            "type": "debit",
            "category": random.choice(["forex", "travel", "international_transfer"]),
            "amount": round(random.randint(15000, 80000), -2),
        })

    filler_txns = generate_base_transactions(random.randint(1, 2), NINETY_DAYS_AGO, TODAY)
    all_txns = sorted(salary_txns + forex_txns + filler_txns, key=lambda t: t["date"])

    return _build_customer(cid, "forex_transaction_spike", balances, all_txns)


def gen_large_one_time_credit(cid: int) -> dict:
    base_bal = random.randint(40000, 120000)
    balances = [random.randint(base_bal - 10000, base_bal + 10000) for _ in range(5)]
    # Last month: huge spike from the credit
    large_amount = random.randint(200000, 1500000)
    balances.append(base_bal + large_amount)

    salary = random.randint(40000, 100000)
    salary_txns = generate_salary_transactions(salary, spike=False, start_date=NINETY_DAYS_AGO)

    large_credit = {
        "date": random_date_in_range(TODAY - timedelta(days=30), TODAY),
        "type": "credit",
        "category": random.choice(["bonus", "maturity", "inheritance", "insurance_payout"]),
        "amount": large_amount,
    }

    filler_txns = generate_base_transactions(random.randint(2, 4), NINETY_DAYS_AGO, TODAY)
    all_txns = sorted(salary_txns + [large_credit] + filler_txns, key=lambda t: t["date"])

    return _build_customer(cid, "large_one_time_credit", balances, all_txns)


def gen_dormant_high_value(cid: int) -> dict:
    high_bal = random.randint(150000, 500000)
    balances = [random.randint(high_bal - 20000, high_bal + 20000) for _ in range(6)]

    # Zero transactions in last 90 days — only old ones
    old_start = TODAY - timedelta(days=180)
    old_end = TODAY - timedelta(days=91)
    old_txns = generate_base_transactions(random.randint(2, 4), old_start, old_end)

    # Add a salary that stopped
    old_salary = {
        "date": random_date_in_range(old_start, old_end),
        "type": "credit",
        "category": "salary",
        "amount": round(random.randint(50000, 120000), -2),
    }
    all_txns = sorted(old_txns + [old_salary], key=lambda t: t["date"])

    customer = _build_customer(cid, "dormant_high_value", balances, all_txns)
    # Override: transactions_last_90d should be EMPTY for dormant
    customer["transactions_last_90d"] = []
    return customer


def _build_customer(cid: int, signal: str, balances: list, transactions: list) -> dict:
    """Assemble a complete customer record."""
    city = random.choice(CITIES)
    config = CITY_CONFIG[city]

    return {
        "customer_id": f"CUST{1001 + cid}",
        "name": random_name(),
        "age": random.randint(23, 58),
        "city": city,
        "language_pref": config["lang"],
        "account_type": random.choice(ACCOUNT_TYPES),
        "kyc_status": random.choice(KYC_STATUSES),
        "risk_profile": random.choice(RISK_PROFILES),
        "existing_products": random_products(signal),
        "monthly_balance_avg_6m": balances,
        "transactions_last_90d": transactions,
        "life_event_signals": [signal],
    }


# ──────────────────────────────────────────────
# Main generator
# ──────────────────────────────────────────────

SIGNAL_GENERATORS = {
    "salary_spike":              (gen_salary_spike, 12),
    "idle_balance_high":         (gen_idle_balance_high, 12),
    "recurring_hospital_debit":  (gen_recurring_hospital_debit, 11),
    "recurring_school_fee":      (gen_recurring_school_fee, 11),
    "forex_transaction_spike":   (gen_forex_transaction_spike, 11),
    "large_one_time_credit":     (gen_large_one_time_credit, 12),
    "dormant_high_value":        (gen_dormant_high_value, 11),
}


def main():
    random.seed(42)  # Reproducible output

    customers = []
    cid_counter = 0

    for signal, (generator_fn, count) in SIGNAL_GENERATORS.items():
        for _ in range(count):
            customer = generator_fn(cid_counter)
            customers.append(customer)
            cid_counter += 1

    # Shuffle so signals aren't grouped
    random.shuffle(customers)

    # Re-assign sequential IDs after shuffle
    for i, c in enumerate(customers):
        c["customer_id"] = f"CUST{1001 + i}"

    output = {"customers": customers}

    # Write output
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "customers.json")
    synthetic_output_path = os.path.join("data", "synthetic_customers.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    with open(synthetic_output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"[OK] Generated {len(customers)} customers -> {output_path}")
    print(f"[OK] Generated {len(customers)} customers -> {synthetic_output_path}")
    signal_counts = {}
    for c in customers:
        for s in c["life_event_signals"]:
            signal_counts[s] = signal_counts.get(s, 0) + 1
    for signal, count in sorted(signal_counts.items()):
        print(f"   {signal}: {count}")


if __name__ == "__main__":
    main()
