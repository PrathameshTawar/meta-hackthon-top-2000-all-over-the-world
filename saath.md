# Saath — Meta Hackathon Build Plan

Oct 28, 2026 · @SASA

Step-by-step implementation with the code for every file: Build guide


## Problem statement

India's sole earners are running two households from one phone, and their aging parents are losing control of their own affairs in the process.


| Your statement | What it adds to the merged problem |
| --- | --- |
| Aging parents, sole earners across cities | The core user: one earner, parents in another city, everything handled by phone |
| Parents' health plus education loans | The earner's own loan EMIs share the same month and the same wallet; health stays logistics only (appointments, insurance renewals, hospital bills) |
| AI for the aging population | Parents are users, not subjects: they speak in their own language and hear back when things are done |


The problem. Many adult children are the main earners for their families and live in a different city from their aging parents. They repay their own education loans while remotely handling their parents' bills, pension and bank paperwork, insurance renewals, and appointment logistics. This arrives as phone calls, voice notes, and photos of paper documents in Marathi or Hindi, and it is tracked nowhere. Siblings duplicate or drop tasks. Deadlines slip into late fees and lapsed policies. The earner never sees the month's total commitments, the parents' bills plus their own EMI, in one place. The parents lose independence too, because most tools are English, text-heavy, and built to monitor them rather than serve them.

Why it matters now

- Indians aged 60 and over are projected to pass 20% of the population by 2050 and to outnumber children by 2046 (UNFPA India Ageing Report 2023).
- About 3 in 10 people aged 60+ live with none of their children: 5.7% alone, 20.3% with a spouse or others, and 5.7% with others only (LASI Wave 1 factsheet).
- 48% of people aged 60+ have difficulty with at least one instrumental daily activity, a group that includes paying bills and keeping track of expenses (LASI).
- Only 39.6% of people aged 60+ are literate (LASI), so a voice-first design is a requirement, not a feature.
- 18.7% of older Indians have no income at all and depend on family (UNFPA).
- Outstanding education loans grew about 40% in three years to ₹1.37 lakh crore in 2025, with repayment running up to 15 years after the moratorium (The Week, June 2026).
How might we let aging parents report what needs doing in their own voice and language, and turn it into one verified plan their children can act on from anywhere, so no deadline is missed and the earner sees the whole month at once, without giving medical or financial advice?

Success looks like

- A parent reports a bill with one voice note or photo, with no typing and no app to learn.
- Every task on the board links back to the exact words it came from.
- Nothing due within 3 days stays unclaimed without an escalation.
- The earner sees the next 30 days' total across the parents' bills and their own EMIs.
- Parents hear back in their own language when something is done.
- For the judges: a measured evaluation table, with all 5 medical items refused.
Boundaries: no medical interpretation, no financial advice, no payments; Standard-mode models and private storage for every family document.


## Reality check

Seven build days remain (Oct 28 to Nov 4), solo, and the 3-minute video carries most of the score. Submit by Nov 4, 6:00 PM IST; the hard deadline is Nov 4, 9:00 PM ET, which is Nov 5, 7:30 AM IST because US clocks fall back on Nov 1.

- The video is the product. Demo (25%) and most of Impact (30%) are judged from it. Build only what appears in the video or proves it is real.
- Claim credits today. Meta API credits need a credit card. Indian cards often block international charges until enabled in the banking app.
- Verify the models on day one. Confirm Muse Voice Transcribe and Muse Spark endpoints, input limits, and Marathi support. If Marathi transcription is weak, demo in Hindi.
- Commit often. The repo must be public and everything must be built during the event; commit history is the proof.
- Stay inside the rules. Medical advice is banned, so the product handles logistics only and shows that boundary on camera.

## Product spec

Saath (साथ, "together") turns a parent's voice notes and document photos into a shared task board for siblings living in other cities. Track: Build for Your World.


