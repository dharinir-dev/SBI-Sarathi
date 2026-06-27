"""
SBI Sarathi — FastAPI Conversation Agent
Proactive banking assistant with local demo mode and optional LLM API support.

Set LLM_API_KEY in environment or .env file for live mode.
Without it, the server runs in demo mode with canned responses.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # Load .env file if present

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from db import get_memory, save_memory, create_escalation, get_escalation

from conversation_agent import (
    ConversationAgentResponse,
    ConversationRequest as ConversationAgentRequest,
    run_conversation_agent,
    derive_metadata,
)
from qualification_agent import (
    QualificationResponse,
    qualify_customer,
    choose_signal_type,
)
from signal_agent import (
    SignalResponse,
    detect_signals_for_customer,
    DetectedSignal,
)
from signal_router import route_signal

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="SBI Sarathi",
    description="Proactive banking assistant — signal-driven conversations",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Load customer data
# ──────────────────────────────────────────────

DATA_PATH = Path(__file__).parent / "data" / "customers.json"


def load_customers() -> dict:
    """Load and index customers by customer_id."""
    if not DATA_PATH.exists():
        raise RuntimeError(
            f"Customer data not found at {DATA_PATH}. "
            "Run `python generate_customers.py` first."
        )
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {c["customer_id"]: c for c in data["customers"]}


# Lazy-loaded customer index
_customers_cache: Optional[dict] = None


def get_customers() -> dict:
    global _customers_cache
    if _customers_cache is None:
        _customers_cache = load_customers()
    return _customers_cache


# ──────────────────────────────────────────────
# In-memory conversation store
# ──────────────────────────────────────────────

# { customer_id: { "messages": [...], "context": {...} } }
conversation_store: dict = {}

# ──────────────────────────────────────────────
# Sarathi system prompt
# ──────────────────────────────────────────────

SARATHI_SYSTEM_PROMPT = """You are Sarathi, SBI's proactive banking assistant. You are reaching out to a 
customer because our system detected a relevant financial signal — not because 
they asked. Your job is to start a warm, low-pressure conversation, not pitch.

RULES:
1. Open by referencing the real signal in plain language, never jargon. 
   E.g., "I noticed your salary's gone up nicely the last couple of months — 
   nice problem to have!" NOT "Our propensity model flagged X."
2. Never assume consent. Always ask before explaining a product: 
   "Want me to show you a quick option for that?"
3. If suitability_check is FAIL, say: "This needs a quick chat with one of our 
   relationship managers to make sure it's right for you — want me to set that up?"
   Do NOT explain or pitch the product yourself in this case.
4. Keep each message under 3 sentences. This is a chat, not an essay.
5. Always offer an easy exit: "No worries if not — just let me know if you'd 
   rather I check back later."
6. Reply in the customer's language_pref if it is "hi", "ta", or "en". Keep 
   tone respectful and warm regardless of language — avoid overly casual slang.
7. If the customer agrees to proceed, walk them through onboarding in short 
   conversational steps (confirm amount, confirm frequency, confirm consent) — 
   never dump a form's worth of fields in one message.
