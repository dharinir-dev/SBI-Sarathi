"""
SBI Sarathi — Conversation Agent
Generates proactive opening messages with structured intent metadata.
"""

from pydantic import BaseModel

SARATHI_SYSTEM_PROMPT = """You are Sarathi, SBI's proactive banking assistant. You are reaching out to a
customer because our system detected a relevant financial signal - not because
they asked. Your job is to start a warm, low-pressure conversation, not pitch.

CONTEXT PROVIDED TO YOU PER CONVERSATION:
- customer_name, language_pref
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
- Triggered Signal: {triggered_signal}
- Recommended Action: {recommended_action}
- Suitability Check: {suitability_check}"""

OPENING_USER_PROMPT = (
    "You are starting a new proactive conversation with this customer. "
    "Send your warm opening message based on the triggered signal. "
    "Remember: reference the signal in plain language, keep it under 3 sentences, "
    "and offer an easy exit."
)

DEMO_RESPONSES = {
    "salary_spike": {
        "en": "Hi {name}! I noticed your salary has gone up nicely over the last couple of months — that's great news! Would you like me to show you a simple way to put that extra income to work? No worries if not — just let me know if you'd rather I check back later.",
        "hi": "नमस्ते {name} जी! मैंने देखा कि पिछले कुछ महीनों में आपकी सैलरी में अच्छी बढ़ोतरी हुई है — बहुत बढ़िया! क्या आप चाहेंगे कि मैं उस एक्स्ट्रा इनकम को सही जगह लगाने का एक आसान तरीका बताऊँ? अगर अभी नहीं तो कोई बात नहीं — बाद में बात करेंगे।",
        "ta": "வணக்கம் {name}! கடந்த சில மாதங்களில் உங்கள் சம்பளம் நன்றாக உயர்ந்திருக்கிறது — முதலில் வாழ்த்துக்கள்! அந்த கூடுதல் வருமானத்தை சரியாக பயன்படுத்த ஒரு எளிய வழி காட்டலாமா? வேண்டாம் என்றால் பரவாயில்லை — பிறகு பார்க்கலாம்.",
    },
    "idle_balance_high": {
        "en": "Hi {name}! I noticed you have a good amount sitting in your account that could be earning more for you. Want me to show you a couple of options to make it work harder? No worries if not — just let me know.",
        "hi": "नमस्ते {name} जी! आपके खाते में अच्छी रकम पड़ी है जो और ज्यादा कमा सकती है। क्या मैं कुछ आसान विकल्प बताऊँ? अगर अभी नहीं तो कोई बात नहीं।",
        "ta": "வணக்கம் {name}! உங்கள் கணக்கில் நல்ல தொகை இருக்கிறது, அதை இன்னும் சிறப்பாக பயன்படுத்தலாம். சில வழிகள் காட்டலாமா? வேண்டாம் என்றால் பரவாயில்லை.",
    },
    "recurring_hospital_debit": {
        "en": "Hi {name}, I noticed a few medical expenses showing up recently. Health costs can add up — would you like me to show you how a health insurance plan could help cover those? No pressure at all.",
        "hi": "नमस्ते {name} जी, हाल ही में कुछ मेडिकल खर्चे आए हैं। क्या आप चाहेंगे कि मैं हेल्थ इंश्योरेंस के बारे में बताऊँ? कोई जोर नहीं।",
        "ta": "வணக்கம் {name}, சமீபத்தில் சில மருத்துவ செலவுகள் வந்திருக்கின்றன. ஆரோக்கிய காப்பீடு பற்றி காட்டலாமா? எந்த நிர்பந்தமும் இல்லை.",
    },
    "recurring_school_fee": {
        "en": "Hi {name}! I see school fees coming through regularly — education costs only go up, right? Want me to show you a plan that can help you stay ahead of those? No worries if you'd rather skip for now.",
        "hi": "नमस्ते {name} जी! स्कूल की फीस नियमित आ रही है। क्या आप चाहेंगे कि मैं बच्चों की पढ़ाई के लिए एक प्लान बताऊँ? अगर अभी नहीं तो कोई बात नहीं।",
        "ta": "வணக்கம் {name}! பள்ளிக்கூட கட்டணங்கள் தொடர்ந்து வருகின்றன. கல்வி செலவுகளுக்கு முன்னே ஒரு திட்டம் காட்டலாமா? வேண்டாம் என்றால் பரவாயில்லை.",
    },
    "forex_transaction_spike": {
        "en": "Hi {name}! Looks like you've been making quite a few international transactions lately. Have you considered a multi-currency forex card for better rates? Happy to explain if you're interested — or we can chat later.",
        "hi": "नमस्ते {name} जी! हाल में आपने काफी इंटरनेशनल ट्रांजेक्शन किए हैं। फॉरेक्स कार्ड से बेहतर रेट्स मिल सकते हैं — बताऊँ?",
        "ta": "வணக்கம் {name}! சமீபத்தில் நிறைய அன்னிய பரிவர்த்தனைகள் செய்திருக்கிறீர்கள். ஃபாரெக்ஸ் கார்ட் பற்றி காட்டலாமா? வேண்டாம் என்றால் பிறகு பேசலாம்.",
    },
    "large_one_time_credit": {
        "en": "Hi {name}! I noticed a significant amount came into your account recently — congratulations! Would you like to chat about ways to make the most of it? No rush at all.",
        "hi": "नमस्ते {name} जी! आपके खाते में हाल ही में एक बड़ी रकम आई है — बधाई! क्या आप इसे सही जगह लगाने के बारे में बात करेंगे? कोई जल्दी नहीं।",
        "ta": "வணக்கம் {name}! உங்கள் கணக்கில் சமீபத்தில் பெரிய தொகை வந்திருக்கிறது — வாழ்த்துக்கள்! அதை சரியாக பயன்படுத்த பேசலாமா? அவசரமில்லை.",
    },
    "dormant_high_value": {
        "en": "Hi {name}! It's been a while since we've seen activity on your account, and you have a healthy balance sitting there. Want me to show you a simple way to earn some interest on it? No worries if you're happy as is.",
        "hi": "नमस्ते {name} जी! आपके खाते में अच्छी रकम है लेकिन कुछ समय से कोई लेनदेन नहीं हुआ। FD के बारे में बताऊँ जिससे ब्याज भी मिले? अगर ऐसे ही ठीक है तो कोई बात नहीं।",
        "ta": "வணக்கம் {name}! உங்கள் கணக்கில் நல்ல தொகை இருக்கிறது ஆனால் சில காலமாக செயல்பாடு இல்லை. FD மூலம் வட்டி பெற ஒரு எளிய வழி காட்டலாமா? வேண்டாம் என்றால் பரவாயில்லை.",
    },
}

