"""
SBI Sarathi — Signal Router
Maps triggered signals to recommended actions and performs suitability checks.
"""

# ──────────────────────────────────────────────
# Signal → Action mapping
# ──────────────────────────────────────────────

SIGNAL_ACTION_MAP = {
    "salary_spike": {
        "recommended_action": "suggest_recurring_sip",
        "description": "Start a monthly SIP to grow the increased income",
        "product_type": "market_linked",
    },
    "idle_balance_high": {
        "recommended_action": "suggest_fd_or_sip",
        "description": "Park idle funds in an FD or start a SIP",
        "product_type": "mixed",
    },
    "recurring_hospital_debit": {
        "recommended_action": "suggest_health_insurance",
        "description": "Health insurance to cover recurring medical expenses",
        "product_type": "insurance",
    },
    "recurring_school_fee": {
        "recommended_action": "suggest_child_education_plan",
        "description": "Child education savings plan for future fees",
        "product_type": "mixed",
    },
    "forex_transaction_spike": {
        "recommended_action": "suggest_forex_card",
        "description": "Multi-currency forex card for better exchange rates",
        "product_type": "banking",
    },
    "large_one_time_credit": {
        "recommended_action": "suggest_wealth_consult",
        "description": "Wealth management consultation for the lump sum",
        "product_type": "advisory",
    },
    "dormant_high_value": {
        "recommended_action": "suggest_reengagement_fd",
        "description": "Fixed deposit to earn interest on dormant balance",
        "product_type": "deposit",
    },
}


def check_suitability(customer: dict, signal: str) -> str:
    """
    Run suitability checks for a given signal against the customer profile.
    
    Returns:
        "PASS" if the product can be pitched directly
        "FAIL" if the customer should be escalated to an RM
    """
    kyc = customer.get("kyc_status", "pending")
    risk = customer.get("risk_profile", "conservative")
    balances = customer.get("monthly_balance_avg_6m", [])
    current_balance = balances[-1] if balances else 0

    # Gate 1: KYC must be complete for all signals
    if kyc != "complete":
        return "FAIL"

    # Gate 2: Signal-specific suitability rules
    if signal == "salary_spike":
        # SIP is market-linked — not suitable for conservative profiles
        if risk == "conservative":
            return "FAIL"

    elif signal == "idle_balance_high":
        # FD is fine for all, but SIP portion needs non-conservative
        pass  # PASS — Sarathi can suggest FD to conservative customers

    elif signal == "large_one_time_credit":
        # Wealth consult requires meaningful balance
        if current_balance < 500000:
            return "FAIL"

    elif signal == "dormant_high_value":
        # Dormant account — if KYC is pending, can't do anything
        pass  # Already handled by Gate 1

    # All other signals pass if KYC is complete
    return "PASS"


def route_signal(customer: dict, signal: str) -> dict:
    """
    Given a customer and a triggered signal, return the full routing context
    for the Conversation Agent.
    
    Returns:
        dict with keys: triggered_signal, recommended_action, description,
        product_type, suitability_check
    """
    if signal not in SIGNAL_ACTION_MAP:
        return {
            "triggered_signal": signal,
            "recommended_action": "escalate_to_rm",
            "description": "Unknown signal — escalate to relationship manager",
            "product_type": "unknown",
            "suitability_check": "FAIL",
        }

    action_info = SIGNAL_ACTION_MAP[signal]
    suitability = check_suitability(customer, signal)

    return {
        "triggered_signal": signal,
        "recommended_action": action_info["recommended_action"],
        "description": action_info["description"],
        "product_type": action_info["product_type"],
        "suitability_check": suitability,
    }
