"""
Quick test script for the /conversation and /conversation/reply endpoints.
Run while the server is active: python test_conversation.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"


def post(endpoint: str, data: dict) -> dict:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP {e.code}: {error_body}")
        return {}


def get(endpoint: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{endpoint}", method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    # 1. Health check
    print("=" * 60)
    print("1. Health Check")
    print("=" * 60)
    health = get("/health")
    print(json.dumps(health, indent=2))
    print()

    # 2. Pick a customer for testing
    customer_id = sys.argv[1] if len(sys.argv) > 1 else "CUST1005"
    customer = get(f"/customers/{customer_id}")
    signal = customer["life_event_signals"][0]
    print("=" * 60)
    print(f"2. Customer: {customer['name']} ({customer_id})")
    print(f"   City: {customer['city']}, Lang: {customer['language_pref']}")
    print(f"   Signal: {signal}")
    print(f"   Risk: {customer['risk_profile']}, KYC: {customer['kyc_status']}")
    print("=" * 60)
    print()

    # 3. Start conversation
    print("=" * 60)
    print("3. Starting Conversation (POST /conversation)")
    print("=" * 60)
    routing = __import__("signal_router").route_signal(customer, signal)
    result = post("/conversation", {
        "customer_name": customer["name"],
        "language_pref": customer["language_pref"],
        "triggered_signal": signal,
        "recommended_action": routing["recommended_action"],
        "suitability_check": routing["suitability_check"],
    })
    if not result:
        print("Failed to start conversation. Check the server logs for details.")
        return

    print(f"   Intent: {result['intent']}")
    print(f"   Next step: {result['next_step']}")
    print(f"   Escalate: {result['escalate']}")
    print(f"\n   Sarathi: {result['message']}")
    print()

    # 4. Simulate customer reply
    print("=" * 60)
    print("4. Customer replies (POST /conversation/reply)")
    print("=" * 60)
    user_reply = "Haan, batao kya option hai?"
    print(f"   Customer: {user_reply}")

    result2 = post("/conversation/reply", {
        "customer_id": customer_id,
        "user_message": user_reply,
    })
    if result2:
        print(f"   Turn: {result2['turn_count']}")
        print(f"\n   Sarathi: {result2['assistant_message']}")
    print()

    print("=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
