# Saath Health Module: Tasks for Claude Code

Save as `HEALTH.md` in the repo root and say: "Work through HEALTH.md one task at a time, same rules as FIXES.md."

## Ground rules

Same as FIXES.md: tasks in order, failing test first, one commit per task (`feat(H-1): ...`), full `pytest -q` green before moving on, no unrelated refactors, no network calls in tests (monkeypatch `_call_llm`, `_transcribe_audio_muse`, `notify`, `_send_whatsapp_message`, `_send_telegram_message`), stop and report on conflicts.

## Product rules (do not violate)

1. **Saath never interprets health data.** No words like "high", "low", "normal", "dangerous", diagnoses, or medicine advice in any message, UI string, or prompt output.
2. **Alerts come only from thresholds the family set.** The only judgment is a code comparison against a limit a child entered (for example "doctor said tell us if systolic is above 150"). Messages say "beyond the limit your family set", never "high blood pressure".
3. **Medications are entered by the children, never extracted.** Prescriptions stay blocked by the existing guardrail (P0-8). The agent never reads medicine names or doses from documents.
4. **Lab reports and prescriptions still go to the guardrail.** Nothing in this module changes that path.
5. **Times are IST.** Store naive datetimes in IST, consistent with the existing `due_date` handling, and use `get_current_ist_datetime()` from `nodes.py` for "now".

## Repo context

- Models: `backend/app/db/models.py` (`Household`, `Member` with `role` parent/child and `phone`, `Task`, `Event`)
- Agent: `backend/app/agent/nodes.py`, `graph.py`, `state.py`
- Shared task logic: `backend/app/services/tasks.py`
- Messaging: `notify()` and `_send_whatsapp_message()` in `backend/app/api/webhooks.py` (supports interactive buttons and templates with `template_button_payloads`)
- Scheduler: `backend/app/scheduler/escalation.py` (`start_scheduler`)
- Admin/demo routes: `backend/app/api/admin.py` (`verify_admin_auth`)
- Frontend: `frontend/src/components/Board.tsx`, `SimulateModal.tsx`, `frontend/src/lib/api.ts`

---

## H-1. Data models and API skeleton

**Files:** `db/models.py`, new `api/health.py`, `main.py`

Add tables:

- `Medication`: `id`, `household_id`, `member_id` (the parent who takes it), `name` (String 120, family-entered), `dose_text` (String 120, family-entered, e.g. "1 tablet"), `times` (JSON list of `"HH:MM"` strings in IST), `owner_child_id` (Member, nullable; who gets missed-dose alerts), `active` (bool, default true), `created_at`.
- `DoseLog`: `id`, `medication_id`, `scheduled_for` (naive IST datetime), `status` (enum: `pending`, `taken`, `missed`), `reminder_sent_at`, `responded_at`, `escalated_at` (all nullable). Unique constraint on (`medication_id`, `scheduled_for`).
- `Vital`: `id`, `household_id`, `member_id`, `kind` (enum: `bp`, `sugar`, `weight`, `spo2`, `pulse`, `temperature`), `value_1` (Numeric), `value_2` (Numeric, nullable; diastolic for BP), `unit` (String 20), `measured_at` (naive IST), `artifact_id` (nullable), `quote` (Text; verbatim source span), `created_at`.
- `VitalThreshold`: `id`, `household_id`, `member_id`, `kind`, `field` (`value_1` or `value_2`), `op` (`gt` or `lt`), `limit` (Numeric), `note` (String 200, e.g. "Doctor advised"), `set_by_member_id`, `active`.

Create `api/health.py` with router prefix `/health`, protected by the same admin-token dependency used for tasks (P3-16 if done, otherwise `verify_admin_auth`):

- `GET /health/{household_id}/summary` → today's doses (with status), last 14 days of vitals per parent, active thresholds, active medications.
- `POST /health/medications`, `PATCH /health/medications/{id}` (edit or deactivate)
- `POST /health/thresholds`, `PATCH /health/thresholds/{id}`

Validate that every referenced member belongs to `household_id` (404 otherwise), that `times` are valid `HH:MM`, and that `member_id` for medications and vitals is a parent.

**Tests:** create medication with invalid time → 422; member from another household → 404; summary returns created items.

## H-2. Medicine reminders with adherence escalation

**Files:** new `services/health.py`, `scheduler/escalation.py`, `api/webhooks.py`, `config.py`, `api/admin.py`

Settings: `dose_escalate_after_minutes: int = 120`.

1. **`ensure_todays_doses(now)`**: for each active medication and each time today (IST), create a `DoseLog` if missing (rely on the unique constraint; ignore conflicts).
2. **`send_due_reminders(now)`**: for `pending` doses with `scheduled_for <= now` and `reminder_sent_at is None`, send the parent:
   - Interactive message (inside 24h window): Marathi text `"🙏 नमस्कार {parent_name}, {med_name} ({dose_text}) घेण्याची वेळ झाली आहे. घेतल्यावर खालील बटण दाबा."` with button `{"id": f"dose_taken:{dose.id}", "title": "घेतली ✅"}`.
   - Template fallback: `template_name="saath_med_reminder"`, `template_language="mr"`, params `[parent_name, med_name]`, `template_button_payloads=[f"dose_taken:{dose.id}"]`. Add `"saath_med_reminder": "mr"` to `TEMPLATE_LANGUAGES`.
   - Set `reminder_sent_at`.
