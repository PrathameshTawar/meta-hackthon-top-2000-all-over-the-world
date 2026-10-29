# Saath (साथ) — Hackathon Build Plan

> **Working name:** Saath ("together")
> **Deadline:** Submit by Wed Nov 4, 6 PM IST (hard cutoff Nov 5, 7:30 AM IST)
> **Today:** Wed Oct 28 — Day 1 of 7

---

## Reality Checks (Read First)

| # | Check | Action |
|---|-------|--------|
| 1 | **Video is most of your score.** Demo (25%) + Impact (30%) are judged from the 3-min video. | Treat the video as the product. Build only what appears in it. |
| 2 | **Solo = ruthless scope cuts.** Scope creep kills solo entries. | Use the cut list at the bottom without guilt. |
| 3 | **Claim credits today.** Meta API credits need a card; Indian cards block international until you enable it. | Do this before writing any code. |
| 4 | **Verify model APIs against docs.** Confirm exact endpoints, input limits, Marathi support. | If Marathi transcription is weak, demo in Hindi instead. |

---

## Product Spec

### Users
- **Parent** — sends voice notes and photos, never touches the app directly
- **Children (1–3, different cities)** — see the shared board, claim tasks, get reminders
- **Local helper (optional)** — neighbour/relative who gets specific tasks like "collect the courier"

### Three Core Flows (build ONLY these)

| Flow | What it does |
|------|-------------|
| **Capture** | Parent sends Marathi voice note or bill photo → agent extracts obligation (what, amount, due date, payee, source) |
| **Coordinate** | Task lands on family board with evidence → auto-assigned by category → siblings notified → duplicates merged |
| **Close the loop** | Agent drafts: Marathi reply to parent, sibling notification, call script if needed. Escalates if deadline near and nobody claimed. |

### Out of Scope (state this in README)
- Payments
- Actual phone calling
- Medical interpretation
- Real bank integration

---

## Architecture

```
Parent
  │  voice note / photo
  ▼
Telegram Bot  ──────────────────────────────────────────────────────────►
  │                                                                      │
  ▼                                                                      ▼
FastAPI  ──►  LangGraph Agent  ──►  PostgreSQL              React Board (Vercel)
               │                                              (siblings view)
               ├── Muse Voice Transcribe  (voice → text)
               └── Muse Spark            (image → text, classify, extract, draft)
```

**Tech choices:**
- **Telegram bot** — native voice + photo, 10-min setup. No approval wait (vs WhatsApp Business API).
- **FastAPI + LangGraph + PostgreSQL** — no Redis needed.
- **Next.js on Vercel** — fastest path to a public shareable URL.
- **Hosting:** Railway / Render / Modal with credits.

### Database Tables

```sql
households  (id, name, primary_language)
members     (id, household_id, name, role, telegram_id, categories_owned[])
artifacts   (id, household_id, type, file_url, raw_text, received_at)
tasks       (id, household_id, category, title, amount, due_date, payee,
             status, assignee_id, confidence, dedupe_key, recurrence)
evidence    (id, task_id, artifact_id, quoted_span, field_name)
events      (id, task_id, actor, action, payload, created_at)  -- audit log
```

---

## Agent Graph (LangGraph)

```
Ingest ──► Perceive ──► Classify ──► [Medical?] ──► Guardrail Reply
                                         │
                                         ▼
                                      Extract ──► Verify ──► [Low confidence?] ──► Interrupt (ask family)
                                                               │
                                                               ▼
                                                           Deduplicate ──► Assign ──► Draft Actions
```

| Node | What it does |
|------|-------------|
| **Ingest** | Save raw artifact to DB |
| **Perceive** | Transcribe voice (Muse Voice Transcribe) OR OCR+doctype from image (Muse Spark) |
| **Classify** | Category: bill / loan EMI / pension / govt letter / insurance / appointment / medical / chit-chat |
| **Guardrail** | Medical content → log only logistics (date, place, transport), send fixed refusal reply. Never summarise results or medicines. |
| **Extract** | Pull fields as structured JSON. Every field must include the **exact quoted text** it came from, or field = null. |
| **Verify** | Code-based checks (not LLM): quoted text exists in source, date is valid + future, amount matches quote. Fail or low confidence → `interrupt()` |
| **Deduplicate** | Match on payee + amount + due-date window. Same bill twice → one task, two evidence rows. |
| **Assign** | By category owner. No owner → round-robin. |
| **Draft Actions** | Marathi reply to parent, sibling notification, call script (if needed) |

> **The quoted-text rule + code-based verification = your Technical Depth story.**

### Escalation Scheduler
- Cron job runs hourly
- Deadline ≤ 3 days + task unclaimed → ping all siblings

---

## Evaluation Set (35 items)

| Type | Count |
|------|-------|
| Bill / letter photos | 15 |
| Voice notes | 10 |
| Duplicate pairs | 5 |
| Medical content items | 5 (lab reports, prescriptions) |

