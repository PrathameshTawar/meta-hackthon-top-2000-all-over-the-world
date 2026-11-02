# Saath: Full Audit Fix Plan for Claude Code

Every finding from the ECC verification loop and the nine skill reviews, including the second hunting pass, (security-audit, ponytail-audit, superpowers code review, Karpathy guidelines, Matt Pocock architecture, frontend-design, Hallmark, web-artifacts-builder, Vercel Web Interface Guidelines), audited at commit `cdd00f5`.

Save as `AUDIT.md` (later move it to `docs/dev/`, see P-7) and say: "Work through AUDIT.md in order, one task at a time, test first."

## Ground rules

These follow the Karpathy guidelines and the earlier task files.

1. **Work in order.** Finish one task (code, tests, commit) before starting the next.
2. **Test first.** Write the failing test, run it to see it fail, fix, then run the full suite (`cd backend && pytest -q`). Frontend tasks must pass `npm run build` and `npx tsc --noEmit`.
3. **One commit per task:** `fix(S-1): ...`, `chore(L-1): ...`, `feat(P-2): ...`, `refactor(A-1): ...`.
4. **Surgical changes only.** Every changed line must trace to the task. No drive-by refactors, renames, or reformatting outside the task's files. Mention unrelated problems in the summary instead of fixing them.
5. **No network in tests.** Monkeypatch `_call_llm`, `_transcribe_audio_muse`, `notify`, `notify_parents_task_done`, `_send_whatsapp_message`, `_send_telegram_message`, and `_answer_callback_query`.
6. **Stop and report** if a task conflicts with the code in a way this file doesn't anticipate.
7. **Product rules from HEALTH.md still bind.** No interpretive health words, alerts only from family-set limits, medications never extracted from documents, lab reports and prescriptions still refused.
8. **Tiers:** **Tier 1** must be done before deploying. **Tier 2** before recording the video. **Tier 3** only if time remains after the feature freeze. Each task is labeled.

---

# Part S: Security

## S-1. Require auth on every non-webhook router (Tier 1)

**Finding (confirmed with dummy data):** `members`, `households`, `events`, and `artifacts` routers have no auth dependency. Without any token:
- `POST /members/` added an "Attacker" member with a phone number to household 1 (201). The WhatsApp webhook identifies senders by phone, so that number becomes a family member that receives alerts and can claim, confirm, and complete tasks.
- `GET /artifacts/1` returned raw bill and voice-note transcripts; `GET /members/1` returned names; `GET /events/1` returned the audit log.

**Files:** `app/api/members.py`, `households.py`, `events.py`, `artifacts.py`

**Fix:** Construct each router as `APIRouter(dependencies=[Depends(verify_admin_auth)])`, like `tasks.py` and `health.py`.

**Tests (new file `tests/test_api_auth.py`, using FastAPI `TestClient` with a temporary SQLite DB set via env vars before importing `app`):**
- Every route on these four routers returns 401 without `X-Admin-Token`.
- `POST /members/` without a token creates no row.
- With the correct token, the existing behavior still works.
- Add one parametrized test that walks `app.routes` and asserts every route except `/webhook/*`, `/healthz`, `/docs`, `/openapi.json` and `/redoc` rejects requests without a token, so a future router can't be added unprotected.

## S-2. Make the Telegram webhook fail closed (Tier 1)

**Finding (confirmed):** `telegram_webhook` only checks the secret when `settings.telegram_webhook_secret` is set. With the default empty value, anyone can POST forged updates. Members are matched by `telegram_id`, which is a username string (e.g. `rohan_blr`), so a forger can claim and complete tasks or inject documents as that person.

**Files:** `app/api/webhooks.py` → `telegram_webhook`; `bot/bot.py`; `.env.example`; `README.md`

**Fix:**
- Reject with 403 when the secret is unset **or** the header doesn't match, mirroring the WhatsApp check. Use `hmac.compare_digest` for the comparison.
- Make sure `bot/bot.py` (long-polling mode) sends the same `X-Telegram-Bot-Api-Secret-Token` header when it forwards updates to the backend, read from the same env var.
- Document `TELEGRAM_WEBHOOK_SECRET` as required in `.env.example` and the README setup steps.

**Tests:** unset secret → 403; wrong secret → 403; correct secret → 200; `bot.py`'s forwarding helper includes the header (unit-test the function that builds the request).

## S-3. Remove the public default token and protect destructive admin routes (Tier 1)

