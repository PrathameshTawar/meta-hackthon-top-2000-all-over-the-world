# Saath: Fix Plan for Claude Code

Paste this whole file into Claude Code at the repo root (or save it as `FIXES.md` and say: "Work through FIXES.md").

## Ground rules (read before starting)

1. Work through the tasks **in order**. Finish one task completely before starting the next.
2. For every task: **write the failing test first**, run it to confirm it fails, then fix the code, then run the full suite with `cd backend && pytest -q`. Do not move on with any test failing.
3. Make **one git commit per task**, with a message like `fix(P0-1): stop graph on failed perception`.
4. Change **only** what the task describes. No drive-by refactors, renames, or reformatting of unrelated code.
5. Follow the existing patterns in `backend/tests/test_agent_pipeline.py`: `@pytest.mark.asyncio` tests that build an `AgentState` dict and call node functions directly. Use unique `household_id` / phone numbers / artifact IDs per test so tests don't collide on the shared SQLite file.
6. Tests must not call any external API. Monkeypatch `app.agent.nodes._call_llm`, `_transcribe_audio_muse`, and the `_send_whatsapp_message` / `_send_telegram_message` / `notify` helpers wherever a code path would hit the network.
7. If a task conflicts with the existing code in a way this file doesn't anticipate, **stop and report** what you found instead of guessing.
8. After all tasks, do the "Final checklist" at the bottom.

## Repo map (relevant files)

- `backend/app/agent/graph.py`: LangGraph wiring, interrupt node, checkpointer
- `backend/app/agent/nodes.py`: all agent nodes, keyword lists, `_heuristic_extract`, `_call_llm`
- `backend/app/agent/state.py`: `AgentState`
- `backend/app/api/webhooks.py`: Telegram + WhatsApp webhooks, `_run_agent`, `notify`, claim/done/confirm handlers
- `backend/app/api/tasks.py`: web board task API
- `backend/app/scheduler/escalation.py`: hourly escalation job
- `backend/app/db/session.py`, `backend/app/db/models.py`: DB engine and models
- `backend/tests/run_eval.py`, `backend/tests/eval_set/eval_items.json`: evaluation harness

---

# P0: Demo-breaking bugs

## P0-1. Stop the graph when perception or extraction fails

**Files:** `graph.py`

**Problem:** When `node_perceive` returns empty `raw_text` (failed transcription or photo reading), the graph still runs classify → extract → verify. With nothing extracted, confidence is 0, verify triggers an interrupt with an empty failure list, and a sibling is asked to confirm nothing. Tapping "Correct" creates a blank task. Same when `node_extract` returns `extracted={}` (unparseable model output).

**Fix:** Replace the two plain edges with conditional edges.

```python
def route_after_perceive(state: AgentState) -> str:
    return "classify" if state.get("raw_text") else END

def route_after_extract(state: AgentState) -> str:
    return "verify" if state.get("extracted") else END

# replace graph.add_edge("perceive", "classify") and graph.add_edge("extract", "verify") with:
graph.add_conditional_edges("perceive", route_after_perceive, {"classify": "classify", END: END})
graph.add_conditional_edges("extract", route_after_extract, {"verify": "verify", END: END})
```

`_run_agent` already sends `parent_reply` from the final state, so the parent gets the existing "please resend" message.

**Tests:**
- Run the compiled graph (with a temporary checkpointer DB path) on an artifact whose perception yields empty text: assert no interrupt occurs, no `Task` row is created, and the final state contains the perceive node's `parent_reply`.
- Same for extraction returning `{}` (monkeypatch `_call_llm` to return `"not json"` with an API key set via monkeypatching `settings.get_api_key`).

## P0-2. Show what is being confirmed in the confirmation question

**Files:** `nodes.py` → `node_verify`; `webhooks.py` → `_run_agent`

