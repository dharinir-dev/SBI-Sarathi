# 🏦 SBI Sarathi — Proactive Banking Assistant MVP

> **Signal-driven AI Banking Assistant** that detects customer financial life events, predicts product propensity, performs suitability checks, initiates personalized conversations, and intelligently escalates to Relationship Managers (RM).

---

## 📌 Overview

Traditional banking is often reactive—waiting for customers to request products—or intrusive, relying on generic cold calls.

**SBI Sarathi** is an AI-powered banking assistant that proactively identifies financial opportunities, qualifies customers using Machine Learning, ensures product suitability, initiates warm conversations, and seamlessly hands over to Relationship Managers when necessary.

---

## ✨ Features

- 🔍 Financial Signal Detection
- 🤖 Logistic Regression Propensity Model
- ✅ Product Suitability Validation
- 💬 AI-powered Conversational Banking
- 🧠 Persistent Conversation Memory
- 👨‍💼 Automatic RM Escalation
- 🌐 FastAPI REST APIs
- 📊 Next.js Dashboard

---

## 🏗️ System Architecture

```text
                 Synthetic Customer Data
                          │
                          ▼
                 Signal Detection Agent
                          │
                          ▼
              Qualification Agent (ML)
                          │
                          ▼
             Conversation Generation Agent
                          │
                          ▼
                  Orchestrator (/engage)
                          │
           ┌──────────────┴──────────────┐
           ▼                             ▼
   Conversation Memory          RM Escalation
           │                             │
           └──────────────┬──────────────┘
                          ▼
                 Next.js Dashboard
```

---

## 📂 Project Structure

```text
SBI-Sarathi/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── public/
│   └── package.json
│
├── data/
│   ├── customers.json
│   ├── transactions.json
│   └── balances.json
│
├── models/
│   └── propensity_model.pkl
│
├── memory/
│   └── conversations.db
│
├── docs/
│   ├── architecture.svg
│   └── DEPLOYMENT.md
│
├── app.py
├── generate_customers.py
├── train_propensity_model.py
├── requirements.txt
└── README.md
```

---

## 🚀 Workflow

```text
Customer Data
      │
      ▼
Signal Detection
      │
      ▼
Propensity Prediction
      │
      ▼
Suitability Check
      │
      ▼
Conversation Generation
      │
      ▼
Conversation Memory
      │
      ▼
RM Escalation (if required)
```

---

## 🛠 Tech Stack

### Backend

- FastAPI
- Python 3.10+
- SQLite
- Scikit-learn
- Pandas
- NumPy

### Frontend

- Next.js
- React
- Tailwind CSS
- TypeScript

### AI Components

- Logistic Regression
- Rule-based Signal Detection
- LLM Conversation Agent
- Conversation Memory
- Agent Orchestrator

---

## 📡 API Endpoints

### Engagement

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/engage/{customer_id}` | Runs the complete orchestration pipeline |

### Signal Detection

| Method | Endpoint |
|--------|----------|
| GET | `/signals/{customer_id}` |

### Qualification

| Method | Endpoint |
|--------|----------|
| GET | `/qualify/{customer_id}` |

### Conversation

| Method | Endpoint |
|--------|----------|
| POST | `/conversation` |
| POST | `/conversation/reply` |

### Memory

| Method | Endpoint |
|--------|----------|
| GET | `/memory/{customer_id}` |
| POST | `/memory/{customer_id}` |
| DELETE | `/memory/{customer_id}` |

### Escalation

| Method | Endpoint |
|--------|----------|
| POST | `/escalate` |

---

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/yourusername/SBI-Sarathi.git

cd SBI-Sarathi
```

### Backend

Install dependencies

```bash
pip install -r requirements.txt
```

Generate synthetic data

```bash
python generate_customers.py
```

Train the model

```bash
python train_propensity_model.py
```

Run FastAPI

```bash
python -m uvicorn app:app --reload --port 8000
```

Backend URL

```
http://localhost:8000
```

---

### Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend URL

```
http://localhost:3000
```

---

## 💬 Conversation States

```text
NEW
   │
   ▼
AWAITING_PERMISSION
   │
   ▼
PRODUCT_EXPLAINED
   │
   ▼
ONBOARDING
   │
   ▼
COMPLETED
```

Possible exit paths:

- Customer Opt-out
- RM Escalation
- Conversation Closed

---

## 📊 Sample Response

```json
{
  "customer_id": "CUST1001",
  "signal": "Salary Spike",
  "propensity_score": 0.84,
  "recommended_product": "Fixed Deposit",
  "suitability": "PASS",
  "conversation_stage": "AWAITING_PERMISSION",
  "escalated": false
}
```

---

## 🚀 Future Enhancements

- Voice Banking Assistant
- WhatsApp Integration
- Real-time Core Banking Integration
- Personalized Financial Planning
- Reinforcement Learning for Outreach
- Explainable AI Dashboard
- Multilingual Support

---