**Finding:** `frontend/src/lib/api.ts` falls back to `"saath_admin_secret_demo"`, and `config.py` defaults `admin_secret` to the same value. With that token, `POST /admin/reset` wiped and reseeded the database locally. `NEXT_PUBLIC_*` variables are compiled into browser JavaScript, so on a public deployment the token is readable by anyone.

**Files:** `app/config.py`, `app/api/admin.py`, `frontend/src/lib/api.ts`, `.env.example`, `README.md`

**Fix:**
1. `config.py`: `admin_secret: str = ""`, and add `environment: str = "development"` (values `development` or `production`).
2. `api.ts`: remove the fallback; if `NEXT_PUBLIC_ADMIN_SECRET` is missing, don't send the header (requests then fail with a clear 401/503 rather than silently using a known token).
3. `admin.py`: when `settings.environment == "production"`, `/admin/reset`, `/admin/reset-db`, and `/admin/seed` return 403 regardless of token. Demo tools (`/admin/ingest/simulate`, `/admin/escalate/simulate`, `/admin/health/*`) stay available but rate-limited (S-8).
4. README: add a short "Demo access" note saying the board token is a demo key visible in the browser, that production disables destructive routes, and that real per-user auth is future work.

**Tests:** default settings → admin routes return 503; production + correct token → reset returns 403; development + correct token → reset works.

## S-4. Stop exposing Postgres with a default password (Tier 1)

**Finding (needs validation on the host):** `docker-compose.yml` publishes Postgres on `5432:5432` with user and password `saath`. On a cloud VM without a firewall rule, the database would be reachable from the internet with known credentials.

**Fix:** Resolved by R-4 (single SQLite database). If Postgres is kept instead, remove the `ports:` mapping from `db`, read `POSTGRES_PASSWORD` from `.env` with no default, and document it.

**Test:** a small test or CI step that parses `docker-compose.yml` and fails if the `db` service publishes a port or hardcodes a password.

## S-5. Upgrade vulnerable backend dependencies (Tier 1)

**Finding (pip-audit):** `starlette 0.38.6` (14 advisories, pulled in by `fastapi==0.115.0`) and `python-multipart 0.0.12` (14 advisories).

**Fix:**
1. Remove `python-multipart` entirely (nothing uses forms or uploads; see L-1).
2. Upgrade `fastapi` to the latest release whose required Starlette version has no open advisories, and pin both. Check with `pip-audit -r requirements.txt` until it reports no known vulnerabilities.
3. Run the full test suite and the app import check after upgrading.

**Acceptance:** `pip-audit` clean; all tests pass; `python -c "import app.main"` succeeds.

## S-6. Upgrade vulnerable frontend dependencies (Tier 1)

**Finding (npm audit):** `next 14.2.15` (critical), its bundled `postcss` (high), and `axios 1.7.7` (high).

**Fix:**
1. Upgrade `next` to the latest 14.2.x patch release and `axios` to the latest 1.x. Do **not** run `npm audit fix --force` (it jumps to Next 16, a breaking change).
2. Run `npm audit --omit=dev`. If a critical advisory remains that only a newer Next major fixes, stop and report it with the advisory IDs instead of upgrading the major version.
3. `npm run build` and `npx tsc --noEmit` must pass.

## S-7. Limit downloaded media size and type (Tier 1)

**Finding:** media downloaded from WhatsApp and Telegram has no size limit or MIME allowlist.

**Files:** `app/agent/nodes.py` (media download in `node_perceive`), `app/api/webhooks.py` (wherever media metadata is read)

**Fix:** Add `MAX_MEDIA_BYTES = 10 * 1024 * 1024` and an allowlist: `image/jpeg`, `image/png`, `image/webp`, `audio/ogg`, `audio/mpeg`, `audio/mp4`, `application/pdf`.
- Check the declared size and MIME type before downloading when the platform provides them.
- Stream the download and abort once it exceeds the limit.
- On rejection, reply to the parent in their language ("This file is too large, please send a photo instead") and log an event, without calling any model.

**Tests:** an oversized response is rejected without calling `_call_llm`; a disallowed MIME type is rejected; an allowed small image proceeds.

## S-8. Rate-limit admin and demo routes (Tier 1)

**Finding:** no rate limiting anywhere. Because the board token is public (S-3), `/admin/ingest/simulate` can be called repeatedly to run up model costs.

**Fix:** Add `slowapi`. Limit `/admin/ingest/simulate` and `/admin/health/dose-now` to 10 requests per minute per IP, other `/admin/*` routes to 30 per minute, and webhooks to 120 per minute per IP (high enough for Meta and Telegram retries). Return 429 with a short message.