| User | What they do | Interface |
| --- | --- | --- |
| Parent | Sends voice notes and photos, asks what's pending, hears back when things are done | Telegram bot |
| Earner and siblings (1 to 3 children) | Claim tasks, forward their own loan EMIs, see the 30-day total and the evidence | Web board |
| Local helper (optional) | Gets errand tasks like collecting a courier | Telegram bot |


Four core flows. Build these and nothing else.

- Capture: a Marathi voice note or a photo of a bill becomes one obligation with what, amount, due date, payee, and source evidence. The earner forwards their own loan EMI notices the same way.
- Coordinate: the task lands on the family board, is auto-assigned by category, siblings are notified, and duplicates merge.
- Close the loop: the assignee gets a nudge with a Claim button, unclaimed tasks escalate near their deadline, and when a task is done the parent hears it in Marathi. Parents can also ask "what's pending?" by voice.
- Plan the month: the earner sees every obligation due in the next 30 days, the parents' and their own, with one total; monthly EMIs repeat automatically.
Out of scope (state this in the README): payments, phone calls, medical interpretation, financial advice, and real bank integrations.


## Architecture and data model

A Telegram bot for parents, FastAPI and a LangGraph agent in the middle, a web board for siblings served by the same app. Skip Redis; hosting details are in the Deployment section.

system architecture · 7 components

Parents install nothing; every model call goes through the agent, and every task row carries its evidence. Telegram replaces the WhatsApp Business API because it needs no approval; say "WhatsApp next" in the video.


| Table | Key columns |
| --- | --- |
| households | id, name, primary_language |
| members | id, household_id, name, role (parent, child, helper), telegram_id, categories_owned |
| artifacts | id, household_id, type (voice, image), file_url, transcript_or_ocr, received_at |
| tasks | id, household_id, category, title, amount, due_date, payee, status, assignee_id, confidence, dedupe_key, recurrence |
| evidence | id, task_id, artifact_id, field_name, quoted_span |
| events | id, household_id, task_id, action, reason, created_at |



## Agent graph

Every extracted field must carry the exact quote it came from, and plain code, not the model, checks that quote before anything reaches the board.

LangGraph agent, 12 nodes and 3 branches

- Classify sorts into bill, loan EMI, pension or government letter, insurance renewal, appointment logistics, medical content, a spoken status question, or chit-chat. A status question gets a short Marathi summary of what's pending and who is on it.
- Guardrail logs only date, place, and transport for medical items, then sends a fixed reply: it can track the appointment but cannot interpret reports.
- Extract returns JSON; a field with no supporting quote is set to null.
- Verify checks that the quote appears in the transcript or OCR text, the date is valid and upcoming, and the amount appears in the quote. A failure or low confidence triggers a LangGraph interrupt.
- Dedupe matches on payee, amount, and a due-date window; a repeat becomes extra evidence on the same task. Assign then routes it to the sibling who owns that category, or round-robin if nobody does.
- The hourly scheduler (see architecture) escalates any task due within 3 days that nobody has claimed.

## Deployment

Run one FastAPI service on Railway with its own Postgres, keep files in a private S3 bucket, and serve the sibling board from the same app. No GPU is needed anywhere, because every model call goes to Meta's hosted API.


| Piece | Choice | Why |
| --- | --- | --- |
| App | FastAPI + LangGraph in one Docker container, 1 replica | One URL, no CORS, and the in-process scheduler runs exactly once |
| Sibling board | Server-rendered pages (Jinja, HTMX, Tailwind) from the same app, polling every 3 s, installable as a PWA | No second build or deployment; still updates live on camera |
| Database | Railway Postgres in the same project | One dashboard; connection string arrives as an env variable |
| Files | Private S3 bucket, presigned URLs in the evidence panel | Parents' documents are never public; you already know AWS |
| Scheduler | APScheduler inside the app, plus a "simulate 3 days later" admin endpoint | No extra service, and the demo never waits for real time |
| Telegram | Webhook at /telegram/webhook with a secret token checked on every request; long polling for local dev | Webhooks need HTTPS; the token blocks forged requests |
| Models | Meta Model API, outputs cached by file hash; Meta's MMS-TTS voice model runs on CPU inside the app | Saves the $150 credit and makes every demo take identical |
| Secrets | Railway env vars, .env.example in the repo, GitHub push protection on | The repo must be public |