3. **`escalate_missed_doses(now)`**: `pending` doses with `reminder_sent_at` older than `dose_escalate_after_minutes` → status `missed`, set `escalated_at`, notify `owner_child_id` (or all children if none) with English text `"{parent_name} hasn't confirmed taking {med_name} (scheduled {HH:MM}). Please check in with them."`; template fallback `saath_dose_missed` (`en_US`), params `[parent_name, med_name, "HH:MM"]`. Write an `Event` for every state change. Idempotent: a dose is escalated at most once.
4. **Scheduler:** add a job every 5 minutes running steps 1–3 in order. Respect `RUN_SCHEDULER` if P3-18 is done.
5. **Webhook:** in both the WhatsApp button handler and the Telegram callback handler, handle `dose_taken:<id>`:
   - Verify the dose's medication belongs to the sender's household.
   - If already `taken` → reply "आधीच नोंदवले आहे 🙏" and stop.
   - If `pending` or `missed` → set `taken`, `responded_at`; reply `"✅ नोंद केली. धन्यवाद! 🙏"`. If it was `missed` (late tap), notify the owner child "Update: {parent_name} has now taken {med_name}."
6. **Demo/admin:** `POST /admin/health/dose-now` (body: `medication_id`) creates a dose scheduled for now and sends the reminder immediately; `POST /admin/health/skip` (body: `minutes`, default 120) runs `escalate_missed_doses(now + minutes)`.

**Tests:** doses created once per time per day; reminder sent once; tap marks taken and second tap is idempotent; untapped dose escalates once after 120 minutes; late tap after escalation sends the update; cross-household tap rejected.

## H-3. Vitals by voice note or text

**Files:** `agent/nodes.py`, `agent/graph.py`, `agent/state.py`, `services/health.py`

1. **Detection in `node_classify`** (after the existing status-query check, before the bill/medical logic): if the text matches a vitals pattern **and** is not diagnostic per P0-8's rules (lab report / prescription keywords), return `{"category": "vital"}` (plain string, not a `TaskCategory`). Patterns (handle Devanagari digits via `DEV_DIGITS` and `norm()` from P1-9):
   - BP: `(?:bp|बीपी|रक्तदाब|ब्लड प्रेशर)?\s*(\d{2,3})\s*(?:/|by|बाय|वर)\s*(\d{2,3})`, requiring a BP keyword somewhere in the text.
   - Sugar: keyword in `sugar, शुगर, साखर, ग्लुकोज` followed within 20 chars by a 2–3 digit number.
   - Weight: `weight, वजन` + number + optional `kg/किलो`.
   - SpO2: `spo2, ऑक्सिजन, oxygen` + 2-digit number.
   - Pulse: `pulse, नाडी, पल्स, heart rate` + 2–3 digit number.
   - Temperature: `temp, ताप, तापमान, fever` + number with optional decimal.
2. **`node_vital`:** extract each reading with a deterministic regex parser first. If a key is set and the regex finds nothing, call `_call_llm` asking for JSON `[{"kind","value_1","value_2","unit","quote"}]`. Every reading must have a `quote` that passes `norm(quote) in norm(raw_text)`, and the numbers in the quote must equal the extracted values via `to_amount`-style parsing; drop readings that fail. Plausibility bounds (drop and log if outside): BP systolic 60–260, diastolic 30–160, sugar 20–700, weight 20–250, SpO2 50–100, pulse 30–220, temperature 90–110 °F or 32–43 °C.
3. **Who it's for:** the sender if they are a parent. If a child sends it, use the household's only parent; if there are two parents, take the one whose name appears in the text, else create no vital and reply asking whose reading it is (do not guess).
4. **Save** each reading as a `Vital` with the quote and `artifact_id`.
5. **Thresholds:** compare each saved reading against the member's active `VitalThreshold`s with plain code. If crossed, notify the threshold's `set_by_member_id` (or all children) in English: `"{parent_name} reported {reading} at {HH:MM}, beyond the limit your family set ({field} {op_symbol} {limit}{', ' + note if note}). Please check in."` Template fallback `saath_vital_alert` (`en_US`), params `[parent_name, reading, HH:MM, "{field} {op_symbol} {limit}"]`.
6. **Parent reply** (Marathi, or Hindi if household language is `hi`): `"नोंद केली: {reading}. 🙏"`; if a threshold was crossed append `" तुमच्या मुलांना कळवले आहे."`. Never add interpretation.
7. **Graph:** route `"vital"` → `"vital"` node → END.