**Problem:** The interrupt question sent to the sibling is "काही माहिती अस्पष्ट आहे" plus raw verifier strings such as `amount digits 1840 not in quote ...`, and it is truncated to 60 characters for the WhatsApp template. The sibling never sees the payee, amount, or due date they're being asked to confirm.

**Fix:**
1. Add a helper in `nodes.py`:
   ```python
   def _confirmation_question(extracted: dict) -> str:
       def v(k):
           return ((extracted.get(k) or {}).get("value")) or "?"
       summary = f"{v('payee')} | {v('amount')} | due {str(v('due_date'))[:10]}"
       return f"Please check: {summary}. Is this right?"
   ```
2. Add a helper that turns verifier failures into plain English for humans, for example: missing quote → "couldn't find {field} on the document"; past date → "the due date {date} has already passed"; amount mismatch → "the amount doesn't match the document".
3. In `node_verify`, set `confirmation_question` to `_confirmation_question(extracted)` and store the plain-English reasons in a new state key `confirmation_reasons: list[str]` (add it to `AgentState`). Keep `verify_failures` unchanged for the audit log.
4. In `_run_agent`, the template parameter stays the short `confirmation_question` (it must fit 60 chars; keep `_clean_template_param`). The interactive/Telegram message body should be the question plus the plain-English reasons as bullet lines. Read `confirmation_reasons` from the latest state via `await graph.aget_state(config)` rather than from the stream chunk.

**Tests:**
- `node_verify` with an amount mismatch → `confirmation_question` contains the payee and amount values, is ≤ 60 characters for realistic values, and `confirmation_reasons` contains no raw strings like "digits" or "quote".

## P0-3. Make escalation actually fire

**Files:** `scheduler/escalation.py` → `run_escalation`

**Problem:** The query requires `Task.assignee_id.is_(None)`, but `node_assign` always sets an assignee (category owner, else `children[0]`). Agent-created tasks are therefore never escalated; the "Skip 3 days" demo only works on seeded rows. The auto-assigned child is a suggestion, not a claim.

**Fix:** Escalate on status, not on assignee:

```python
select(Task).where(
    Task.due_date <= threshold_naive,
    Task.status.in_([TaskStatus.new, TaskStatus.confirmed, TaskStatus.needs_review]),
)
```

Claimed, done, and already-escalated tasks are excluded by status, so the job stays idempotent. Also wrap `task.title` in `_clean_template_param` (import it from `app.api.webhooks`) in the template params.

**Tests:**
- Create a task with an assignee, status `confirmed`, due in 2 days → `run_escalation()` returns its ID and its status becomes `escalated` (monkeypatch `notify`).
- Run `run_escalation()` again → the same task is not returned.
- A `claimed` task due tomorrow is not escalated.

## P0-4. Don't re-alert siblings when a duplicate is merged

**Files:** `nodes.py` → `node_draft`

**Problem:** When `node_deduplicate` finds an existing task, `node_draft` still produces a `sibling_notification` and `task_id` is set, so siblings get a second "new family task" alert for the same bill. This breaks the cross-lingual merge demo.

**Fix:** In `node_draft`, if `state.get("existing_task_id")`:
- return `sibling_notification = ""` and `call_script = None`;
- set `parent_reply` to a short Marathi note that this bill is already recorded, for example: `"हे बिल आधीच नोंदवले आहे. काळजी करू नका, आम्ही लक्ष ठेवत आहोत. 🙏"`.

**Tests:**
- `node_draft` with `existing_task_id=5` → `sibling_notification == ""` and the parent reply is the "already recorded" message.

## P0-5. Serialize agent runs per household (fixes the dedup race)

**Files:** `webhooks.py` → `_run_agent`, and every place that calls `graph.astream(Command(resume=...))` (Telegram and WhatsApp confirm_yes / confirm_no handlers)

**Problem:** Dedupe reads in one DB session and assign inserts in another node. If two parents send the same bill seconds apart, both runs pass the dedupe check before either inserts, creating two tasks.