Options considered


| Option | Verdict |
| --- | --- |
| Railway | Pick: container, Postgres, and an HTTPS URL in minutes, and it stays awake. Check current pricing before you start. |
| AWS (EC2 or App Runner, plus RDS) | You know it, but VPC, IAM, and RDS setup costs a day you don't have. Use only S3. |
| Modal ($100 credits) | Can host FastAPI, but needs an outside database, and cold starts make webhook debugging harder. |
| Any free tier that sleeps when idle | Avoid: a sleeping app drops or delays Telegram webhooks mid-demo. |


Deployment checklist

- ☐ Dockerfile and docker-compose.yml (app + Postgres) so anyone can run it with one command
- ☐ /healthz endpoint, checked before every recording session
- ☐ Seed script for the demo household and a reset script run before each take
- ☐ Board access through signed per-member links, no passwords
- ☐ GitHub Actions running pytest on verification and dedupe logic with cached fixtures, no API calls
- ☐ Log every model call and agent decision to the events table

## Evaluation set and metrics

A 35-item test set with measured accuracy is what separates this from a basic document-reading app. Use synthetic or redacted data only: real bills with account numbers covered, mock letters, and voice notes recorded by a family member.


| Slice | Items | Metric | Target |
| --- | --- | --- | --- |
| Bill and letter photos | 15 | Field accuracy: amount, due date, payee | 85%+ |
| Voice notes (Marathi or Hindi) | 10 | Field accuracy and category accuracy | 80%+ |
| Duplicate pairs | 5 | Correctly merged | 5 of 5 |
| Medical content (reports, prescriptions) | 5 | Guardrail recall: refused interpretation | 5 of 5, required |


Show the results table in the README and for about 10 seconds in the video. Targets are suggested starting points; report the real numbers whatever they are.


## Day-by-day plan

Risky parts first, features frozen on Nov 2, video on Nov 3, submit Nov 4 by 6:00 PM IST. Each day ends with a "done when" check; if it fails, cut from the list at the end of this doc.


### Wed Oct 28: setup and model tests

- ☐ Claim Meta API credits and enable international card payments
- ☐ Create the public repo and make the first commit
- ☐ Test Muse Voice Transcribe on one Marathi and one Hindi voice note
- ☐ Test Muse Spark on one bill photo
- ☐ Watch Agents 102 at 9:30 PM IST
- ☐ Create the bot with BotFather and set up a second Telegram account for the sibling role
- ☐ Repo skeleton: Dockerfile, docker-compose, .env.example, push protection on
- ☐ Check which phones and watch you can use; turn on Telegram notifications on the watch
- ☐ Play three MMS-TTS Marathi sentences to a parent; keep MMS-TTS or switch to recorded clips
- Done when: demo language is decided and both models return usable output

### Thu Oct 29: capture pipeline

- ☐ Telegram bot receives voice notes and photos
- ☐ Perception and extraction to JSON with quoted evidence, stored in Postgres
- ☐ Start collecting the 35-item evaluation set
- ☐ Deploy the skeleton to Railway with Postgres and set the webhook with a secret token
- Done when: a bill photo sent to the bot creates a task row with evidence on the deployed app

### Fri Oct 30: agent graph

- ☐ Code-based verification and the confirmation pause
- ☐ Deduplication and category-based assignment
- ☐ Medical guardrail with fixed reply
- ☐ Optional: Fireworks session at 9:30 PM IST
- Done when: a duplicate merges, a blurry bill asks for confirmation, a lab report is declined

### Sat Oct 31: family board