**Tests:** "आज बीपी १५०/९५ आहे" → one BP vital 150/95 with a verbatim quote; "BP 150 by 95" → same; "sugar 180 fasting" → sugar 180; a lab report containing "fasting blood sugar 180 mg/dl" still goes to the guardrail; threshold `value_1 gt 140` triggers exactly one alert; implausible "BP 15/9" saves nothing; no reply string contains "high", "low", "normal", "जास्त", or "कमी".

## H-4. Appointment logistics polish

**Files:** `agent/nodes.py` → `node_draft`

For tasks with category `appointment`:
- Sibling notification: `"🏥 {payee or 'Doctor'} appointment for {parent_name} on {date}. Who can take them? Tap Claim."`
- Parent reply (Marathi): `"अपॉइंटमेंट नोंदवली: {Marathi date}. कोण सोबत येणार ते लवकरच कळवू. 🙏"` (use the Marathi date formatting from P1-13 if done; otherwise add a small `_marathi_date()` helper).
- When a sibling claims an appointment task, send the parent: `"{child_name} तुमच्यासोबत {Marathi date} ला येणार आहे. 🙏"` (add this in `services/tasks.claim_task`'s caller for the `appointment` category only).

**Tests:** appointment draft contains "Who can take them"; claiming an appointment notifies parents once.

## H-5. Health tab on the board

**Files:** `frontend/src/components/Board.tsx` (or a new `HealthPanel.tsx` it renders), `frontend/src/lib/api.ts`, `SimulateModal.tsx`

Add a "Health / आरोग्य" tab next to the task board, using the existing styling:

1. **Today's medicines:** one row per dose: parent, medicine, time, status chip (pending / taken ✅ / missed ⚠️). Poll the summary endpoint every 5 seconds, like the board does.
2. **Readings:** per parent, a list of the last 14 days of vitals with time, value, and an "evidence" toggle showing the quoted source (reuse `EvidenceHighlight` if it fits). For BP, add a small inline SVG line chart of systolic/diastolic (hand-written SVG; no new chart library). Draw the family threshold as a dashed line labeled "Family limit".
3. **Family limits:** list active thresholds with their note; form to add one (parent, kind, field, `>`/`<`, limit, note).
4. **Medicines setup:** list and add/deactivate medications (parent, name, dose text, times, owner child).
5. **Demo tools** in `SimulateModal`: "Send dose reminder now" (pick medication) and "Skip 2 hours" (calls the H-2 admin routes), plus a "Simulate vital" text box that posts to the existing `/admin/ingest/simulate` route.
6. Footer note on the tab, in small text: "Saath records what your family reports. It does not give medical advice."

No new npm dependencies.

## H-6. Seed data and README

**Files:** `db/seed.py`, `README.md`, `.env.example`

- Seed for the demo household: one medication for Aai at 08:00 and 20:00 (name "सकाळची गोळी"/"रात्रीची गोळी" style generic names, dose "1"), owner child set; one threshold for Baba: BP `value_1 gt 150`, note "Doctor advised"; three past BP readings for Baba over the last week, one with a verbatim quote from a seeded artifact.
- README: add a "Health module" section with the product rules from the top of this file, the three new WhatsApp templates (exact names, categories, languages, bodies below), and the H-7 eval table. Update the architecture diagram text to show the `vital` branch.

WhatsApp templates (the human creates these in WhatsApp Manager; just document them):

| Name | Category | Language | Body | Button |
|---|---|---|---|---|
| `saath_med_reminder` | UTILITY | mr | `नमस्कार {{1}}, {{2}} घेण्याची वेळ झाली आहे. घेतल्यावर खालील बटण दाबा.` | Quick reply "घेतली ✅" (payload `dose_taken:<id>`) |
| `saath_dose_missed` | UTILITY | en_US | `{{1}} has not confirmed taking {{2}} (scheduled {{3}}). Please check in with them.` | none |
| `saath_vital_alert` | UTILITY | en_US | `{{1}} reported {{2}} at {{3}}, beyond the limit your family set ({{4}}). Please check in.` | none |

## H-7. Evaluation slice for vitals

**Files:** `tests/eval_set/eval_items.json` (or a new `vitals_items.json`), `tests/run_eval.py`

Add 15 typed items: 10 vitals phrasings across Marathi, Hindi, and English (Devanagari and Latin digits, "by"/"/"/"वर" separators, two readings in one message, one implausible value, one with no number), plus 5 that must **not** become vitals (lab report with "fasting blood sugar", prescription with "500 mg", a bill containing "₹150/95" style numbers, a status question, and chit-chat). Report: reading-level accuracy (kind + values), threshold decision accuracy, and "non-vital correctly not logged". Add the table to `docs/evaluation_results.md`.

---

## Final checklist

1. `pytest -q` green.
2. Run the eval; paste the vitals table into the README.
3. Manually verify on real phones (human step): dose reminder arrives on the parent's WhatsApp, tap marks taken; untapped dose escalates after "Skip 2 hours"; a BP voice note crosses the threshold and the sibling gets the alert.
4. Print a summary of commits and anything skipped.