**Metrics to report:**
- Field accuracy (amount, due date, payee)
- Category accuracy
- Duplicate detection rate
- Guardrail recall — must be **5/5**

Show as a table in README and ~10 seconds in the video.

---

## Day-by-Day Plan

### Day 1 — Wed Oct 28 (Today): Setup + Risky Parts First
- [ ] Enable international transactions on your card
- [ ] Claim Meta API credits
- [ ] Create GitHub repo (public) + first commit
- [ ] Test Muse Voice Transcribe on 1 Marathi + 1 Hindi voice note
- [ ] Test Muse Spark on 1 bill photo
- [ ] Watch Agents 102 at 9:30 PM IST
- **Done when:** Both models return usable output; you know which language to demo in

### Day 2 — Thu Oct 29: Capture Pipeline
- [ ] Set up Telegram bot (BotFather, get token)
- [ ] Build: received message → perceive → extract → JSON → Postgres row with quoted evidence
- [ ] Start collecting eval set (photograph bills with account numbers covered)
- **Done when:** Sending a bill photo to the bot creates a DB row with quoted evidence

### Day 3 — Fri Oct 30: Agent Graph
- [ ] Build: verify node (code checks), confirmation interrupt, deduplication, assignment
- [ ] Build: medical guardrail node
- [ ] Fireworks session 9:30 PM IST (skip if behind)
- **Done when:** Duplicate merges ✓, blurry bill triggers confirmation ✓, lab report gets refusal ✓

### Day 4 — Sat Oct 31: Family Board
- [ ] Build board columns (New → Claimed → Done)
- [ ] Build task cards with evidence panel (click field → see highlighted quote + image)
- [ ] Build member view
- [ ] Deploy backend + frontend publicly
- **Done when:** A sibling can open a link and claim a task

### Day 5 — Sun Nov 1: Close the Loop
- [ ] Build drafted actions (Marathi reply, sibling notification, call script)
- [ ] Build escalation scheduler
- [ ] Build audit log view
- **Done when:** Full flow works end-to-end — parent voice note → parent receives Marathi reply

### Day 6 — Mon Nov 2: Evaluation + Hardening
- [ ] Run full 35-item eval set
- [ ] Fix worst failures
- [ ] Write results table
- [ ] Handle error cases (unreadable image, silent audio, unknown sender)
- [ ] **Feature freeze tonight**

### Day 7 — Tue Nov 3: Video + README
- [ ] Write script (see below)
- [ ] Record each scene separately
- [ ] Edit — re-record flaky scenes rather than hoping live demo works
- [ ] Write README

### Day 8 — Wed Nov 4: Submit
- [ ] Final checks, repo public, video uploaded
- [ ] Submit by 6 PM IST (don't use the Nov 5 buffer)

---

## Video Script (3:00)

| Time | Scene |
|------|-------|
| 0:00–0:20 | **Hook.** "My parents live in Pune. Their kids live in three other cities. Here's what managing their bills, pensions, and appointments looks like today." Show messy family WhatsApp thread. |
| 0:20–0:50 | **Capture.** Parent sends Marathi voice note about electricity bill + photo of insurance renewal. Show bot's Marathi reply. |
| 0:50–1:30 | **Coordinate.** Board updates live, task auto-assigned. Click field → see quoted evidence highlighted. Duplicate photo arrives → merges. |
| 1:30–1:55 | **Verification.** Blurry bill → agent asks for confirmation. Lab report → agent declines interpretation. Say: "It handles logistics, never medical advice." |
| 1:55–2:20 | **Escalation.** Fast-forward clock, nobody claimed → all siblings pinged. Sibling's phone buzzes. |
| 2:20–2:45 | **How it works.** Architecture diagram → evaluation table → name the Meta models used. |
| 2:45–3:00 | **Impact.** "Millions of families in India live this split." [cite real statistic] Close. |

> **Before recording:** Look up a real statistic on internal migration or elderly people living apart from children. Cite the source in the README.

---

## README Structure (checklist)

- [ ] Problem statement
- [ ] Demo GIF
- [ ] Architecture diagram
- [ ] Which Meta models are used where
- [ ] Agent graph diagram
- [ ] Verification design (the quoted-text rule)
- [ ] Evaluation results table
- [ ] Guardrail policy
- [ ] What was built during the event (required by rules)
- [ ] Setup steps
- [ ] Limitations

---

## Cut List (cut in this order if behind)

| Cut | Safe to cut? |
|-----|-------------|
| Local helper role | ✅ Yes |
| Call scripts | ✅ Yes — keep only Marathi reply + sibling notification |
| Recurring task detection | ✅ Yes |
| Escalation scheduler | ✅ Yes — fake it with "simulate 3 days later" button |
| **Quoted-text evidence** | ❌ Never cut |
| **Confirmation pause (interrupt)** | ❌ Never cut |
| **Medical guardrail** | ❌ Never cut |
| **Evaluation table** | ❌ Never cut |