8. Never guarantee returns, never give specific investment advice beyond what's 
   in recommended_action, and always include one line of risk disclosure if the 
   product is market-linked (e.g., "SIPs are subject to market risk — past 
   performance doesn't guarantee future returns.").

GOAL: By the end of the conversation, the customer has either (a) completed 
a simple onboarding step, (b) been routed to a human RM, or (c) politely 
declined — all three are successful outcomes. Pressure is not.

CUSTOMER CONTEXT:
- Name: {customer_name}
- Language Preference: {language_pref}
- Risk Profile: {risk_profile}
- Existing Products: {existing_products}
- Triggered Signal: {triggered_signal}
- Recommended Action: {recommended_action}
- Suitability Check: {suitability_check}"""


def build_system_prompt(customer: dict, routing: dict) -> str:
    """Inject customer context into the Sarathi system prompt."""
    return SARATHI_SYSTEM_PROMPT.format(
        customer_name=customer["name"],
        language_pref=customer["language_pref"],
        risk_profile=customer["risk_profile"],
        existing_products=", ".join(customer["existing_products"]),
        triggered_signal=routing["triggered_signal"],
        recommended_action=routing["recommended_action"],
        suitability_check=routing["suitability_check"],
    )


# ──────────────────────────────────────────────
# Legacy-compatible LLM client name
# ──────────────────────────────────────────────

MODEL = os.environ.get("LLM_MODEL", "demo")


def _is_api_key_available() -> bool:
    """Check if LLM_API_KEY is set."""
    return bool(os.environ.get("LLM_API_KEY"))


def call_claude(system_prompt: str, messages: list) -> str:
    """
    Compatibility wrapper for the provider-neutral LLM client defined below.
    Falls back to demo mode if LLM_API_KEY is not set.
    """
    return _demo_response(system_prompt, messages)


# ──────────────────────────────────────────────
# Demo mode (no API key required)
# ──────────────────────────────────────────────

DEMO_RESPONSES = {
    "salary_spike": {
        "en": "Hi {name}! I noticed your salary has gone up nicely over the last couple of months \u2014 that\u2019s great news! Would you like me to show you a simple way to put that extra income to work? No worries if not \u2014 just let me know if you\u2019d rather I check back later.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940! \u092e\u0948\u0902\u0928\u0947 \u0926\u0947\u0916\u093e \u0915\u093f \u092a\u093f\u091b\u0932\u0947 \u0915\u0941\u091b \u092e\u0939\u0940\u0928\u094b\u0902 \u092e\u0947\u0902 \u0906\u092a\u0915\u0940 \u0938\u0948\u0932\u0930\u0940 \u092e\u0947\u0902 \u0905\u091a\u094d\u091b\u0940 \u092c\u0922\u093c\u094b\u0924\u0930\u0940 \u0939\u0941\u0908 \u0939\u0948 \u2014 \u092c\u0939\u0941\u0924 \u092c\u0927\u093e\u0908! \u0915\u094d\u092f\u093e \u0906\u092a \u091a\u093e\u0939\u0947\u0902\u0917\u0947 \u0915\u093f \u092e\u0948\u0902 \u0907\u0938 \u090f\u0915\u094d\u0938\u094d\u091f\u094d\u0930\u093e \u0907\u0928\u0915\u092e \u0915\u094b \u0938\u0939\u0940 \u091c\u0917\u0939 \u0932\u0917\u093e\u0928\u0947 \u0915\u093e \u090f\u0915 \u0906\u0938\u093e\u0928 \u0924\u0930\u0940\u0915\u093e \u092c\u0924\u093e\u090a\u0901? \u0905\u0917\u0930 \u0905\u092d\u0940 \u0928\u0939\u0940\u0902 \u0924\u094b \u0915\u094b\u0908 \u092c\u093e\u0924 \u0928\u0939\u0940\u0902 \u2014 \u092c\u093e\u0926 \u092e\u0947\u0902 \u092c\u093e\u0924 \u0915\u0930\u0947\u0902\u0917\u0947\u0964",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}! \u0b95\u0b9f\u0ba8\u0bcd\u0ba4 \u0b9a\u0bbf\u0bb2 \u0bae\u0bbe\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0bae\u0bcd\u0baa\u0bb3\u0bae\u0bcd \u0ba8\u0ba9\u0bcd\u0bb1\u0bbe\u0b95 \u0b89\u0baf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1 \u2014 \u0bae\u0bc1\u0ba4\u0bb2\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd! \u0b85\u0ba8\u0bcd\u0ba4 \u0b95\u0bc2\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd \u0bb5\u0bb0\u0bc1\u0bae\u0bbe\u0ba9\u0ba4\u0bcd\u0ba4\u0bc8 \u0b9a\u0bb0\u0bbf\u0baf\u0bbe\u0b95 \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0b92\u0bb0\u0bc1 \u0b8e\u0bb3\u0bbf\u0baf \u0bb5\u0bb4\u0bbf \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bb2\u0bbe\u0bae\u0bbe? \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bbe\u0bae\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bb0\u0bb5\u0bbe\u0baf\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8 \u2014 \u0baa\u0bbf\u0bb1\u0b95\u0bc1 \u0baa\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb2\u0bbe\u0bae\u0bcd.",
    },
    "idle_balance_high": {
        "en": "Hi {name}! I noticed you have a good amount sitting in your account that could be earning more for you. Want me to show you a couple of options to make it work harder? No worries if not \u2014 just let me know.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940! \u0906\u092a\u0915\u0947 \u0916\u093e\u0924\u0947 \u092e\u0947\u0902 \u0905\u091a\u094d\u091b\u0940 \u0930\u0915\u092e \u092a\u0921\u093c\u0940 \u0939\u0948 \u091c\u094b \u0914\u0930 \u091c\u094d\u092f\u093e\u0926\u093e \u0915\u092e\u093e \u0938\u0915\u0924\u0940 \u0939\u0948\u0964 \u0915\u094d\u092f\u093e \u092e\u0948\u0902 \u0915\u0941\u091b \u0906\u0938\u093e\u0928 \u0935\u093f\u0915\u0932\u094d\u092a \u092c\u0924\u093e\u090a\u0901? \u0905\u0917\u0930 \u0905\u092d\u0940 \u0928\u0939\u0940\u0902 \u0924\u094b \u0915\u094b\u0908 \u092c\u093e\u0924 \u0928\u0939\u0940\u0902\u0964",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}! \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba8\u0bb2\u0bcd\u0bb2 \u0ba4\u0bca\u0b95\u0bc8 \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1, \u0b85\u0ba4\u0bc8 \u0b87\u0ba9\u0bcd\u0ba9\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bbe\u0b95 \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bbe\u0bae\u0bcd. \u0b9a\u0bbf\u0bb2 \u0bb5\u0bb4\u0bbf\u0b95\u0bb3\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bb2\u0bbe\u0bae\u0bbe? \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bbe\u0bae\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bb0\u0bb5\u0bbe\u0baf\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8.",
    },
    "recurring_hospital_debit": {
        "en": "Hi {name}, I noticed a few medical expenses showing up recently. Health costs can add up \u2014 would you like me to show you how a health insurance plan could help cover those? No pressure at all.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940, \u092e\u0948\u0902\u0928\u0947 \u0926\u0947\u0916\u093e \u0915\u093f \u0939\u093e\u0932 \u0939\u0940 \u092e\u0947\u0902 \u0915\u0941\u091b \u092e\u0947\u0921\u093f\u0915\u0932 \u0916\u0930\u094d\u091a\u0947 \u0906\u090f \u0939\u0948\u0902\u0964 \u0915\u094d\u092f\u093e \u0906\u092a \u091a\u093e\u0939\u0947\u0902\u0917\u0947 \u0915\u093f \u092e\u0948\u0902 \u0939\u0947\u0932\u094d\u0925 \u0907\u0902\u0936\u094d\u092f\u094b\u0930\u0947\u0902\u0938 \u0915\u0947 \u092c\u093e\u0930\u0947 \u092e\u0947\u0902 \u092c\u0924\u093e\u090a\u0901? \u0915\u094b\u0908 \u091c\u094b\u0930 \u0928\u0939\u0940\u0902\u0964",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}, \u0b9a\u0bae\u0bc0\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb2 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0b9a\u0bcd \u0b9a\u0bc6\u0bb2\u0bb5\u0bc1\u0b95\u0bb3\u0bcd \u0bb5\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9. \u0b86\u0bb0\u0bcb\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc0\u0b9f\u0bc1 \u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bb2\u0bbe\u0bae\u0bbe? \u0b8e\u0ba8\u0bcd\u0ba4 \u0ba8\u0bbf\u0bb0\u0bcd\u0baa\u0ba8\u0bcd\u0ba4\u0bae\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0bcd\u0bb2\u0bc8.",
    },
    "recurring_school_fee": {
        "en": "Hi {name}! I see school fees coming through regularly \u2014 education costs only go up, right? Want me to show you a plan that can help you stay ahead of those? No worries if you\u2019d rather skip for now.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940! \u092e\u0948\u0902\u0928\u0947 \u0926\u0947\u0916\u093e \u0915\u093f \u0938\u094d\u0915\u0942\u0932 \u0915\u0940 \u092b\u0940\u0938 \u0928\u093f\u092f\u092e\u093f\u0924 \u0906 \u0930\u0939\u0940 \u0939\u0948\u0902\u0964 \u0915\u094d\u092f\u093e \u0906\u092a \u091a\u093e\u0939\u0947\u0902\u0917\u0947 \u0915\u093f \u092e\u0948\u0902 \u092c\u091a\u094d\u091a\u094b\u0902 \u0915\u0940 \u092a\u0922\u093c\u093e\u0908 \u0915\u0947 \u0932\u093f\u090f \u090f\u0915 \u092a\u094d\u0932\u093e\u0928 \u092c\u0924\u093e\u090a\u0901? \u0905\u0917\u0930 \u0905\u092d\u0940 \u0928\u0939\u0940\u0902 \u0924\u094b \u0915\u094b\u0908 \u092c\u093e\u0924 \u0928\u0939\u0940\u0902\u0964",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}! \u0baa\u0bb3\u0bcd\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bb0\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9. \u0b95\u0bb2\u0bcd\u0bb5\u0bbf\u0b9a\u0bcd \u0b9a\u0bc6\u0bb2\u0bb5\u0bc1\u0b95\u0bb3\u0bcd \u0b89\u0baf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc7 \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd, \u0b85\u0ba4\u0bb1\u0bcd\u0b95\u0bc1 \u0b92\u0bb0\u0bc1 \u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bb2\u0bbe\u0bae\u0bbe? \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bbe\u0bae\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bb0\u0bb5\u0bbe\u0baf\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8.",
    },
    "forex_transaction_spike": {
        "en": "Hi {name}! Looks like you\u2019ve been making quite a few international transactions lately. Have you considered a multi-currency forex card for better rates? Happy to explain if you\u2019re interested \u2014 or we can chat later.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940! \u0932\u0917\u0924\u093e \u0939\u0948 \u0939\u093e\u0932 \u092e\u0947\u0902 \u0906\u092a\u0928\u0947 \u0915\u093e\u092b\u0940 \u0907\u0902\u091f\u0930\u0928\u0947\u0936\u0928\u0932 \u091f\u094d\u0930\u093e\u0902\u091c\u0947\u0915\u094d\u0936\u0928 \u0915\u093f\u090f \u0939\u0948\u0902\u0964 \u092b\u0949\u0930\u0947\u0915\u094d\u0938 \u0915\u093e\u0930\u094d\u0921 \u0938\u0947 \u092c\u0947\u0939\u0924\u0930 \u0930\u0947\u091f\u094d\u0938 \u092e\u093f\u0932 \u0938\u0915\u0924\u0947 \u0939\u0948\u0902 \u2014 \u092c\u0924\u093e\u090a\u0901?",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}! \u0b9a\u0bae\u0bc0\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0baf \u0b85\u0ba8\u0bcd\u0ba8\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bb0\u0bbf\u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0ba9\u0bc8\u0b95\u0bb3\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0bc0\u0bb0\u0bcd\u0b95\u0bb3\u0bcd. \u0b83\u0baa\u0bbe\u0bb0\u0bc6\u0b95\u0bcd\u0bb8\u0bcd \u0b95\u0bbe\u0bb0\u0bcd\u0b9f\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bb2\u0bbe\u0bae\u0bbe? \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bbe\u0bae\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bbf\u0bb1\u0b95\u0bc1 \u0baa\u0bc7\u0b9a\u0bb2\u0bbe\u0bae\u0bcd.",
    },
    "large_one_time_credit": {
        "en": "Hi {name}! I noticed a significant amount came into your account recently \u2014 congratulations! Would you like to chat about ways to make the most of it? No rush at all.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940! \u0906\u092a\u0915\u0947 \u0916\u093e\u0924\u0947 \u092e\u0947\u0902 \u0939\u093e\u0932 \u0939\u0940 \u092e\u0947\u0902 \u090f\u0915 \u092c\u0921\u093c\u0940 \u0930\u0915\u092e \u0906\u0908 \u0939\u0948 \u2014 \u092c\u0927\u093e\u0908! \u0915\u094d\u092f\u093e \u0906\u092a \u091a\u093e\u0939\u0947\u0902\u0917\u0947 \u0915\u093f \u0907\u0938\u0947 \u0938\u0939\u0940 \u091c\u0917\u0939 \u0932\u0917\u093e\u0928\u0947 \u0915\u0947 \u092c\u093e\u0930\u0947 \u092e\u0947\u0902 \u092c\u093e\u0924 \u0915\u0930\u0947\u0902? \u0915\u094b\u0908 \u091c\u0932\u094d\u0926\u0940 \u0928\u0939\u0940\u0902\u0964",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}! \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0bae\u0bc0\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0ba4\u0bca\u0b95\u0bc8 \u0bb5\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1 \u2014 \u0bb5\u0bbe\u0bb4\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd! \u0b85\u0ba4\u0bc8 \u0b9a\u0bb0\u0bbf\u0baf\u0bbe\u0b95 \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4 \u0baa\u0bc7\u0b9a\u0bb2\u0bbe\u0bae\u0bbe? \u0b85\u0bb5\u0b9a\u0bb0\u0bae\u0bcd \u0b87\u0bb2\u0bcd\u0bb2\u0bc8.",
    },
    "dormant_high_value": {
        "en": "Hi {name}! It\u2019s been a while since we\u2019ve seen activity on your account, and you have a healthy balance sitting there. Want me to show you a simple way to earn some interest on it? No worries if you\u2019re happy as is.",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 {name} \u091c\u0940! \u0906\u092a\u0915\u0947 \u0916\u093e\u0924\u0947 \u092e\u0947\u0902 \u0915\u093e\u092b\u0940 \u0905\u091a\u094d\u091b\u0940 \u0930\u0915\u092e \u092a\u0921\u093c\u0940 \u0939\u0948 \u0932\u0947\u0915\u093f\u0928 \u0915\u0941\u091b \u0938\u092e\u092f \u0938\u0947 \u0915\u094b\u0908 \u0932\u0947\u0928\u0926\u0947\u0928 \u0928\u0939\u0940\u0902 \u0939\u0941\u0906\u0964 \u0915\u094d\u092f\u093e \u092e\u0948\u0902 FD \u0915\u0947 \u092c\u093e\u0930\u0947 \u092e\u0947\u0902 \u092c\u0924\u093e\u090a\u0901 \u091c\u093f\u0938\u0938\u0947 \u092c\u094d\u092f\u093e\u091c \u092d\u0940 \u092e\u093f\u0932\u0947? \u0905\u0917\u0930 \u0910\u0938\u0947 \u0939\u0940 \u0920\u0940\u0915 \u0939\u0948 \u0924\u094b \u0915\u094b\u0908 \u092c\u093e\u0924 \u0928\u0939\u0940\u0902\u0964",
        "ta": "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd {name}! \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba8\u0bb2\u0bcd\u0bb2 \u0ba4\u0bca\u0b95\u0bc8 \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1 \u0b86\u0ba9\u0bbe\u0bb2\u0bcd \u0b9a\u0bbf\u0bb2 \u0b95\u0bbe\u0bb2\u0bae\u0bbe\u0b95 \u0b8e\u0ba8\u0bcd\u0ba4 \u0baa\u0bb0\u0bbf\u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0ba9\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0bcd\u0bb2\u0bc8. FD \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0bb5\u0b9f\u0bcd\u0b9f\u0bbf \u0baa\u0bc6\u0bb1 \u0b92\u0bb0\u0bc1 \u0b8e\u0bb3\u0bbf\u0baf \u0bb5\u0bb4\u0bbf \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bb2\u0bbe\u0bae\u0bbe? \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bbe\u0bae\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bb0\u0bb5\u0bbe\u0baf\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8.",
    },
}

DEMO_FOLLOW_UP = {
    "en": "[DEMO MODE] Thanks for your interest! In live mode, Sarathi would continue the conversation with your configured LLM. To enable live mode, set LLM_API_KEY in the .env file.",
    "hi": "[DEMO MODE] \u0906\u092a\u0915\u0940 \u0930\u0941\u091a\u093f \u0915\u0947 \u0932\u093f\u090f \u0927\u0928\u094d\u092f\u0935\u093e\u0926! \u0932\u093e\u0907\u0935 \u092e\u094b\u0921 \u092e\u0947\u0902, \u0938\u093e\u0930\u0925\u0940 \u0906\u092a\u0915\u0947 configured LLM \u0915\u0947 \u0938\u093e\u0925 \u092c\u093e\u0924\u091a\u0940\u0924 \u091c\u093e\u0930\u0940 \u0930\u0916\u0947\u0917\u093e\u0964 .env \u092b\u093e\u0907\u0932 \u092e\u0947\u0902 LLM_API_KEY \u0938\u0947\u091f \u0915\u0930\u0947\u0902\u0964",
    "ta": "[DEMO MODE] \u0ba8\u0ba9\u0bcd\u0bb1\u0bbf! \u0bb2\u0bc8\u0bb5\u0bcd \u0bae\u0bcb\u0b9f\u0bbf\u0bb2\u0bcd, \u0b9a\u0bbe\u0bb0\u0ba4\u0bbf \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd configured LLM \u0b89\u0b9f\u0ba9\u0bcd \u0b89\u0bb0\u0bc8\u0baf\u0bbe\u0b9f\u0bb2\u0bc8 \u0ba4\u0bca\u0b9f\u0bb0\u0bc1\u0bae\u0bcd. .env \u0b95\u0bcb\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd LLM_API_KEY \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd.",
}


def _demo_response(system_prompt: str, messages: list) -> str:
    """Generate a canned response for demo mode (no API key)."""
    # Extract context from system prompt
    import re

    # Parse language
    lang_match = re.search(r"Language Preference: (\w+)", system_prompt)
    lang = lang_match.group(1) if lang_match else "en"

    # Parse name
    name_match = re.search(r"Name: (.+)", system_prompt)
    name = name_match.group(1).strip() if name_match else "Customer"

    # Parse signal
    signal_match = re.search(r"Triggered Signal: (\w+)", system_prompt)
    signal = signal_match.group(1) if signal_match else "idle_balance_high"

    # Parse suitability and enforce RM routing in demo mode.
    suitability_match = re.search(r"Suitability Check: (\w+)", system_prompt)
    suitability = suitability_match.group(1) if suitability_match else "PASS"
    if suitability == "FAIL":
        fail_messages = {
            "en": "This needs a quick chat with one of our relationship managers to make sure it's right for you - want me to set that up? No worries if not - just let me know if you'd rather I check back later.",
            "hi": "यह आपके लिए सही है या नहीं, यह पक्का करने के लिए हमारे relationship manager से एक छोटी बातचीत बेहतर रहेगी - क्या मैं उसे सेट कर दूं? अभी नहीं तो कोई बात नहीं - आप चाहें तो मैं बाद में चेक कर सकता हूं।",
            "ta": "இது உங்களுக்கு சரியாக இருக்கிறதா என்பதை உறுதி செய்ய எங்கள் relationship manager உடன் ஒரு சுருக்கமான உரையாடல் நல்லது - அதை ஏற்பாடு செய்யவா? வேண்டாம் என்றால் பரவாயில்லை - பிறகு பார்க்கச் சொல்லுங்கள்.",
        }
        return fail_messages.get(lang, fail_messages["en"])

    # Check if this is a follow-up (more than 1 user message)
    user_messages = [m for m in messages if m["role"] == "user"]
    if len(user_messages) > 1:
        return DEMO_FOLLOW_UP.get(lang, DEMO_FOLLOW_UP["en"])

    # Opening message
    templates = DEMO_RESPONSES.get(signal, DEMO_RESPONSES["idle_balance_high"])
    template = templates.get(lang, templates["en"])
    return template.format(name=name.split()[0])


# Runtime overrides: provider-neutral prompt and LLM client.
SARATHI_SYSTEM_PROMPT = """You are Sarathi, SBI's proactive banking assistant. You are reaching out to a
customer because our system detected a relevant financial signal - not because
they asked. Your job is to start a warm, low-pressure conversation, not pitch.

CONTEXT PROVIDED TO YOU PER CONVERSATION:
- customer_name, language_pref, risk_profile, existing_products
- triggered_signal
- recommended_action
- suitability_check: PASS/FAIL

RULES:
1. Open by referencing the real signal in plain language, never jargon.
   Example: "I noticed your salary's gone up nicely the last couple of months -
   nice problem to have!" NOT "Our propensity model flagged X."
2. Never assume consent. Always ask before explaining a product:
   "Want me to show you a quick option for that?"
3. If suitability_check is FAIL, say: "This needs a quick chat with one of our
   relationship managers to make sure it's right for you - want me to set that up?"
   Do NOT explain or pitch the product yourself in this case.
4. Keep each message under 3 sentences. This is a chat, not an essay.
5. Always offer an easy exit: "No worries if not - just let me know if you'd
   rather I check back later."
6. Reply in the customer's language_pref if it is "hi", "ta", or "en". Keep
   tone respectful and warm regardless of language - avoid overly casual slang.
7. If the customer agrees to proceed, walk them through onboarding in short
   conversational steps: confirm amount, confirm frequency, confirm consent.
   Never dump a form's worth of fields in one message.
8. Never guarantee returns, never give specific investment advice beyond what's
   in recommended_action, and always include one line of risk disclosure if the
   product is market-linked. Example: "SIPs are subject to market risk - past
   performance doesn't guarantee future returns."

GOAL: By the end of the conversation, the customer has either (a) completed
a simple onboarding step, (b) been routed to a human RM, or (c) politely
declined. All three are successful outcomes. Pressure is not.

CUSTOMER CONTEXT:
- Name: {customer_name}
- Language Preference: {language_pref}
- Risk Profile: {risk_profile}
- Existing Products: {existing_products}
- Triggered Signal: {triggered_signal}
- Recommended Action: {recommended_action}
- Suitability Check: {suitability_check}"""

MODEL = os.environ.get("LLM_MODEL", "demo")
LLM_API_BASE_URL = os.environ.get(
    "LLM_API_BASE_URL",
    "https://api.openai.com/v1/chat/completions",
)


def _is_api_key_available() -> bool:
    """Check if a provider-neutral chat API key is set."""
    return bool(os.environ.get("LLM_API_KEY"))


def call_claude(system_prompt: str, messages: list) -> str:
    """
    Generate Sarathi's response.

    Despite the historical function name, this no longer uses Anthropic. If
    LLM_API_KEY is present, it calls an OpenAI-compatible chat completions API.
    Otherwise it falls back to demo responses so the endpoint works locally.
    """
    if not _is_api_key_available():
        return _demo_response(system_prompt, messages)

    import urllib.error
    import urllib.request

    payload = {
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.4,
        "max_tokens": 512,
    }
    request = urllib.request.Request(
        LLM_API_BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['LLM_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise HTTPException(status_code=502, detail=f"LLM API error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"LLM API unavailable: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="LLM API returned an unexpected response") from exc


# ──────────────────────────────────────────────
# Request/Response models
# ──────────────────────────────────────────────

class ConversationReplyRequest(BaseModel):
    customer_id: str
    user_message: str


class ConversationResponse(BaseModel):
    customer_id: str
    customer_name: str
    language_pref: str
    triggered_signal: str
    recommended_action: str
    suitability_check: str
    assistant_message: str
    turn_count: int


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.post("/conversation", response_model=ConversationAgentResponse, tags=["conversation"])
def start_conversation(req: ConversationAgentRequest):
    """
    Conversation Agent — generate Sarathi's opening message from routed context.

    Accepts customer context and signal routing output, returns a warm opening
    message plus structured intent metadata for the orchestration layer.
    """
    llm_call = call_claude if _is_api_key_available() else None
    return run_conversation_agent(req, llm_call=llm_call)


def check_auto_escalate_text(text: str) -> Optional[str]:
    """Check text for keywords that should trigger human RM escalation."""
    text_lower = text.lower()
    human_keywords = ["human", "representative", "manager", "person", "agent", "connect", "talk to", "rm", "relationship manager", "speak"]
    advice_keywords = ["portfolio", "tax", "equity", "stocks", "mutual fund", "advice", "advise", "market", "return"]
    dissatisfaction_keywords = ["bad", "worst", "unhappy", "useless", "annoyed", "stop", "complain", "disappointed", "poor", "hate", "scam", "fraud"]

    for kw in human_keywords:
        if kw in text_lower:
            return "Customer requested human assistance"
    for kw in advice_keywords:
        if kw in text_lower:
            return "Customer asked for complex financial advice"
    for kw in dissatisfaction_keywords:
        if kw in text_lower:
            return "Customer reported dissatisfaction"
    return None


def transition_stage(current_stage: str, user_message: str) -> str:
    """Transition conversation stage based on user message content."""
    msg = user_message.lower()
    
    # Positive/negative intent words
    positives = ["yes", "sure", "ok", "okay", "haan", "batao", "proceed", "agreed", "want", "show", "tell me"]
    negatives = ["no", "skip", "later", "not now", "exit", "stop", "don't", "dont", "nay"]
    
    if current_stage in ("initial_outreach", "awaiting_permission"):
        if any(w in msg for w in negatives):
            return "declined"
        elif any(w in msg for w in positives):
            return "awaiting_amount"
        return "awaiting_permission"
        
    elif current_stage == "awaiting_amount":
        import re
        if re.search(r'\d+', msg) or any(w in msg for w in ["thousand", "lakh", "crore", "hundred"]):
            return "awaiting_frequency"
        if any(w in msg for w in negatives):
            return "declined"
        return "awaiting_amount"
        
    elif current_stage == "awaiting_frequency":
        frequencies = ["monthly", "month", "year", "annual", "weekly", "week", "once", "daily", "sip", "lumpsum"]
        if any(w in msg for w in frequencies):
            return "awaiting_consent"
        if any(w in msg for w in negatives):
            return "declined"
        return "awaiting_frequency"
        
    elif current_stage == "awaiting_consent":
        consent_words = ["yes", "confirm", "agree", "proceed", "do it", "approve", "consent"]
        if any(w in msg for w in consent_words):
            return "completed"
        if any(w in msg for w in negatives):
            return "declined"
        return "awaiting_consent"
        
    return current_stage


@app.post("/conversation/reply", response_model=ConversationResponse)
def reply_conversation(req: ConversationReplyRequest):
    """
    Continue an existing conversation. The customer sends a reply,
    and Sarathi responds with the next conversational step.
    """
    customers = get_customers()
    customer = customers.get(req.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {req.customer_id} not found")

    # Check for existing conversation in database
    mem = get_memory(req.customer_id)
    if not mem:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No active conversation for {req.customer_id}. "
                "Start one by calling GET /engage/{customer_id} first."
            ),
        )

    history = mem["conversation_history"]
    current_stage = mem["current_stage"]

    # Check for auto-escalation based on message content
    escalation_reason = check_auto_escalate_text(req.user_message)
    
    if escalation_reason:
        # Create ticket
        ticket = create_escalation(req.customer_id, escalation_reason)
        # Update history
        history.append({"role": "user", "content": req.user_message})
        assistant_reply = (
            "I understand you need assistance. I am connecting you with a "
            "Relationship Manager right away who can help you with this. "
            f"Your ticket ID is {ticket['ticket_id']}."
        )
        history.append({"role": "assistant", "content": assistant_reply})
        # Save memory
        save_memory(req.customer_id, history, "escalated")
    else:
        # Normal conversation flow
        history.append({"role": "user", "content": req.user_message})
        
        # Transition stage
        next_stage = transition_stage(current_stage, req.user_message)
        
        # Check if we should send a fixed closing message or call Claude
        if next_stage == "declined":
            assistant_reply = "No problem at all! Let me know if you change your mind. Have a great day!"
            history.append({"role": "assistant", "content": assistant_reply})
            current_stage = "declined"
        elif next_stage == "completed":
            assistant_reply = "Perfect, thank you! I've set up your request and you'll receive a confirmation SMS shortly."
            history.append({"role": "assistant", "content": assistant_reply})
            current_stage = "completed"
        else:
            # Reconstruct system prompt and routing context
            qual_res = qualify_customer(req.customer_id)
            signal_type = qual_res.signal_type if qual_res else choose_signal_type(customer)
            routing = route_signal(customer, signal_type)
            
            system_prompt = build_system_prompt(customer, routing)
            
            # Call Claude/LLM with full history
            assistant_reply = call_claude(system_prompt, history)
            history.append({"role": "assistant", "content": assistant_reply})
            current_stage = next_stage
            
        save_memory(req.customer_id, history, current_stage)

    # Count assistant messages
    turn_count = len([m for m in history if m["role"] == "assistant"])

    # Reconstruct routing context for the response object
    qual_res = qualify_customer(req.customer_id)
    signal_type = qual_res.signal_type if qual_res else choose_signal_type(customer)
    routing = route_signal(customer, signal_type)

    return ConversationResponse(
        customer_id=req.customer_id,
        customer_name=customer["name"],
        language_pref=customer["language_pref"],
        triggered_signal=routing["triggered_signal"],
        recommended_action=routing["recommended_action"],
        suitability_check=routing["suitability_check"],
        assistant_message=assistant_reply,
        turn_count=turn_count,
    )


@app.get("/customers")
def list_customers():
    """List all customers with their IDs, names, and signals."""
    customers = get_customers()
    return [
        {
            "customer_id": c["customer_id"],
            "name": c["name"],
            "city": c["city"],
            "language_pref": c["language_pref"],
            "life_event_signals": c["life_event_signals"],
        }
        for c in customers.values()
    ]


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    """Get full details for a specific customer."""
    customers = get_customers()
    customer = customers.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


@app.get("/signals/{customer_id}", response_model=SignalResponse, tags=["signals"])
def get_signals(customer_id: str):
    """Detect financial life-event signals for a customer."""
    response = detect_signals_for_customer(customer_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return response


@app.get("/qualify/{customer_id}", response_model=QualificationResponse, tags=["qualification"])
def qualify(customer_id: str):
    """Score product propensity and qualification for a customer."""
    response = qualify_customer(customer_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return response


class EscalationRequest(BaseModel):
    customer_id: str
    reason: str


class EscalationResponse(BaseModel):
    ticket_id: str
    status: str
    assigned_to: str


class MemoryStateResponse(BaseModel):
    customer_id: str
    conversation_history: list[dict]
    current_stage: str
    last_updated: str


class MemoryUpdateRequest(BaseModel):
    conversation_history: list[dict]
    current_stage: str


class EngageResponse(BaseModel):
    customer_id: str
    signals: list[DetectedSignal]
    qualification: QualificationResponse
    conversation: ConversationAgentResponse
    memory: MemoryStateResponse
    escalation: Optional[EscalationResponse] = None


@app.post("/escalate", response_model=EscalationResponse, tags=["escalation"])
def escalate(req: EscalationRequest):
    """Create a Relationship Manager handoff ticket."""
    customers = get_customers()
    if req.customer_id not in customers:
        raise HTTPException(status_code=404, detail=f"Customer {req.customer_id} not found")
        
    ticket = create_escalation(req.customer_id, req.reason)
    
    # Also update memory state to escalated
    mem = get_memory(req.customer_id)
    history = mem["conversation_history"] if mem else []
    
    # Append RM escalation system notice
    history.append({
        "role": "assistant",
        "content": f"[SYSTEM] Escalated to Relationship Manager: {req.reason}. Ticket {ticket['ticket_id']} created."
    })
    save_memory(req.customer_id, history, "escalated")
    
    return EscalationResponse(
        ticket_id=ticket["ticket_id"],
        status=ticket["status"],
        assigned_to=ticket["assigned_to"]
    )


@app.get("/memory/{customer_id}", response_model=MemoryStateResponse, tags=["memory"])
def get_customer_memory(customer_id: str):
    """Retrieve conversation memory for a customer."""
    customers = get_customers()
    if customer_id not in customers:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
        
    mem = get_memory(customer_id)
    if not mem:
        now_iso = datetime.utcnow().isoformat() + "Z"
        return MemoryStateResponse(
            customer_id=customer_id,
            conversation_history=[],
            current_stage="initial_outreach",
            last_updated=now_iso
        )
    return MemoryStateResponse(**mem)


@app.post("/memory/{customer_id}", response_model=MemoryStateResponse, tags=["memory"])
def update_customer_memory(customer_id: str, req: MemoryUpdateRequest):
    """Update conversation memory for a customer."""
    customers = get_customers()
    if customer_id not in customers:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
        
    mem = save_memory(customer_id, req.conversation_history, req.current_stage)
    return MemoryStateResponse(**mem)


@app.get("/engage/{customer_id}", response_model=EngageResponse, tags=["orchestrator"])
def engage_customer(customer_id: str):
    """
    Engage Orchestrator:
    1. Call Signal Agent to detect signals.
    2. Call Qualification Agent to qualify customer.
    3. Call Conversation Agent to generate opening message if no active memory.
    4. Handle auto-escalations (if suitability FAIL, propensity > 0.90, etc.)
    5. Return combined response.
    """
    customers = get_customers()
    customer = customers.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
        
    # 1. Call Signal Agent
    signals_res = detect_signals_for_customer(customer_id)
    signals = signals_res.signals if signals_res else []
    
    # 2. Call Qualification Agent
    qual_res = qualify_customer(customer_id)
    
    # Check if memory already exists
    mem = get_memory(customer_id)
    escalation_ticket = get_escalation(customer_id)
    
    # Check for auto-escalations based on qualification rules
    auto_escalated = False
    escalation_reason = ""
    
    if qual_res:
        if qual_res.suitability == "FAIL":
            auto_escalated = True
            escalation_reason = "Suitability FAIL"
        elif qual_res.propensity_score > 0.90:
            auto_escalated = True
            escalation_reason = f"High propensity score ({qual_res.propensity_score}) - high touch lead"
            
    if auto_escalated and not escalation_ticket:
        # Create escalation ticket automatically
        escalation_ticket = create_escalation(customer_id, escalation_reason)
        # Also update memory stage to escalated
        stage = "escalated"
        history = mem["conversation_history"] if mem else []
        history.append({
            "role": "assistant",
            "content": f"[SYSTEM] Automatically escalated: {escalation_reason}. Ticket {escalation_ticket['ticket_id']} created."
        })
        mem = save_memory(customer_id, history, stage)
        
    # If not escalated but we have a ticket, make sure stage is escalated
    if escalation_ticket and mem and mem["current_stage"] != "escalated":
        mem = save_memory(customer_id, mem["conversation_history"], "escalated")

    # 3. Call Conversation Agent (if not already initiated)
    if not mem:
        # Initialize conversation
        stage = "escalated" if auto_escalated else "awaiting_permission"
        
        # Route signal to get action info
        signal_type = qual_res.signal_type if qual_res else choose_signal_type(customer)
        routing = route_signal(customer, signal_type)
        if auto_escalated:
            routing["suitability_check"] = "FAIL"
            
        conv_req = ConversationAgentRequest(
            customer_name=customer["name"],
            language_pref=customer["language_pref"],
            triggered_signal=signal_type,
            recommended_action=routing["recommended_action"],
            suitability_check=routing["suitability_check"]
        )
        
        llm_call = call_claude if _is_api_key_available() else None
        conv_res = run_conversation_agent(conv_req, llm_call=llm_call)
        
        # Save initial outreach message to memory
        history = [{"role": "assistant", "content": conv_res.message}]
        mem = save_memory(customer_id, history, stage)
    else:
        # Conversation already exists in memory, rebuild/retrieve ConversationAgentResponse
        last_assistant_msg = ""
        for m in reversed(mem["conversation_history"]):
            if m["role"] == "assistant":
                last_assistant_msg = m["content"]
                break
                
        # Reconstruct ConversationAgentResponse
        intent, next_step, escalate_flag = derive_metadata(qual_res.suitability if qual_res else "PASS")
        if mem["current_stage"] == "escalated":
            intent, next_step, escalate_flag = "escalate_to_rm", "wait_for_customer", True
            
        conv_res = ConversationAgentResponse(
            message=last_assistant_msg or "Hello!",
            intent=intent,
            next_step=next_step,
            escalate=escalate_flag
        )

    # Re-fetch escalation if created during this call
    esc_response = None
    if escalation_ticket:
        esc_response = EscalationResponse(
            ticket_id=escalation_ticket["ticket_id"],
            status=escalation_ticket["status"],
            assigned_to=escalation_ticket["assigned_to"]
        )
        
    return EngageResponse(
        customer_id=customer_id,
        signals=signals,
        qualification=qual_res,
        conversation=conv_res,
        memory=MemoryStateResponse(**mem),
        escalation=esc_response
    )


@app.delete("/memory/{customer_id}", tags=["memory"])
def reset_customer_memory(customer_id: str):
    """Reset conversation memory and delete escalation tickets for a customer."""
    db.init_db()
    with db.get_db_connection() as conn:
        conn.execute("DELETE FROM memory WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM escalations WHERE customer_id = ?", (customer_id,))
        conn.commit()
    return {"status": "reset", "customer_id": customer_id}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    customers = get_customers()
    return {
        "status": "healthy",
        "total_customers": len(customers),
        "model": MODEL,
    }
