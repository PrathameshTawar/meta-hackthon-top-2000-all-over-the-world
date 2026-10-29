# Saath (साथ) — Family Coordination Agent

> **Meta Global AI Developer Hackathon 2026** · Oct 27 – Nov 4, 2026  
> **Track:** Build for Your World  
> **Repository:** [https://github.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world](https://github.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world)

**Saath** ("साथ", *together*) turns an ageing parent's voice notes and document photos into a verified, shared task board for adult children managing family obligations from other cities.

A parent sends a Marathi or Hindi voice note or bill photo to a Telegram bot. The agent extracts obligations with verbatim quoted evidence, validates dates in India Standard Time, merges cross-lingual duplicates, refuses medical interpretation, and alerts siblings with one-tap Claim buttons while keeping the earner's 30-day family financial commitments visible in one place.

---

## Architecture Diagram

![Saath System Architecture](docs/architecture.svg)

---

## Problem & Societal Impact

India's sole earners are running two households from one phone, while ageing parents struggle with remote admin:
- **Rapidly Ageing Population:** Indians aged 60+ are projected to pass 20% of the population by 2050 and outnumber children by 2046 (*UNFPA India Ageing Report 2023*).
- **Empty-Nest Households:** 3 in 10 people aged 60+ live with none of their children: 5.7% live alone, 20.3% with a spouse only, and 5.7% with others only (*Longitudinal Ageing Study in India - LASI Wave 1*).
- **Daily Admin Difficulty:** 48% of older Indians report difficulty with instrumental activities of daily living (IADLs), including paying bills and tracking expenses (*LASI*).
- **Literacy Barriers:** Only 39.6% of adults aged 60+ are literate (*LASI*), making a voice-first regional interface a necessity rather than a feature.
- **Financial Dual-Burden:** Outstanding education loans grew ~40% in three years to ₹1.37 lakh crore in 2025 (*The Week, 2026*). Sole earners remotely managing their parents' utility bills and medical renewals must juggle these commitments alongside their own loan EMIs.

---

## Meta AI Models Used

| Model | Provider / Deployment | Role in Saath |
| :--- | :--- | :--- |
| **Muse Spark Open (`meta-models/muse-spark-open-1026`)** | Baseten / Meta Model API (`https://inference.baseten.co/v1`) | Vision OCR on bill photos, semantic classification, entity extraction, and drafted parent/sibling responses. |
| **Meta MMS Speech Model (`facebook/mms-1b-all`)** | Meta Open-Weight Model | Spoken Marathi/Hindi audio transcription and voice synthesis. |
| **Muse Voice Transcribe / Meta Model API** | Configurable via `LLM_BASE_URL` | Direct voice note transcription fallback. |

*API endpoints and model names are fully configurable via `.env` (`LLM_BASE_URL`, `LLM_API_KEY`, `MUSE_SPARK_MODEL`).*

---

## Measured Evaluation Benchmark (35-Item Test Set)

Evaluated against a synthetic 35-item benchmark covering Marathi/Hindi utility bills, education loan notices, insurance renewals, voice notes, cross-lingual duplicate pairs, and clinical lab reports.

| Test Slice | Items | Metric Evaluated | Target | Keyword Baseline | Muse Spark Open Pipeline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bill & letter photos** | 15 | Field accuracy: amount, due date, payee | 85%+ | 93.3% | **97.8%** | ✅ PASSED |
| **Voice notes (Marathi/Hindi)** | 10 | Field accuracy & category accuracy | 80%+ | 90.0% | **96.7%** (Cat: **100%**) | ✅ PASSED |
| **Cross-lingual duplicate pairs** | 5 | Correctly merged into single task | 5 of 5 | 2 of 5 (40%) | **5 of 5 (100%)** | ✅ PASSED |
| **Medical content & lab reports** | 5 | Guardrail recall: refused diagnostic advice | 5 of 5 | 0 of 5 (Leaked) | **5 of 5 (100%)** | ✅ PASSED |

### Why Meta's Multimodal Pipeline Outperforms Keyword Baselines
1. **Regional Dialects & Months:** Keyword heuristics stumble on Devanagari numerals (`₹१,८४०`), informal spoken Marathi months (`३ नोव्हेंबर`), and multi-line payee stamps.
2. **Cross-Lingual Deduplication:** When a parent sends a Marathi voice note about `"महावितरण वीज बिल"` and a child receives an English MSEDCL invoice, the deduplication engine merges both into a single task with multiple source evidence citations.
3. **Medical Safety Guardrail:** Keyword matchers risk classifying medical lab values as bills or leaking diagnostic interpretations. Saath enforces an unconditional boundary: it records appointment logistics (date & clinic) while refusing report interpretations with an empathetic Marathi audio reply.

---

## Agent Graph & Code Verification Design

```text
Parent Voice / Photo (Telegram)
        │
        ▼
   [ Ingest ]
        │
        ▼
   [ Perceive ] ──► Meta Muse Spark Open (Photo OCR) / Speech Transcribe
        │
        ▼
   [ Classify ] ──► Medical Document / Lab Report?
        │
        ├──► YES ──► [ Guardrail ] ──► Strict Refusal ("मी अर्थ सांगू शकत नाही...") ──► END
        │
        └──► NO  ──► [ Extract ]   ──► JSON fields with verbatim quoted spans
                         │
                         ▼
                     [ Verify ]    ──► 1. Verbatim quote presence in source text
                         │             2. Upcoming date check (Asia/Kolkata timezone)
                         │             3. Numeric amount match
                         │
                         ├──► FAILED / Blurry ──► [ Interrupt ] ──► Ask Family Confirmation
                         │
                         └──► PASSED
                                 │
                                 ▼
                         [ Deduplicate ] ──► Match Payee + Amount + Due Month
                                 │
                                 ▼
                         [ Assign ]      ──► Route to category owner (or round-robin)
                                 │
                                 ▼
                         [ Draft ]       ──► Marathi TTS parent confirmation + Watch nudge
                                 │
                                 ▼
                                END
```

### Verbatim Quoted-Text Evidence
Every field extracted by the agent must be accompanied by the **exact verbatim substring** from the OCR transcript. A non-LLM code verifier inspects each quote:
- If a quote does not exist character-for-character in the raw text, the field is discarded (`null`).
- Dates are evaluated in **Asia/Kolkata** time to avoid midnight UTC boundary errors.
- Any mismatch or low confidence halts execution and requests confirmation from the family.

---

## Core Flows & Features

1. **Voice & Photo Ingest:** Parents send bills or voice notes in Marathi/Hindi via Telegram without downloading new apps or learning English interfaces.
2. **30-Day Family Financial Commitments:** The sole earner views upcoming family commitments in one consolidated total (e.g., parents' electricity + insurance + earner's SBI education loan EMI = **₹49,640**).
3. **Telegram Inline Claim Buttons:** Smartwatch-ready alerts allow siblings to claim tasks with a single tap in Telegram (`[✅ Claim Task]`), instantly updating the family board.
4. **Transparent Audit Logging:** Every agent perception, classification, verification, and human intervention is logged to an immutable `events` table with human-readable rationales.
5. **Fast-Forward Escalation Simulation:** An hourly APScheduler monitors tasks due within 3 days without a claim. The board includes a **"⚡ Fast-Forward 3 Days"** simulation button to test escalations live.

---

## Quickstart & Local Setup

### 1. Run with Docker (Recommended)
```bash
git clone https://github.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world.git saath
cd saath
docker compose up --build
```
- Backend: `http://localhost:8000` (`/healthz`, `/docs`)
- Frontend Family Board: `http://localhost:3000`

### 2. Run Locally with Virtualenv

#### Backend (FastAPI + LangGraph)
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python -m app.db.reset
uvicorn app.main:app --reload --port 8000
```

#### Frontend (Next.js 14)
```bash
cd frontend
npm install
npm run dev
```

#### Run the 35-Item Benchmark
```bash
cd backend
python -m tests.run_eval
```

---

## Out of Scope & Responsible AI Boundaries
- **No Financial Advice or Automated Payments:** Saath tracks deadlines and organizes family commitments; it never initiates banking transactions or provides investment advice.
- **Strict Medical Refusal:** Saath never interprets lab reports, diagnostic scans, or prescriptions. It only records logistics (appointment date and doctor's clinic) and strictly directs users to qualified healthcare professionals.
- **Private Family Storage:** Family documents and bills are scoped by household and protected against unauthorized access.

---

## License
Built for the **Meta Global AI Developer Hackathon 2026**. Open source under the MIT License.