**Fix:**

```python
from collections import defaultdict
_household_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
```

Wrap each graph run (initial run and every resume) in `async with _household_locks[household_id]:`. Only the graph execution needs to be inside the lock; sending notifications afterward can be outside it. Add a code comment noting that multi-process deployments need a DB-level constraint instead.

**Tests:**
- Use `asyncio.gather` to run `_run_agent` twice concurrently for the same household with two text artifacts describing the same bill (one in Marathi, one in English, with `_call_llm` monkeypatched to return deterministic extractions that produce the same dedupe key). Assert exactly one open `Task` exists afterward.

## P0-6. Make claim and done idempotent, and share the logic across channels

**Files:** new `backend/app/services/tasks.py` (create the `services` package); `webhooks.py` (Telegram callbacks around the `claim:` / `done:` handlers and the WhatsApp equivalents); `api/tasks.py` → `update_task`

**Problem:**
- A second tap on "Mark Done" is a new message (message-ID idempotency doesn't catch it). It re-notifies parents and, for `loan_emi`, creates a second next-month recurring task.
- "Claim" silently takes over a task another sibling already claimed.
- Web `PATCH /tasks/{id}` → done does not create the next recurring task, so channels behave differently.

**Fix:** Create two functions and call them from all three channels (Telegram, WhatsApp, web):

```python
class ClaimResult(enum.Enum): ok = "ok"; already_yours = "already_yours"; taken = "taken"; done = "done"; not_found = "not_found"
class DoneResult(enum.Enum): ok = "ok"; already_done = "already_done"; not_found = "not_found"

async def claim_task(task_id: int, member: Member) -> tuple[ClaimResult, Task | None]: ...
async def complete_task(task_id: int, actor_name: str, household_id: int | None) -> tuple[DoneResult, Task | None]: ...
```

Rules:
- `claim_task`: not found or different household → `not_found`; status `done` → `done`; status `claimed` with a different assignee → `taken`; same assignee → `already_yours`; otherwise set `claimed`, assignee, `updated_at`, write an `Event`, return `ok`.
- `complete_task`: status already `done` → `already_done` (no notifications, no recurrence); otherwise set `done`, create the next monthly task when `recurrence == "monthly"` and `due_date` is set (keep the existing +30 days logic), write an `Event`, return `ok`. Only the `ok` path calls `notify_parents_task_done`.
- Channel handlers send a short reply for each non-ok result (for example "Already claimed by another sibling", "Already marked done").
- The web `update_task` uses `complete_task` when status becomes `done` and `claim_task` semantics are not required there (it may keep setting `assignee_id` directly), but it must use `complete_task` so recurrence and notifications match.

**Tests:**
- `complete_task` twice on a monthly EMI task → exactly one new recurring task, and `notify_parents_task_done` (monkeypatched) is called once.
- `claim_task` by sibling B on a task claimed by sibling A → `taken`, assignee unchanged.
- Web `PATCH` to done on a monthly task creates the next task (use FastAPI `TestClient` or call the function directly).

## P0-7. Route status questions away from task creation

**Files:** `nodes.py` → `node_classify`; `graph.py`; new node `node_status`

**Problem:** A voice note asking "काय बाकी आहे?" is classified as `appointment`, then extracted and saved as a junk appointment task. (The WhatsApp text path handles status queries before the graph, but voice notes go through the graph.)

**Fix:**
1. In `node_classify`, when the status-question check matches, return `{"category": "status_query"}` (a plain string; do not add it to the `TaskCategory` enum, since it is never persisted).
2. Move the pending-tasks reply builder from the WhatsApp text path in `webhooks.py` into a reusable function (for example `build_pending_tasks_reply(household_id) -> str` in `app/services/tasks.py`) and use it in both places.
3. Add `node_status` that returns `{"parent_reply": await build_pending_tasks_reply(state["household_id"]), "sibling_notification": ""}`.
4. In `route_after_classify`, route `"status_query"` → `"status"`; add `graph.add_edge("status", END)`.

**Tests:**
- Graph run on raw text "काय बाकी आहे?" → no new `Task`, `parent_reply` starts with the pending-tasks header (or the "no pending tasks" message).

## P0-8. Fix the medical guardrail's false refusals and Hindi gap

**Files:** `nodes.py` → `MEDICAL_KEYWORDS`, `node_classify`, `node_perceive` (doc-type inference), `node_guardrail`, `node_draft`

**Problem (verified):**

| Input | Should be | Currently |
|---|---|---|
| "अपोलो फार्मसी औषध बिल रक्कम ₹2,340 देय 15 नोव्हेंबर" | tracked as bill | refused as medical |
| "Dr Lal PathLabs Invoice Amount Rs 1,200 due 20 Nov 2026" | tracked as bill | refused as medical |
| "Sahyadri Hospital final bill, see discharge summary. Amount payable Rs 45,000" | tracked as bill | refused as medical |
| "डॉक्टर ने दवाई लिखी है, रोज़ दो गोली सुबह शाम" | refused | not caught by keywords |

Also: `node_perceive` uses the substring `"rx"` for doc-type inference (false matches), and `node_guardrail` saves the logistics task with `status=TaskStatus.done`, so the family never sees the appointment.

**Fix:**
1. Add Hindi terms and bill signals:
   ```python
   HINDI_MEDICAL = ["दवाई", "दवा", "गोली", "पर्चा", "जांच रिपोर्ट", "खुराक", "ब्लड रिपोर्ट"]
   BILL_SIGNALS = ["bill", "invoice", "amount payable", "total amount", "बिल", "रक्कम", "देय", "राशि", "भुगतान"]
   AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s*[\d०-९,]+", re.I)
   ```
2. In `node_classify` (keep the existing MGL check first):
   ```python
   diagnostic = (any(k in text_lower for k in MEDICAL_KEYWORDS + HINDI_MEDICAL)
                 or doc_type in ("prescription", "lab_report")
                 or re.search(r"\b\d+\s?mg\b", text_lower))
   has_bill = any(s in text_lower for s in BILL_SIGNALS) and AMOUNT_RE.search(raw_text)
   if diagnostic and has_bill:
       category = TaskCategory.bill
       medical_context = True     # return this in the state update
   elif diagnostic:
       category = TaskCategory.medical
   ```
   Add `medical_context: bool` to `AgentState`.
3. In `node_draft`, when `medical_context` is true, append the existing `GUARDRAIL_REPLY` sentence about not interpreting reports to the parent reply.
4. In `node_perceive`, remove `"rx"` from the prescription keyword list (keep "prescription", "dosage", "गोळ्या", "औषध"), and add the Hindi terms to the doc-type inference.
5. In `node_guardrail`: if no date is found, do **not** create a task (still send `GUARDRAIL_REPLY`). If a date is found, save the logistics task with `status=TaskStatus.confirmed`, not `done`. Also detect Marathi and English month-name dates by reusing the date logic from `_heuristic_extract` (factor it into a small `_find_date(raw_text) -> tuple[value, quote] | None` helper used by both).

**Tests:** One test per table row above (expected categories: bill, bill, bill, medical), plus:
- Pharmacy bill draft includes the "cannot interpret reports" sentence.
- Guardrail on a prescription with no date creates no task; with "10 नोव्हेंबर 2026" creates a `confirmed` task.
- Keep the existing MGL and "500 mg" tests passing.

---

# P1: Correctness bugs that contradict the README

## P1-9. Fix Devanagari amounts and normalize quote checks

**Files:** `nodes.py` → `node_extract` (quote check), `node_verify` (checks 1 and 3)

**Problem (verified):**
- Python's `\d` keeps Devanagari digits, so check 3 compares `"1840"` with `"१८४०"` and fails. The README claims ₹१,८४० matches ₹1,840; it currently doesn't.
- Check 3 uses a substring test, so an extracted ₹184 passes against a quote of ₹1,840.
- Quote checks are exact, so a double space or Unicode composition difference nulls a correct field.

**Fix:** Add near the top of `nodes.py`:

```python
import unicodedata
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"))

def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(ZW)
    return re.sub(r"\s+", " ", s).strip()

def to_amount(s) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", norm(str(s)).translate(DEV_DIGITS))
    return float(m.group().replace(",", "")) if m else None
```

- Quote presence (both in `node_extract` and verify check 1): `norm(quote) in norm(raw_text)`.
- Verify check 3: fail when `to_amount(value) != to_amount(quote)` (also fail if either is `None`).
- In `node_assign`, the evidence-saving condition `quote in raw_text` must use the same `norm()` comparison.
- Do **not** loosen wording matches; only normalize encoding and whitespace.

**Tests:**
- value `₹1,840`, quote `₹१,८४०` → passes.
- value `₹184`, quote `₹1,840` → fails.
- quote with a double space vs single space in source → passes.

## P1-10. Stop grounding the generated title

**Files:** `nodes.py` → `node_extract`, `node_verify`

**Problem:** The prompt asks for a "concise task title" with a verbatim quote. Titles are summaries and almost never verbatim, so they get nulled, confidence drops, and tasks fall back to "Bill Task".

**Fix:** Exclude `title` from quote checks in `node_extract` and `node_verify`, and from the confidence denominator. Confidence = grounded fields among `amount`, `due_date`, `payee` (and `consumer_number` once P1-11 adds it, counted only when present). Update the prompt to say the title does not need a quote.

**Tests:** An extraction with a non-verbatim title and grounded other fields keeps its title and passes verification.

## P1-11. Make dedup keys robust

**Files:** `nodes.py` → `node_extract` prompt, `node_deduplicate`

**Problem:**
- `"lic" in payee_lower` matches "policy" and "public".
- Without a due date the key is `payee|amount|`, merging different months.
- No consumer/policy number, so two policies with the same premium merge.

**Fix:**
1. Add `consumer_number` (consumer / account / policy / loan number) to the extraction prompt and JSON schema, grounded with a quote like other fields.
2. Payee normalization: build a canonical map from `KNOWN_PAYEES` and match whole words (`re.search(rf"\b{re.escape(needle.lower())}\b", payee_lower)`) for Latin-script needles; plain `in` is fine for Devanagari needles. Remove the hand-written substring chain.
3. Key:
   - If `consumer_number` present: `cn|{canonical_payee}|{digits_only(consumer_number)}|{due_month}`.
   - Else if `due_month` present: `fb|{canonical_payee}|{int(to_amount(amount) or 0)}|{due_month}`.
   - Else: return `{"existing_task_id": None, "dedupe_key": None}` (no dedup; P1-12 makes such tasks `needs_review`).

**Tests:**
- "New India Assurance policy" does not normalize to LIC.
- Two tasks, same payee and amount, different consumer numbers → not merged.
- Missing due date → `dedupe_key is None`.
- Existing cross-lingual MSEDCL pair still merges.

## P1-12. Make the README's claims true

**Files:** `nodes.py` → `node_extract`, `node_assign`; `README.md`

**Problem:**
- README: "Without LLM_API_KEY, extraction falls back to the keyword rules." Code returns `{}` and never calls `_heuristic_extract`.
- README: "Route to category owner (or round-robin)." Code always picks `children[0]`.
- README: "drafts Marathi replies" with Muse Spark. Replies are fixed templates.

**Fix:**
- In `node_extract`, when there is no API key, use `_heuristic_extract(raw_text)` and log the event with `payload["mode"] = "keyword_fallback"`. When the key is set, log `mode = "muse_spark"`.
- In `node_assign`, if no category owner matches, pick the child with the fewest open tasks (status not `done`), breaking ties by member ID. If `dedupe_key` is `None` (see P1-11), save the new task as `needs_review`.
- In `README.md`, change the drafting claim to say replies use fixed, reviewed Marathi templates filled with verified fields (a deliberate safety choice), and keep the other two claims (now true).

**Tests:** No-key extraction returns heuristic fields; round-robin assigns to the child with fewer open tasks.

## P1-13. Smaller crashes and edge cases

**Files:** `nodes.py`, `webhooks.py`, `requirements.txt`

1. **Classify crash on empty model output.** `llm_cat.strip().lower().split()[0]` raises `IndexError` on whitespace. Replace with:
   ```python
   parts = (llm_cat or "").strip().lower().split()
   cat_cleaned = parts[0].strip(".:'\"") if parts else ""
   ```
2. **PDF bills ignored.** In `process_single_whatsapp_message`, handle `msg_type == "document"` when `msg["document"]["mime_type"] == "application/pdf"`: create an `image` artifact with `file_url=f"whatsapp-pdf://{media_id}"`. In `node_perceive`, for that prefix, download like WhatsApp media, render page 1 to PNG with `pypdfium2` (scale ≈ 2), and continue with the existing image path. Add `pypdfium2` to `requirements.txt`.
3. **Image preprocessing.** In `node_perceive`, before base64-encoding: open with Pillow, apply `ImageOps.exif_transpose`, convert to RGB, resize so the long edge is at most 1600 px, re-encode as JPEG quality 85, and send `data:image/jpeg;base64,...`. Add `Pillow` to `requirements.txt`. Wrap in try/except and fall back to the original bytes.
4. **Parent-facing reply formatting** (`node_draft`):
   - Format due dates as Marathi day + month name (reuse `MARATHI_MONTHS` inverted) instead of ISO strings.
   - Use a Marathi title per category (वीज बिल, कर्जाचा हप्ता, विम्याचा हप्ता, पेन्शन, सरकारी पत्र, अपॉइंटमेंट) instead of the English title in the parent reply. Siblings still get the English title.
   - If the household's `primary_language` is `hi`, use Hindi equivalents for the reply strings.
5. **One shared LLM client.** In `nodes.py`, create the `AsyncOpenAI` client once (lazily, module-level) with `max_retries=2`, instead of per call. Measure each `_call_llm` and ASR call's latency with `time.perf_counter()` and include `latency_ms` and `model` in the corresponding `_log_event` payloads.

**Tests:** Empty-string LLM output doesn't crash classify; the draft for a due date of `2026-11-10` contains "नोव्हेंबर" and not "2026-11-10"; image preprocessing returns bytes ≤ original size for a large test image generated in memory.

---

# P2: Evaluation

## P2-14. Add a held-out eval set that the keyword rules were not written against

**Files:** `tests/eval_set/`, `tests/run_eval.py`, `docs/evaluation_results.md`, `README.md`

**Problem:** `KNOWN_PAYEES` in `nodes.py` contains the exact payees used in `eval_items.json` (for example "Suyash Co-op Housing Society", Sahyadri, Tata Power). The keyword baseline's 97.8% therefore measures the test, not the method.

**Fix:**
1. Create `tests/eval_set/holdout_items.json` with the same schema (`id`, `slice`, `type`, `raw_text`, `expected`). Use payees, formats, and phrasings that appear **nowhere** in `nodes.py`: other utilities (for example BEST, Adani Electricity, Jio, BSNL), other banks and insurers, mixed Hindi-Marathi text, bills with both "previous dues" and "current amount", "due date" vs "disconnection date", rotated-OCR-style noise, and the four guardrail cases from P0-8 plus at least four more "medical-sounding but must be tracked" bills. Leave placeholders (clearly marked `"TODO_REAL_PHOTO"`) for real photos and voice notes that will be added by hand.
2. In `run_eval.py`, add `--set {regression,holdout}` (default `regression`) and report both sets in separate tables. Label the existing 40 items as the **regression set**.
3. Add a guardrail **false-refusal rate** next to refusal recall.
4. Before writing, add a check that fails loudly if any holdout payee string appears in `nodes.py`.

## P2-15. Make the eval reproducible and side-effect free

**Files:** `tests/run_eval.py`

1. Point the eval at a temporary SQLite file: set `os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmpdir}/eval.db"` and `CHECKPOINTS_DB_PATH` **before** importing `app.*` modules.
2. Add `--live`: run items with `file_path` (real photos/audio) through `node_perceive` too, not just typed text.
3. Cache every model response to `tests/eval_set/cache/{sha256(prompt or input bytes)}.json`; on rerun, use the cache. Add `--refresh-cache` to bypass it. Commit the cache directory so judges can reproduce results without an API key.
4. Report median and p95 latency per slice for live runs.

---

# P3: Security and infrastructure

## P3-16. Protect the web task API

**Files:** `api/tasks.py`, `frontend/src/lib/api.ts`

**Problem:** `GET /tasks/{household_id}` and `PATCH /tasks/{id}` have no auth, so anyone can read or change any household's tasks. Invalid `status` values raise a 500.

**Fix:**
- Add a dependency that requires the `X-Admin-Token` header (or whichever header `frontend/src/lib/api.ts` already sends for admin routes; reuse it) to equal `settings.admin_secret`; apply it to every route in `tasks.py`.
- In `PATCH`, verify the task's `household_id` matches a `household_id` query parameter or header sent by the board.
- Make `TaskUpdate.status` an `Optional[TaskStatus]` so invalid values return 422.
- Update the frontend API client to send the header on these routes.

**Tests:** Missing token → 401; invalid status → 422; wrong household → 404.

## P3-17. Enable SQLite WAL and a busy timeout

**Files:** `db/session.py`

```python
from sqlalchemy import event

def _apply_sqlite_pragmas(engine):
    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()
```

Call it for every SQLite engine created (including the fallback engines in `init_db`).

## P3-18. Run the scheduler in one process only

**Files:** `config.py`, `main.py`

Add `run_scheduler: bool = True` to `Settings`, and only call `start_scheduler()` when it's true. Document in `.env.example` that only one process should have it enabled when running multiple workers.

## P3-19. No default admin secret in deployment

**Files:** `config.py`, `api/admin.py`, `.env.example`, `README.md`

Change the default `admin_secret` to `""`. If it's empty, admin and task-mutating routes return 503 with "ADMIN_SECRET not configured". Keep `saath_admin_secret_demo` only in `.env.example` with a comment saying to change it before deploying. Update the README setup steps.

## P3-20. Repo hygiene

- Move `PLAN.md`, `saath.md`, and `Saath — Meta Hackathon Build Plan.docx` into `docs/planning/` (or delete if no longer needed; ask before deleting).
- Remove the root-level `reset_db.py` and `run_eval.py` if they only duplicate `backend/app/db/reset.py` and `backend/tests/run_eval.py` (check first; report if they differ).
- Make sure `.env`, `*.db`, and `data/` are in `.gitignore`. Run `git log --all -p -- .env` and report if a real `.env` was ever committed (do not print secret values; just say whether it happened).

---

# Final checklist

1. `cd backend && pytest -q`: all tests pass.
2. `python -m tests.run_eval --set regression` and `--set holdout` run without errors (offline, keyword baseline).
3. `docker compose up --build` starts cleanly; `/healthz` returns ok.
4. Update `README.md`:
   - Evaluation section: two tables (regression set, holdout set), guardrail recall **and** false-refusal rate, and a note that the regression set's payees appear in the keyword rules by design.
   - Remove or correct any claim that no longer matches the code (search the README for "round-robin", "falls back", "drafts", "Devanagari").
5. Print a summary: each task ID, commit hash, tests added, and anything skipped or stopped on, with the reason.