- ☐ Board columns: New, Claimed, Done
- ☐ Task cards with evidence panel (click a field to see its quote and image)
- ☐ Member view, served from the same deployment
- ☐ PWA manifest, icons, and service worker; install on Android and iPhone
- Done when: a sibling opens a link and claims a task

### Sun Nov 1: close the loop

- ☐ Drafted Marathi reply, sibling nudge, call script
- ☐ Hourly escalation scheduler
- ☐ Audit log view
- ☐ Claim button on Telegram nudges, with a watch-friendly first line
- ☐ Month view with the 30-day total, done confirmations to parents, monthly EMI repeats
- ☐ Voice status questions and appointment reminders (first to cut if behind)
- ☐ Marathi voice replies with Meta's MMS-TTS (Build guide step 13)
- Done when: parent voice note to parent confirmation works end to end

### Mon Nov 2: evaluate and harden

- ☐ Run the evaluation set and fix the worst failures
- ☐ Handle unreadable images, silent audio, unknown senders
- ☐ Write the results table
- ☐ Freeze features tonight
- ☐ Rehearse on the live deployment: reset script, health check, cached model outputs

### Tue Nov 3: video and README

- ☐ Record each scene separately and edit to 3:00
- ☐ Draw the architecture diagram for the video and README
- ☐ Write the README
- ☐ Set up OBS and phone mirroring; run the reset script before every take

### Wed Nov 4: submit

- ☐ Confirm the repo is public and the README covers what was built during the event
- ☐ Upload the video
- ☐ Submit by 6:00 PM IST

## Demo video script (3:00)

Every scene is recorded separately and re-shot until clean; nothing runs live.


| Time | Scene | What the judge sees |
| --- | --- | --- |
| 0:00–0:20 | Hook | "My parents live in Pune. Their kids live in three other cities." A messy family chat thread. |
| 0:20–0:50 | Capture | Parent sends a Marathi voice note about the electricity bill and a photo of an insurance renewal. Bot replies with a Marathi voice note. |
| 0:50–1:30 | Coordinate | Board updates live, task auto-assigned. Click a field to see its quoted evidence. A duplicate photo merges. The earner forwards their own loan EMI and the 30-day total updates. |
| 1:30–1:55 | Verification | Blurry bill triggers a confirmation question. A lab report is declined: logistics only, never medical advice. |
| 1:55–2:20 | Escalation | Simulate 3 days later; unclaimed task pings every sibling. The sibling's watch buzzes, and one tap on Claim in Telegram updates the board. Marked done, and the parent's phone says so in Marathi. |
| 2:20–2:45 | How it works | Architecture diagram, evaluation table, Meta models named. |
| 2:45–3:00 | Impact | Two numbers from LASI: 3 in 10 Indians over 60 live with none of their children, and only 4 in 10 can read. Then close. |


Every number in the video is sourced in the Problem statement section; cite the same links in the README.


## Hardware, phones, and watch

You need no special hardware: a laptop, two phones (ideally one iPhone and one Android) with two phone numbers, printed props, and optionally any smartwatch. The one easy-to-miss item is the second number, because each Telegram account needs its own.


| Item | Used for | If you don't have it |
| --- | --- | --- |
| Laptop, no GPU | Development, Docker, recording | Any laptop that runs Docker works, since inference runs on Meta's API |
| Phone 1 (parent) | Sends Marathi voice notes and bill photos to the bot | Borrow one; this is the core of the demo |
| Phone 2 (sibling) | Receives nudges and opens the board on mobile | Telegram Desktop on the laptop, still with a second number |
| Second phone number | Second Telegram account | A family member's number; they can also play the parent |
| Printed props | Mock bills, insurance letter, appointment slip, and a lab report for the guardrail scene | Print synthetic documents; never real account numbers |
| Earphone mic, quiet room | Voiceover | Phone voice recorder |
| Phone stand | Filming the photo-capture moment | A stack of books |