**Tests:** the 11th simulate request within a minute returns 429 (use the limiter's in-memory storage in tests).

## S-9. Mask personal data in logs (Tier 2)

**Finding:** phone numbers and message text are logged at INFO, e.g. `webhooks.py:148` and `:246`.

**Fix:** Add `mask_phone(p)` (keep the last 4 digits: `+91******3210`) in a small `app/core/redact.py`. Use it in every log line that prints a phone number or chat ID. Never log message bodies, transcripts, or extracted amounts at INFO; log their length and the artifact ID instead.

**Tests:** `mask_phone` cases; a `caplog` test showing a simulated WhatsApp send logs no full phone number and no message text.

## S-10. Don't return exception text from webhooks (Tier 2)

**Finding:** Telegram handlers return `{"ok": False, "error": str(exc)}` (e.g. `webhooks.py:613, 647, 667, 687, 746`).

**Fix:** Log the exception with `logger.exception` and return `{"ok": False}` only.

**Test:** a handler that raises returns a body without the exception message.

## S-11. Stop fetching arbitrary URLs and reading arbitrary files (Tier 1)

**Finding (confirmed with dummy data):** `/admin/ingest/simulate` accepts any `file_url`, and `node_perceive` (`nodes.py` around lines 596–618) fetches any `http://` or `https://` URL from the server and reads any local path that exists. Locally, the server requested a loopback URL shaped like the cloud metadata endpoint (`/latest/meta-data/iam`), and a dummy local file's contents were sent to the model as an image payload. The model's "transcription" is stored in `raw_text`, which S-1's open `/artifacts` route exposed. With the board token public (S-3), on a deployed host this could read `.env` (WhatsApp token, API key, admin secret) or cloud metadata credentials.

**Files:** `app/agent/nodes.py` → `node_perceive`; `app/api/admin.py` → `simulate_ingest` and its request model; `tests/run_eval.py`

**Fix:**
1. In `node_perceive`, accept only these schemes: `telegram://`, `whatsapp://`, `whatsapp-pdf://`, `simulate://`. Delete the generic `http(s)` branch.
2. Local files: allow only when `settings.environment != "production"` **and** the resolved real path (`os.path.realpath`) is inside `backend/tests/eval_set/` (needed by `run_eval --live`). Reject everything else and log an event.
3. In `SimulateIngestRequest`, validate `file_url` against the same allowlist and return 422 otherwise.
4. Move the local file read into `asyncio.to_thread` (it currently blocks the event loop; ruff ASYNC230/240 at `nodes.py:601, 614, 617`).

**Tests:** `http://127.0.0.1:...` URL → no request is made (assert with a local test server that receives nothing) and an error event is logged; `/etc/hostname` → rejected; a file inside `tests/eval_set/` in development → read; the same in production → rejected; simulate with a bad `file_url` → 422.

---

# Part R: Correctness and reliability

## R-1. Route Telegram claim and done through the shared task service (Tier 1)

**Finding (confirmed):** Telegram's `claim:` and `done:` callbacks (around `webhooks.py:689–775`) still use inline code instead of `services/tasks.py`. Two "Done" taps on a monthly EMI created **two** next-month tasks and called `notify_parents_task_done` **twice**. Claim also lets one sibling silently take another's claimed task. WhatsApp (`webhooks.py:1120, 1140`) and the web API already use the service.

**Fix:** Replace both inline blocks with `claim_task(task_id, member)` and `complete_task(task_id, member.name, member.household_id)`, handling each `ClaimResult` / `DoneResult` with the same replies WhatsApp sends (via i18n, see R-5). Delete the inline recurrence code.

**Tests:** Telegram double "Done" on a monthly task → exactly one new task and one parent notification; Telegram claim of a task claimed by another sibling → "taken" reply, assignee unchanged; cross-household Telegram callback rejected.

## R-2. Fix `run_eval.py` on Python 3.11 (Tier 1)

**Finding:** `tests/run_eval.py:186` uses a backslash inside an f-string expression, which only Python 3.12+ allows. The Dockerfile and CI use Python 3.11, so judges reproducing the eval in Docker get a `SyntaxError`.

**Fix:** Compute `amount_digits = int(re.sub(r"[^\d]", "", amount) or 0)` before the f-string and use the variable. Search the whole backend for other f-strings with backslashes inside `{}` and fix them the same way.

**Test:** CI (T-5) compiles all files with Python 3.11: `python -m compileall -q app tests bot`.

## R-3. Log the latency that is already measured (Tier 2)

**Finding:** in `node_classify` (`nodes.py` around line 843), `latency_ms` is computed but never used.

**Fix:** Include `latency_ms` and `model` in that node's `_log_event` payload, as other nodes do. Check every other place that measures `time.perf_counter()` and confirm the value reaches an event.

**Test:** classify with a monkeypatched `_call_llm` writes an event whose payload has a numeric `latency_ms`.

## R-4. Use one database, with persistent storage (Tier 1)

**Finding:** `docker-compose.yml` runs Postgres (`postgresql+asyncpg`), but all tests, evals, and local development use SQLite, so the deployed path is untested. LangGraph checkpoints live in `data/checkpoints.db` with no volume, so a container restart loses paused confirmations.

**Fix (simplest, for the hackathon):**
- Switch compose to SQLite: remove the `db` service and `pgdata` volume, set `DATABASE_URL=sqlite+aiosqlite:////data/saath.db` and `CHECKPOINTS_DB_PATH=/data/checkpoints.db`, and mount a named volume at `/data`.
- Run the backend with exactly one worker (required by the per-household lock and the scheduler).
- Remove `asyncpg` (L-1). Note in the README that Postgres support is future work.

**Test:** CI step (T-5) runs `docker compose config` successfully; a test confirms settings read `CHECKPOINTS_DB_PATH` from the environment.

## R-5. Send Telegram replies through i18n (Tier 2)

**Finding:** Telegram handlers hardcode Marathi strings (for example "नोंदणी सापडली नाही.", "काम सापडले नाही.", "⚠️ हे काम तुमच्या कुटुंबाचे नाही."), bypassing I-1's per-member language.

**Fix:** Move every user-facing Telegram reply into `app/core/i18n.py` keys and call `t(key, member.language)`. When the member is unknown, use `settings.default_language`.

**Test:** a Telegram callback from an English-language member gets an English reply; no Devanagari string literals remain in `telegram_webhook` (assert with a source scan in the test).

## R-6. Remove the remaining mixed-language strings (Tier 2)

**Findings:**
- `frontend/src/components/HealthPanel.tsx:244`: "Blood Pressure Trend (BP ट्रेंड)"
- `frontend/src/components/HealthPanel.tsx:497`: "e.g. सकाळची गोळी / Metformin"
- `frontend/src/app/layout.tsx:10`: "Saath (साथ) — Family Coordination Board"

**Fix:** Move each into the frontend translation dictionary with one string per language. For the page `<title>`, use "Saath: family coordination board".

**Test:** add a script (`frontend/scripts/check-mixed-language.mjs`, run in CI) that fails if any `.tsx` string literal outside the translation files contains both Latin letters (3+ in a row) and Devanagari.

## R-7. Fix the lowercase `any` type (Tier 3)

**Finding:** `webhooks.py:64` uses `any` (the built-in function) where `typing.Any` was meant.

**Fix:** Use `Any`. **Test:** pyright no longer reports `reportGeneralTypeIssues` there.

## R-8. Replace deprecated `datetime.utcnow()` (Tier 3)

**Finding:** 9 calls (in `services/tasks.py`, `agent/nodes.py`, `api/webhooks.py`, `api/tasks.py`); they cause most of the 153 test warnings.

**Fix:** Add `utc_now_naive()` in a shared module returning `datetime.now(timezone.utc).replace(tzinfo=None)`, which keeps the current naive-UTC semantics for `updated_at` and `last_inbound_at`, and use it everywhere. Do not change any IST logic.

**Test:** the suite runs with no `DeprecationWarning` for `utcnow`.

## R-9. Never auto-confirm a bill with a missing amount or due date (Tier 1)

**Finding (confirmed with dummy data):** when the model's quote for the amount doesn't match the document, `node_extract` nulls the amount, but confidence stays at 0.67 (payee and due date grounded), so `node_verify` passes and the task is saved as `confirmed` with **no amount**. Nobody is asked, and the 30-day total silently undercounts. This bypasses the "pause and ask" safeguard for the most important field.

**Files:** `app/agent/nodes.py` → `node_verify`

**Fix:** Define required fields per category: `bill`, `loan_emi`, `insurance` need `amount` and `due_date`; `appointment` needs `due_date`; others need none. If any required field is missing or ungrounded after extraction, add a plain-English reason ("couldn't find the amount on the document") and fail verification so the graph interrupts and asks the family, showing the fields it did find.

**Tests:** a bill whose amount quote is wrong → interrupt, no task created until confirmation; a bill with all fields grounded → task created as before; an appointment with no amount → not interrupted for the amount.

## R-10. Never send stale medicine reminders (Tier 1)

**Finding (confirmed with dummy data):** with the server starting at 22:30, `ensure_todays_doses` created the day's doses and `send_due_reminders` immediately sent Aai **three** "time to take your medicine" messages, including the **08:00 morning** dose ("सकाळची गोळी"). Any evening deploy or restart could prompt a parent to take morning medicine at night or a dose twice.

**Files:** `app/services/health.py` → `ensure_todays_doses`, `send_due_reminders`; `app/config.py`

**Fix:**
1. Add `dose_reminder_grace_minutes: int = 60`.
2. `send_due_reminders` only messages the parent for doses with `scheduled_for` within the grace window (`now - grace <= scheduled_for <= now`).
3. Doses older than the window that were never reminded become `missed` with an event reason `reminder_not_sent` and **no parent message**. Send the owner child one combined note ("Saath couldn't send today's 08:00 reminder for Aai. Please check with her."), once per dose.
4. Never send more than one reminder per dose (already true; keep the test).

**Tests:** server start at 22:30 → no parent message for the 08:00 dose, one child note, and the 20:00 dose (150 min late) also not sent to the parent; start at 08:20 → the 08:00 reminder is sent; repeated runs send nothing new.

---

# Part T: Tests, coverage, and tooling

## T-1. Test the webhook entry points (Tier 2)

**Finding:** `webhooks.py` has 20% coverage, the lowest in the backend; total coverage is 63% against ECC's 80% target.

**Fix:** Add `tests/test_webhooks.py` covering, for WhatsApp: bad or missing signature → rejected; a repeated message ID → processed once; unregistered sender → polite reply, no artifact; button payloads `claim:`, `done:`, `dose_taken:`, `confirm_yes:`, `confirm_no:`, each with the household check. For Telegram: the same actions through callbacks, plus the secret check (S-2).

**Acceptance:** `webhooks.py` coverage at least 60%, total at least 75%.

## T-2. Add a coverage floor (Tier 2)

**Fix:** Add `pytest-cov` to dev dependencies (L-3) and set `--cov=app --cov-fail-under=75` in `pytest.ini` (raise to 80 after the hackathon).

## T-3. Configure ESLint (Tier 2)

**Finding:** `next lint` stops at an interactive setup prompt because no config exists.

**Fix:** Add `.eslintrc.json` with `{"extends": "next/core-web-vitals"}` and the matching dev dependency; fix any errors it reports (warnings may stay, listed in the summary).

## T-4. Configure ruff and apply safe fixes (Tier 3)

**Finding:** 412 ruff findings, 302 auto-fixable; repeated imports inside tests (`F811`).

**Fix:** Add a `[tool.ruff]` section to `pyproject.toml` (target `py311`, select `E,F,I,B,UP,SIM`). Run `ruff check --fix` (safe fixes only), remove the duplicated in-function imports in `tests/test_agent_pipeline.py`, and fix remaining `E`/`F` errors by hand. Leave style-only rules that need manual rewrites for later; list them in the summary.

## T-5. Make CI run everything (Tier 2)

**Finding:** `.github/workflows/ci.yml` runs only `tests/test_agent_pipeline.py` (28 of 38 tests), never builds the frontend, and doesn't check the eval.

**Fix:** In the backend job, run `python -m compileall -q app tests bot`, `ruff check app tests --select E9,F`, `pytest -q` (all tests, with the coverage floor), and `python -m tests.run_eval --set regression`. Add a frontend job: `npm ci`, `npx tsc --noEmit`, `npm run lint`, `npm run build`, and the mixed-language check from R-6. Add a CI status badge to the top of the README.

## T-6. Clean up the most misleading type errors (Tier 3)

**Finding:** pyright reports 47 errors, mostly `TypedDict` access and dict annotations in `nodes.py` and `graph.py`.

**Fix:** Only fix the ones that hide real nullability: `graph.py:205–208` (`AsyncSqliteSaver | None`) and the `get_db` return type in `db/session.py:72` (`AsyncGenerator[AsyncSession, None]`). Leave the rest; don't refactor `AgentState` for typing alone.

---

# Part L: Lean (remove what isn't needed)

## L-1. Remove unused dependencies (Tier 1, alongside S-5)

**Remove** after grepping to confirm no use: `python-multipart` (also clears 14 advisories), `alembic` (no migrations exist), `pytz` (use `zoneinfo`), `langchain-core` if nothing imports it directly, and `asyncpg` (after R-4).
**Keep:** `uvicorn`, `aiosqlite`, `langgraph-checkpoint-sqlite`, `Pillow`, `greenlet` (each is used indirectly).

**Acceptance:** fresh `pip install -r requirements.txt`, the full suite, and `python -c "import app.main"` all pass.

## L-2. Remove unused imports (Tier 3)

`nodes.py:15` (`struct`), `nodes.py:18` (`wave`), `health.py:6` (`and_`), `webhooks.py:12` (`tempfile`), `webhooks.py:42` (`detect_language`), `seed.py:14` (`delete`). Grep before each removal.

## L-3. Split dev dependencies (Tier 3)

Move `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, and `pip-audit` into `requirements-dev.txt`; the Dockerfile installs only `requirements.txt`; CI installs both.

---

# Part A: Architecture (Matt Pocock deepening)

## A-1. One family-action module for both channels (Tier 2)

**Finding:** `telegram_webhook` is 391 lines and `process_single_whatsapp_message` is 251 lines; they implement the same five actions (claim, done, dose taken, confirm yes, confirm no) twice. That duplication caused the R-1 regression.

**Fix:** Create `app/services/actions.py` with one interface: `async def handle_family_action(action: str, target_id: int, member: Member) -> ActionOutcome`, where `ActionOutcome` holds the result code, an i18n reply key with parameters, and any notifications to send. Telegram and WhatsApp handlers become adapters: parse the payload, look up the member, call `handle_family_action`, then render and send the reply in their own format. Do this after R-1, keeping R-1's tests green.

**Tests:** the action tests from R-1 and T-1 move to target `handle_family_action` directly; each channel keeps one thin adapter test per action.

## A-2. Split `node_vital` into a reading recorder (Tier 3)

**Finding:** `node_vital` is 351 lines doing six jobs: regex parsing, LLM fallback, quote verification, choosing the parent, saving, and threshold alerts.

**Fix:** Move parsing and verification into `app/services/readings.py` as `parse_readings(text) -> list[Reading]` (pure, no DB), and saving plus thresholds into `record_readings(household_id, member_id, readings) -> RecordResult`. `node_vital` keeps only orchestration and the reply. Existing vitals tests and the vitals eval must pass unchanged.

## A-3. One family messenger (Tier 3)

**Finding:** `notify()`, `_send_whatsapp_message()` (132 lines), `_send_telegram_message()`, and the Telegram callback answers each decide channel, 24-hour window, template, and language separately.

**Fix:** Create `app/services/messenger.py` with `send_to_member(member, message_key, params, buttons=None)` that picks the channel, chooses free text or the right per-language template, translates via i18n, and masks logs (S-9). Callers stop building channel-specific payloads.

## A-4. Add a domain glossary (Tier 3)

Create `CONTEXT.md` defining: Household, Parent, Sibling, Member language, Artifact, Task, Claim, Done, Escalation, Confirmation (interrupt), Dose, Reading, Family limit, Evidence quote. Use these names in A-1 to A-3.

---

# Part P: Product and README fixes carried over

## P-1. Remove the overfit baseline entries (Tier 1)

**Finding:** `KNOWN_PAYEES` in `nodes.py` (lines 151–152) still maps "Suyash" and "सोसायटीचे मेन्टेनन्स" to "Suyash Co-op Housing Society", the payee from the regression eval set.

**Fix:** Remove both entries. Re-run `--set regression` and `--set holdout`; update the README so the **holdout** table is the headline result and the regression set is labeled as a regression suite whose items the rules were partly written against.

## P-2. Safe reply for scam messages (Tier 2)

When a parent's message mentions OTP, KYC, "account blocked", "खाते बंद", "ओटीपी", or similar, reply in their language: "Don't share any OTP. I've asked {sibling} to check." Alert the category owner or all siblings in English with the masked message text. Create no task and make no model call that could act on the message. Add the keywords and strings to i18n.

**Tests:** a KYC-scam text triggers the safe reply and one sibling alert, creates no task; a normal bank letter without these words is processed as usual.

## P-3. Sibling quiet hours and time zones (Tier 2)

Add `timezone_name` (default `Asia/Kolkata`) to `Member`, editable via the members API. Non-urgent sibling notifications (new task, escalation) are held between 22:00 and 07:00 in the sibling's time zone and sent at 07:00; dose-missed and family-limit alerts are always sent immediately.

**Tests:** an escalation at 02:00 sibling time is queued and sent at 07:00; a vital alert at 02:00 is sent immediately.

## P-4. Flag stale claims (Tier 3)

Show "Claimed, no progress for 2 days" on task cards and the family view when a task has been `claimed` for 48 hours or more without becoming `done`, and include those tasks in the escalation job once.

**Tests:** a task claimed 49 hours ago is flagged and escalated once; one claimed 10 hours ago is not.

## P-5. Privacy reassurance on a parent's first photo (Tier 3)

The first time a parent sends a photo or document, append one line in their language: "Only your family can see this." Track it with a `first_photo_ack_sent` flag on `Member`.

**Test:** sent on the first photo only.

## P-6. Restructure the README top (Tier 2)

Order: one-line description with the tagline; CI badge (T-5); demo video link; live demo link with "try it yourself" steps; a short GIF; the holdout eval headline table; safety rules (money, medical, family limits); then architecture, setup, and the WhatsApp template details further down. Keep all claims true to the code.

## P-7. Move planning files out of the repo root (Tier 2)

Move `HEALTH.md` and this `AUDIT.md` into `docs/dev/` once all tasks are done.

---

# Part U: UI, accessibility, and design

Findings from frontend-design, Hallmark's code-level gates, web-artifacts-builder's anti-slop rules, and Vercel's Web Interface Guidelines. Hallmark's screenshot-based gates were not run.

## U-1. Label icon-only buttons (Tier 2)

`components/AuditLogModal.tsx:51`, `components/SimulateModal.tsx:124`, `components/TaskDetailPanel.tsx:52`: close buttons containing only an `<X />` icon. Add a translated `aria-label` ("Close") and `aria-hidden="true"` on the icon. Check every other button whose only child is an icon.

## U-2. Replace `transition-all` (Tier 2)

17 occurrences, starting at `app/page.tsx:47, 57, 67`, `components/AuditLogModal.tsx:75`, `components/Board.tsx:105, 115`. Replace each with the specific properties that change (`transition-colors`, `transition-transform`, `transition-opacity`, or `transition-[...]`).

## U-3. Respect reduced motion (Tier 2)

`components/Board.tsx:131` (`animate-ping`), `components/BoardSkeleton.tsx:10–11` (`animate-pulse`). Add `motion-reduce:animate-none` to each and a global `@media (prefers-reduced-motion: reduce)` block in `globals.css` that stops animations and transitions.

## U-4. Visible keyboard focus (Tier 2)

No `focus-visible` styles exist. Add a single shared style: an instant (no transition) 2px outline in the accent color with 2px offset, with at least 3:1 contrast against the surface, applied to all buttons, links, inputs, selects, and interactive cards.

## U-5. Use `Intl` for dates and numbers (Tier 2)

`components/AuditLogModal.tsx:96`, `components/TaskCard.tsx:97`, `components/TaskDetailPanel.tsx:66` use hardcoded `date-fns` format patterns. Use `Intl.DateTimeFormat` with the current UI language (`mr-IN`, `hi-IN`, `en-IN`) so dates follow the language switch. Format rupee amounts with `Intl.NumberFormat(locale, { style: "currency", currency: "INR" })`. Guard date rendering against hydration mismatch (format on the client or with a fixed time zone `Asia/Kolkata`).

## U-6. Fix contrast failures (Tier 2)

Measured ratios (WCAG needs 4.5:1 for normal text):
- White text on the terracotta button (`#c85a17`): **4.26:1**.
- Terracotta text on the canvas (`#f8f6f1`): **3.94:1**.
- Muted text (`#757064`) on the raised surface (`#f2eee5`): **4.26:1**.

Darken the accent used behind or as text until each pair reaches at least 4.5:1, and darken `muted` until it passes on both canvas and raised. Add a small test script that computes these ratios from the Tailwind config and fails below 4.5.

## U-7. No text under 12px (Tier 2)

`text-[10px]` appears 24 times and `text-[11px]` 38 times. Raise all running and functional text to at least 12px (`text-xs`); badges may stay at 12px with medium weight.

## U-8. Replace emoji used as icons (Tier 2)

10 lines, including `TaskCard.tsx:98` (" ⚠️" for overdue) and the ✅ / ⚡ prefixes in `SimulateModal.tsx` and `Board.tsx`. Use the existing `lucide-react` icons (with `aria-hidden`) or plain words. In `SimulateModal.tsx:249`, replace the "➔" arrow chain with a real ordered list or a short sentence. WhatsApp and Telegram message text may keep emoji; this task is about the web UI only.

## U-9. Remove template punctuation (Tier 3)

8 middle-dot meta strings (`AuditLogModal.tsx:92, 96`, `MembersBar.tsx:46`, `MonthCommitmentBar.tsx:94`, `TaskCard.tsx:158`, `lib/i18n.tsx:57` and others). Lay out the pieces as separate elements or a short sentence instead of joining them with " · ".

## U-10. Cut monospace and tracked-caps labels (Tier 3)

`font-mono` appears 42 times and uppercase tracked labels 14 times. Keep monospace only for amounts in tables and IDs where alignment matters (with `tabular-nums`); set other labels in the body face, sentence case, no letter-spacing. Remove the JetBrains Mono import from `globals.css` if nothing still uses it.

## U-11. Give the ledger its own accent (Tier 3)

**Finding:** cream paper (`#f8f6f1`) with a terracotta accent (`#c85a17`) is the most common AI-generated look (frontend-design trait #1, Hallmark gate 65), and close to Claude's own interface accent. The khata ledger concept is good; the accent is the problem.

**Fix:** Keep the ledger concept and paper. Change the accent to one taken from the subject: either the deep red of a bahi-khata cloth binding (hue below 15 in OKLCH, darker than the current terracotta) or the blue of ledger ruling ink. Update the Tailwind tokens only (no new components). Re-run U-6's contrast check afterward.

## U-12. Replace stock Tailwind status colors (Tier 3)

The status palettes reuse Tailwind defaults (`#eab308` yellow-500, `#16a34a` green-600 and their scales). Define warning and success tokens mixed for this palette (same lightness steps as the accent), and use them through tokens only. Never use yellow-500 as text (1.92:1 on white).

## U-13. Clean the font stack (Tier 3)

`tailwind.config.ts:59` and `globals.css:14` list `Inter` as a fallback after Plus Jakarta Sans. Remove `Inter`; keep Plus Jakarta Sans, Noto Sans Devanagari, and the system fallback.

## U-14. Make the modals accessible (Tier 2)

`components/AuditLogModal.tsx`, `components/SimulateModal.tsx`, and `components/TaskDetailPanel.tsx` have no `role="dialog"`, no `aria-modal`, no labelled title, no Escape-to-close, no focus trap, and no `overscroll-behavior: contain`. Add all of these with one small shared hook or wrapper (no new dependency): focus moves into the dialog on open, Tab cycles inside it, Escape closes it, focus returns to the button that opened it, and the background doesn't scroll behind it.

**Test:** a Playwright-free check is enough: render each modal in a unit test (React Testing Library if already present; otherwise skip the test and list manual steps in the summary) and assert `role="dialog"`, `aria-modal="true"`, and that pressing Escape calls `onClose`.

---

# Human-only checklist (not for Claude Code)

- **Settle authorship.** The README lists Prathamesh Taware as sole developer.
- **Get the Muse API key,** then run the live eval (`--set regression`, `--set holdout`, `--set vitals`, `--live` with real files) and commit the cache.
- **Add real inputs:** 10–15 real bill photos and 5 real voice notes, replacing the `TODO_REAL_PHOTO` placeholder.
- **Submit per-language WhatsApp templates** if R-5 / I-1 need them.
- **Set production environment variables:** `ENVIRONMENT=production`, a long random `ADMIN_SECRET` and `NEXT_PUBLIC_ADMIN_SECRET`, `TELEGRAM_WEBHOOK_SECRET`, `WHATSAPP_APP_SECRET`.
- **Deploy** with the `/data` volume (R-4) to an always-on host, and run the full demo flow there twice.
- **Validate S-3 on the deployed build:** confirm `/admin/reset` returns 403.
- **Record the subtitled demo video** and add the links to the README (P-6).

---

# Order and cut lines

**Before deploying (Tier 1):** S-1, S-11, S-2, S-3, S-4 + R-4, S-5 + L-1, S-6, S-7, S-8, R-1, R-9, R-10, R-2, P-1.

**Before recording (Tier 2):** S-9, S-10, R-3, R-5, R-6, T-1, T-2, T-3, T-5, A-1, P-2, P-3, P-6, P-7, U-1 to U-8, U-14.

**Only if time remains after the freeze (Tier 3):** R-7, R-8, T-4, T-6, L-2, L-3, A-2, A-3, A-4, P-4, P-5, U-9 to U-13.

If time runs short, cut from the bottom of Tier 3 upward. Never skip Tier 1.

# Final checklist

1. `cd backend && pytest -q`: all green, coverage floor met.
2. `pip-audit -r requirements.txt` and `npm audit --omit=dev`: no critical or high findings (or each remaining one reported with its advisory ID).
3. `npm run build`, `npx tsc --noEmit`, `npm run lint` pass.
4. `python -m tests.run_eval --set regression` and `--set holdout` run under Python 3.11.
5. `docker compose up --build` starts with the SQLite volume; `/docs` loads; `/admin/reset` refuses in production mode.
6. Print a summary: each task ID, commit hash, tests added, and anything skipped or stopped on, with the reason.