FAIL_MESSAGES = {
    "en": "This needs a quick chat with one of our relationship managers to make sure it's right for you — want me to set that up? No worries if not — just let me know if you'd rather I check back later.",
    "hi": "यह आपके लिए सही है या नहीं, यह पक्का करने के लिए हमारे relationship manager से एक छोटी बातचीत बेहतर रहेगी — क्या मैं उसे सेट कर दूं? अभी नहीं तो कोई बात नहीं — आप चाहें तो मैं बाद में चेक कर सकता हूं।",
    "ta": "இது உங்களுக்கு சரியாக இருக்கிறதா என்பதை உறுதி செய்ய எங்கள் relationship manager உடன் ஒரு சுருக்கமான உரையாடல் நல்லது — அதை ஏற்பாடு செய்யவா? வேண்டாம் என்றால் பரவாயில்லை — பிறகு பார்க்கச் சொல்லுங்கள்.",
}


class ConversationRequest(BaseModel):
    customer_name: str
    language_pref: str
    triggered_signal: str
    recommended_action: str
    suitability_check: str


class ConversationAgentResponse(BaseModel):
    message: str
    intent: str
    next_step: str
    escalate: bool


def build_system_prompt(req: ConversationRequest) -> str:
    return SARATHI_SYSTEM_PROMPT.format(
        customer_name=req.customer_name,
        language_pref=req.language_pref,
        triggered_signal=req.triggered_signal,
        recommended_action=req.recommended_action,
        suitability_check=req.suitability_check,
    )


def derive_metadata(suitability_check: str) -> tuple[str, str, bool]:
    if suitability_check.upper() == "FAIL":
        return "escalate_to_rm", "wait_for_customer", True
    return "ask_permission", "wait_for_customer", False


def demo_opening_message(req: ConversationRequest) -> str:
    lang = req.language_pref if req.language_pref in ("en", "hi", "ta") else "en"
    first_name = req.customer_name.split()[0]

    if req.suitability_check.upper() == "FAIL":
        return FAIL_MESSAGES.get(lang, FAIL_MESSAGES["en"])

    templates = DEMO_RESPONSES.get(req.triggered_signal, DEMO_RESPONSES["idle_balance_high"])
    template = templates.get(lang, templates["en"])
    return template.format(name=first_name)


def run_conversation_agent(
    req: ConversationRequest,
    llm_call=None,
) -> ConversationAgentResponse:
    """
    Generate Sarathi's opening message and structured conversation metadata.

    If llm_call is None, returns a demo-mode canned response.
    """
    intent, next_step, escalate = derive_metadata(req.suitability_check)

    if llm_call is None:
        message = demo_opening_message(req)
    else:
        system_prompt = build_system_prompt(req)
        messages = [{"role": "user", "content": OPENING_USER_PROMPT}]
        message = llm_call(system_prompt, messages)

    return ConversationAgentResponse(
        message=message,
        intent=intent,
        next_step=next_step,
        escalate=escalate,
    )