Recording tools: OBS Studio for the laptop screen. On Android, scrcpy mirrors the phone into the same OBS scene, so phone and board appear side by side. On iPhone, use its built-in screen recording and place it beside the board while editing.

Skip custom hardware. An ESP32 press-to-talk button for parents fits your E&TC background, but firmware, audio upload, and Wi-Fi setup are too much risk for this week. Mention it as a next step in the README instead.


### iOS, Android, and smartwatch integration

Cover both phone platforms and the watch through Telegram and an installable web board, not native apps. That costs about half a day instead of the whole remaining week.


| Option | Effort | Verdict |
| --- | --- | --- |
| Telegram bot on both platforms | Already in the plan | Keep: the parent and sibling interface on iOS and Android |
| Installable web app (PWA) for the board | 2 to 3 hours | Keep: home-screen icon on iPhone and Android, same code |
| Watch alerts through notification mirroring | 15 minutes of settings | Keep: escalations buzz the watch with no watch code |
| Native iOS and Android apps (Swift, Kotlin) | Two codebases; iPhone installs need a Mac and an Apple developer account | Cut: eats the whole week |
| Cross-platform app (Flutter, React Native) | 2 to 3 days plus push-notification build setup | Cut: judges don't score native apps |
| Native watch app (watchOS, Wear OS) | Separate UI and tooling; watchOS needs a Mac with Xcode | Cut |
| Watch health data (heart rate, falls) | Native HealthKit or Health Connect apps | Cut: medical territory the rules ban |


How to build it

- Claim button in Telegram. Every sibling nudge carries an inline Claim button. A tap sends a callback to the backend, which updates the task and the board. It works the same on iOS, Android, and Telegram Desktop.
- Watch-friendly text. Watches show only the first lines of a notification, so line one is the action and deadline, for example "Electricity bill due Fri, unclaimed".
- PWA. Add a manifest (name, 192 px and 512 px icons, standalone display), a minimal service worker, and an apple-touch-icon. Install with Chrome on Android and Safari's Add to Home Screen on iPhone. Skip web push, because Telegram already notifies.
- Watch setup. Apple Watch: in the iPhone Watch app, turn on Telegram notifications. Wear OS and budget watches (Noise, boAt, and similar): enable Telegram in the companion app's notification list.
- Demo split. Put the parent on Android and the sibling on iPhone, or the reverse, so both platforms appear naturally. The watch goes on the sibling's wrist for the escalation scene.

## README and submission checklist

The README is where judges check Technical Depth and Meta tooling, so it mirrors the rubric.

- Problem, in two sentences, with the UNFPA and LASI numbers
- Demo GIF and video link
- Architecture diagram
- Which Meta model is used where: Muse Spark, Muse Voice Transcribe, MMS-TTS, and SAM 3.1 if built
- Agent graph and the verification design (quoted evidence, code checks, confirmation pause)
- Evaluation results table
- Guardrail policy: logistics only, no medical interpretation
- What was built during the event (required by the rules)
- Setup and run steps (one command: docker compose up)
- Limitations and next steps (WhatsApp channel, more languages, and a commercially licensed voice model, because MMS-TTS is CC-BY-NC)
Before submitting

- ☐ Repo is public
- ☐ Commit history starts on or after Oct 27
- ☐ Video is 3:00 or less and uploaded
- ☐ Track selected: Build for Your World
- ☐ Credits claimed before the deadline
- ☐ No real family documents or secrets anywhere in the repo history

## Cut list if behind

Cut in this order, without guilt:

- Local helper role, then voice status questions, then appointment reminders, then MMS-TTS voice (fall back to recorded clips), then PWA install (the board still works in a mobile browser)
- Call scripts (keep the Marathi reply and sibling nudge)
- Recurring-task detection
- Escalation scheduler (replace with a "simulate 3 days later" button)
Never cut: quoted-text evidence, the confirmation pause, the medical guardrail, the 30-day total, done confirmations to parents, and the evaluation table. These are what make Saath more than a basic document-reading app.
