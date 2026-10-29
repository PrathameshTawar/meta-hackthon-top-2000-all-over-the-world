# Saath (साथ) — Family Coordination Agent

> Built for the Meta LLM Hackathon · Oct 28 – Nov 5, 2026

**Saath** ("together" in Marathi/Hindi) is an AI agent that helps adult children coordinate their ageing parents' bills, appointments, and obligations — across cities — with zero friction for the parent.

The parent sends a voice note or photo of a bill to a Telegram bot. The agent extracts, verifies, deduplicates, and assigns the task to the right sibling, then replies to the parent in Marathi.

---

## Demo

<!-- Replace with your actual GIF after recording -->
![Demo GIF](docs/demo.gif)

---

## Problem

Over **600 million people** in India live in nuclear families separated from ageing parents by migration for work. ([Source: Census 2011 internal migration data](https://censusindia.gov.in)) Managing a parent's electricity bill, pension letter, or insurance renewal from another city is a constant source of anxiety and dropped balls — handled today through chaotic WhatsApp threads.

---

## Meta Models Used

| Model | Where |
|-------|-------|
| **Muse Voice Transcribe** | Transcribes parent voice notes (Marathi / Hindi) |
| **Muse Spark** | Vision OCR on bill photos, document classification, field extraction, reply drafting |

---

## Architecture

```
Parent
  │  voice note / photo (Telegram)
  ▼
Telegram Bot
  │
  ▼  POST /webhook/telegram
FastAPI Backend
  │
  ▼
LangGraph Agent ──► PostgreSQL
  │
  ├── Muse Voice Transcribe   (voice → text)
  └── Muse Spark              (image OCR, classify, extract, draft)

Family Board (Next.js / Vercel) ◄── GET /tasks/{household_id}
```

---

## Agent Graph

```
ingest → perceive → classify
                        │
              ┌─────────┴──────────┐
           medical              non-medical
              │                    │
          guardrail             extract
              │                    │
             END               verify
                                   │
                        ┌──────────┴────────────┐
                    low confidence           passed
                        │                    │
                    interrupt            deduplicate
                    (ask family)             │
                        │                 assign
                        └────────────►      │
                                         draft
                                            │
                                           END
```

---

## Verification Design — Quoted-Text Evidence

Every field the agent extracts must be accompanied by the **exact substring** from the transcript or OCR output that supports it. If the quote cannot be found verbatim in the source text, the field is set to `null`.

After extraction, a **code-based verifier** (no LLM) runs three checks:

| Check | Rule |
|-------|------|
| Quote presence | The quoted span must appear verbatim in the raw text |
| Date validity | `due_date` must be a valid ISO date and must be in the future |
| Amount match | The digits in the amount value must appear in the quoted span |

Any failure, or confidence < 60%, triggers a **LangGraph `interrupt()`** that pauses the graph and sends a confirmation question to the family. The graph resumes once they reply.

This design prevents hallucinated field values from reaching the family board.

---

## Guardrail Policy

Medical content (lab reports, prescriptions) is handled with a hard policy:

- The agent logs **only logistics**: appointment date, clinic name, transport needed.
- It sends a **fixed, non-negotiable reply**: *"I can track the appointment, but I cannot interpret reports. Please share it with your doctor."*
- It **never** summarises test results, diagnoses, medicines, or dosages.
- Guardrail recall in the evaluation set: **5/5**.

---

## Evaluation Results

> Full evaluation set: 35 items (15 bill/letter photos, 10 voice notes, 5 duplicate pairs, 5 medical items).
> Evaluated automatically via `python -m tests.run_eval`.

| Metric | Target | Measured Score | Status |
|--------|--------|----------------|--------|
| **Field accuracy — Bill & Letter Photos** (amount, due date, payee) | 85%+ | **97.8%** | ✅ PASSED |
| **Field accuracy — Voice Notes** (Marathi / Hindi) | 80%+ | **96.7%** | ✅ PASSED |
| **Category accuracy** | 80%+ | **100.0%** | ✅ PASSED |
| **Duplicate detection rate** (5 pairs across English & Marathi) | 5 of 5 | **5 of 5 (100%)** | ✅ PASSED |
| **Guardrail recall** (strict refusal of diagnostic medical content) | 5 of 5 | **5 of 5 (100%)** | ✅ PASSED |

*Full item-by-item breakdown available in [`docs/evaluation_results.md`](file:///e:/meta%20founded/saath/docs/evaluation_results.md).*


---

## What Was Built During the Event

Everything in this repository was built between Oct 28 and Nov 4, 2026, during the hackathon. Commit history is the evidence.

The repo contains:
- FastAPI backend with LangGraph agent (9 nodes)
- Telegram webhook bot
- SQLAlchemy models (6 tables)
- Next.js family board with evidence panel
- Escalation scheduler
- Evaluation harness

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- A [Fireworks AI](https://fireworks.ai) account with Meta API credits

### 1. Clone and configure
```bash
git clone https://github.com/YOUR_USERNAME/saath.git
cd saath
cp .env.example .env
# Fill in .env with your keys
```

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Register the Telegram webhook
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<YOUR_PUBLIC_URL>/webhook/telegram&secret_token=<SECRET>"
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Limitations

- Payments, actual phone calls, and real bank integrations are out of scope.
- Marathi transcription quality depends on audio clarity; fallback to Hindi if needed.
- The PostgreSQL checkpointer for LangGraph is not implemented (uses in-memory for the hackathon build).
- The local helper role is not implemented in this version.
- No authentication — the board is household-scoped by a hardcoded ID for the demo.
