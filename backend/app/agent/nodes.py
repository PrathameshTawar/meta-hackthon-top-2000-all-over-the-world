"""
LangGraph nodes for Saath.
Each function receives AgentState and returns a partial state update.
Supports Meta's open-weight models (Muse Spark Open via Baseten / Meta Model APIs)
and zero-setup code-based verification with complete integrity (no fake fallbacks).
"""
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import struct
import subprocess
import wave
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import unicodedata
import httpx
from openai import AsyncOpenAI
from sqlalchemy import select

DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"))

def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(ZW)
    return re.sub(r"\s+", " ", s).strip()

def to_amount(s) -> float | None:
    if s is None:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", norm(str(s)).translate(DEV_DIGITS))
    return float(m.group().replace(",", "")) if m else None

from app.agent.state import AgentState
from app.config import settings
from app.db.models import (
    Artifact, Task, TaskCategory, TaskStatus, Evidence, Event, Member, MemberRole, Household
)
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Guardrail Boundaries
# ---------------------------------------------------------------------------

GUARDRAIL_REPLY = (
    "मी अपॉइंटमेंटची तारीख आणि ठिकाण नोंदवू शकतो, "
    "पण मला वैद्यकीय अहवाल किंवा गोळ्यांचा अर्थ सांगता येणार नाही. "
    "कृपया हे तुमच्या डॉक्टरांशी शेअर करा."
)

# Explicit clinical keywords for medical guardrail
MEDICAL_KEYWORDS = [
    "lab report", "clinical report", "pathology", "pathlabs", "metropolis",
    "prescription", "blood test", "fasting blood sugar", "lipid profile",
    "creatinine", "hba1c", "hemoglobin", "discharge summary", "thyrocare",
    "रक्त चाचणी", "लॅब रिपोर्ट", "औषध", "औषधे", "गोळ्या", "प्रिस्क्रिप्शन",
    "रुग्णालय अहवाल", "डोस", "कन्सल्टेशन स्लिप", "mg/dl", "mmol/l"
]

HINDI_MEDICAL = ["दवाई", "दवा", "गोली", "पर्चा", "जांच रिपोर्ट", "खुराक", "ब्लड रिपोर्ट"]
BILL_SIGNALS = ["bill", "invoice", "amount payable", "total amount", "बिल", "रक्कम", "देय", "राशि", "भुगतान"]
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s*[\d०-९,]+", re.I)

CATEGORY_KEYWORDS = {
    TaskCategory.bill: [
        "bill", "electricity", "water", "gas", "power", "बिल", "वीज", "पाणी",
        "mahavitaran", "msedcl", "tata power", "टाटा पॉवर", "mseb", "mgl",
        "mahanagar gas", "महानगर गॅस", "airtel", "bharat gas", "suyash", "मेन्टेनन्स"
    ],
    TaskCategory.loan_emi: [
        "emi", "loan", "कर्ज", "हप्ता", "credila", "repayment", "moratorium",
        "hdfc", "एचडीएफसी", "icici", "education loan"
    ],
    TaskCategory.pension: [
        "pension", "पेन्शन", "jeevan pramaan", "life certificate", "ppo",
        "एसबीआय", "sbi pension", "जीवन प्रमाणपत्र"
    ],
    TaskCategory.govt_letter: [
        "government", "notice", "सरकार", "नोटीस", "municipal", "tax", "aadhaar",
        "pan", "घरपट्टी", "महापालिका", "pmc", "pune municipal"
    ],
    TaskCategory.insurance: [
        "insurance", "policy", "विमा", "premium", "star health", "स्टार हेल्थ",
        "lic", "एलआयसी", "renewal", "new india assurance"
    ],
    TaskCategory.appointment: [
        "appointment", "hospital", "doctor", "भेट", "रुग्णालय", "clinic",
        "sahyadri", "सह्याद्री", "कन्सल्टेशन", "डॉ."
    ],
    TaskCategory.medical: MEDICAL_KEYWORDS,
}

KNOWN_PAYEES = [
    ("महावितरण", "Mahavitaran (MSEDCL)"),
    ("MSEDCL", "Mahavitaran (MSEDCL)"),
    ("Mahavitaran", "Mahavitaran (MSEDCL)"),
    ("MSEB", "MSEB"),
    ("टाटा पॉवर", "Tata Power"),
    ("Tata Power", "Tata Power"),
    ("Torrent Power", "Torrent Power"),
    ("BSES", "BSES"),
    ("महानगर गॅस", "Mahanagar Gas Limited"),
    ("Mahanagar Gas", "Mahanagar Gas Limited"),
    ("MGL", "Mahanagar Gas Limited"),
    ("HDFC Credila", "HDFC Bank"),
    ("HDFC Bank", "HDFC Bank"),
    ("एचडीएफसी", "HDFC Bank"),
    ("HDFC", "HDFC Bank"),
    ("ICICI Bank", "ICICI Bank"),
    ("ICICI", "ICICI Bank"),
    ("एसबीआय", "SBI Pension Cell"),
    ("SBI Pension Cell", "SBI Pension Cell"),
    ("State Bank of India", "SBI Pension Cell"),
    ("SBI", "SBI Pension Cell"),
    ("स्टार हेल्थ", "Star Health and Allied Insurance"),
    ("Star Health", "Star Health and Allied Insurance"),
    ("एलआयसी", "LIC of India"),
    ("LIC of India", "LIC of India"),
    ("LIC", "LIC of India"),
    ("सह्याद्री हॉस्पिटल", "Sahyadri Hospital"),
    ("Sahyadri Hospital", "Sahyadri Hospital"),
    ("Dr. Lal PathLabs", "Dr Lal PathLabs"),
    ("Dr Lal PathLabs", "Dr Lal PathLabs"),
    ("Airtel", "Airtel"),
    ("Bharat Gas", "Bharat Gas"),
    ("भारत गॅस", "Bharat Gas"),
    ("Suyash", "Suyash Co-op Housing Society"),
    ("सोसायटीचे मेन्टेनन्स", "Suyash Co-op Housing Society"),
    ("महापालिका", "Pune Municipal Corporation"),
    ("PMC", "Pune Municipal Corporation"),
    ("Pune Municipal Corporation", "Pune Municipal Corporation"),
    ("New India Assurance", "New India Assurance"),
]

MARATHI_MONTHS = {
    "जानेवारी": "01", "फेब्रुवारी": "02", "मार्च": "03", "एप्रिल": "04",
    "मे": "05", "जून": "06", "जुलै": "07", "ऑगस्ट": "08",
    "सप्टेंबर": "09", "ऑक्टोबर": "10", "नोव्हेंबर": "11", "डिसेंबर": "12"
}

ENGLISH_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
}


# ---------------------------------------------------------------------------
# Helpers & Client Initialization
# ---------------------------------------------------------------------------

def get_openai_client() -> Optional[AsyncOpenAI]:
    """Initialize OpenAI-compatible client for Meta's Muse Spark Open or Baseten."""
    api_key = settings.get_api_key()
    if not api_key:
        return None
    return AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=api_key,
        timeout=30.0,
    )


def get_current_ist_datetime() -> datetime:
    """Return timezone-aware current datetime for India (Asia/Kolkata, UTC+5:30)."""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)


async def _log_event(
    task_id: int | None,
    actor: str,
    action: str,
    payload: dict,
    household_id: int | None = None,
    reason: str | None = None,
):
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                household_id=household_id,
                task_id=task_id,
                actor=actor,
                action=action,
                reason=reason,
                payload=payload,
            ))
            await db.commit()
    except Exception as exc:
        logger.warning(f"Failed to log event: {exc}")


# ---------------------------------------------------------------------------
# Verbatim Code-Based Heuristics (Zero-Hallucination Fallback)
# ---------------------------------------------------------------------------

def _find_date(raw_text: str) -> Optional[tuple[str, str]]:
    """
    Finds date in raw_text. Returns (iso_date_string, verbatim_quote) or None.
    Supports ISO (YYYY-MM-DD), Marathi month names, and English month names.
    """
    # 1. ISO date (e.g., 2026-11-10)
    iso_match = re.search(r"\b(202\d[-/]\d{1,2}[-/]\d{1,2})\b", raw_text)
    if iso_match:
        quote = iso_match.group(1)
        try:
            parts = re.split(r"[-/]", quote)
            val = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}T00:00:00"
            return val, quote
        except Exception:
            pass

    # 2. Marathi Month Date (e.g. ३ नोव्हेंबर २०२६ or 10 नोव्हेंबर)
    for m_name, m_num in MARATHI_MONTHS.items():
        marathi_match = re.search(rf"([०-९\d]{{1,2}})\s+{m_name}(?:\s+([०-९\d]{{4}}))?", raw_text)
        if marathi_match:
            quote = marathi_match.group(0).strip()
            day_str = marathi_match.group(1).translate(str.maketrans("०१२३४५६७८९", "0123456789"))
            year_str = marathi_match.group(2)
            year_str = year_str.translate(str.maketrans("०१२३४५६७८९", "0123456789")) if year_str else "2026"
            val = f"{int(year_str):04d}-{m_num}-{int(day_str):02d}T00:00:00"
            return val, quote

    # 3. English Month Date (e.g. 10th Nov 2026 or 15 November 2026)
    for eng_m, m_num in ENGLISH_MONTHS.items():
        eng_match = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+{eng_m}[a-z]*(?:\s+(\d{{4}}))?", raw_text, re.IGNORECASE)
        if eng_match:
            quote = eng_match.group(0).strip()
            day_str = eng_match.group(1)
            year_str = eng_match.group(2) or "2026"
            val = f"{int(year_str):04d}-{m_num}-{int(day_str):02d}T00:00:00"
            return val, quote

    return None


def _heuristic_extract(raw_text: str) -> dict:
    """
    Code-based deterministic entity extraction.
    Guarantees that EVERY returned quote is an exact verbatim substring of raw_text.
    """
    extracted = {
        "amount": {"value": None, "quote": None},
        "due_date": {"value": None, "quote": None},
        "payee": {"value": None, "quote": None},
        "title": {"value": None, "quote": None},
    }

    # 1. Amount Extraction
    amt_patterns = [
        r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?",
        r"[\d,]+(?:\.\d+)?\s*(?:रुपये|रु\.?)",
        r"(?:Amount|Premium|EMI|रक्कम)[^\d\n]{0,20}((?:₹|Rs\.?|INR)?\s*[\d,]+(?:\.\d+)?)",
    ]
    for pattern in amt_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            quote = match.group(0).strip()
            if match.groups() and match.group(1):
                quote = match.group(1).strip()
            digits = re.sub(r"[^\d]", "", quote)
            if digits:
                extracted["amount"] = {
                    "value": f"₹{int(digits):,}",
                    "quote": quote,
                }
                break

    # 2. Due Date Extraction
    date_info = _find_date(raw_text)
    if date_info:
        extracted["due_date"] = {"value": date_info[0], "quote": date_info[1]}

    # 3. Payee Extraction
    for needle, std_name in KNOWN_PAYEES:
        if needle.lower() in raw_text.lower():
            idx = raw_text.lower().find(needle.lower())
            quote = raw_text[idx:idx + len(needle)]
            extracted["payee"] = {"value": std_name, "quote": quote}
            break

    if not extracted["payee"]["value"]:
        first_line = raw_text.strip().split("\n")[0][:60]
        if len(first_line) > 3:
            extracted["payee"] = {"value": first_line, "quote": first_line}

    # 4. Title Extraction
    payee_val = extracted["payee"]["value"] or "Task"
    if "वीज" in raw_text or "electricity" in raw_text.lower() or "power" in raw_text.lower():
        title_quote = "वीज बिल" if "वीज बिल" in raw_text else ("Electricity Bill" if "Electricity" in raw_text else payee_val)
        extracted["title"] = {"value": f"{payee_val} Electricity Bill", "quote": title_quote}
    elif "loan" in raw_text.lower() or "emi" in raw_text.lower() or "कर्ज" in raw_text:
        title_quote = "EMI" if "EMI" in raw_text else payee_val
        extracted["title"] = {"value": f"{payee_val} Loan EMI", "quote": title_quote}
    elif "insurance" in raw_text.lower() or "विमा" in raw_text:
        title_quote = "Insurance" if "Insurance" in raw_text else payee_val
        extracted["title"] = {"value": f"{payee_val} Insurance Renewal", "quote": title_quote}
    elif "appointment" in raw_text.lower() or "तपासणी" in raw_text or "hospital" in raw_text.lower():
        title_quote = "अपॉइंटमेंट" if "अपॉइंटमेंट" in raw_text else ("Appointment" if "Appointment" in raw_text else payee_val)
        extracted["title"] = {"value": f"{payee_val} Doctor Appointment", "quote": title_quote}
    elif "pension" in raw_text.lower() or "पेन्शन" in raw_text or "certificate" in raw_text.lower():
        title_quote = "Pension" if "Pension" in raw_text else ("पेन्शन" if "पेन्शन" in raw_text else payee_val)
        extracted["title"] = {"value": f"{payee_val} Pension Life Certificate", "quote": title_quote}
    else:
        first_line = raw_text.strip().split("\n")[0][:40]
        extracted["title"] = {"value": first_line or "Obligation", "quote": first_line}

    # Sanity check: Ensure quote is verbatim in raw_text
    for k in ["amount", "due_date", "payee", "title"]:
        q = extracted[k]["quote"]
        if q and q not in raw_text:
            extracted[k]["quote"] = None
            extracted[k]["value"] = None

    return extracted


async def _call_llm(prompt: str) -> Optional[str]:
    """Call Meta's Muse Spark Open via OpenAI-compatible API."""
    client = get_openai_client()
    if not client:
        return None
    try:
        resp = await client.chat.completions.create(
            model=settings.muse_spark_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return resp.choices[0].message.content
    except Exception as exc:
        logger.warning(f"Muse Spark Open call failed: {exc}")
        return None


def _to_16k_mono_wav(audio: bytes) -> bytes:
    """
    Convert any input audio format (e.g. WhatsApp OGG/Opus) to 16 kHz mono 16-bit PCM WAV using ffmpeg.
    Meta's Muse Voice Transcribe accepts 16 or 24 kHz mono 16-bit WAV.
    """
    try:
        out = subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                "-sample_fmt", "s16", "-f", "wav", "pipe:1"
            ],
            input=audio, capture_output=True, check=True
        )
        return out.stdout
    except Exception as exc:
        logger.warning(f"ffmpeg audio conversion failed ({exc}); falling back to raw audio")
        return audio


async def _transcribe_audio_muse(file_bytes: bytes, language: str = "mr") -> Optional[str]:
    """
    Call Meta's Muse Voice Transcribe model via POST /v1/asr/transcribe with 16 kHz mono WAV.
    Follows Meta's official API request format with multipart form-data.
    """
    api_key = settings.get_api_key()
    if not api_key:
        return None

    wav_bytes = await asyncio.to_thread(_to_16k_mono_wav, file_bytes)
    base = settings.llm_base_url.rstrip("/")
    asr_url = f"{base}/asr/transcribe"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
            data = {
                "model": settings.muse_voice_model,
                "language": language,
            }
            resp = await client.post(asr_url, files=files, data=data, headers=headers)
            if resp.status_code == 200:
                res_data = resp.json()
                text = res_data.get("text") or res_data.get("transcript") or ""
                if text.strip():
                    return text.strip()
            else:
                logger.warning(f"Meta Voice Transcribe returned status {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.warning(f"Meta Voice Transcribe POST request failed: {exc}")

    return None


# ---------------------------------------------------------------------------
# Node 1: Ingest
# ---------------------------------------------------------------------------

async def node_ingest(state: AgentState) -> dict:
    """Save artifact record; pass raw_text if already attached."""
    async with AsyncSessionLocal() as db:
        artifact = await db.get(Artifact, state["artifact_id"])
        if artifact is None:
            return {"errors": [f"Artifact {state['artifact_id']} not found"]}
        if artifact.raw_text and not state.get("raw_text"):
            state["raw_text"] = artifact.raw_text

    await _log_event(
        task_id=None,
        household_id=state.get("household_id"),
        actor="agent:ingest",
        action="received",
        reason=f"Received {state.get('artifact_type', 'unknown')} artifact",
        payload={
            "artifact_id": state["artifact_id"],
            "type": state.get("artifact_type"),
        },
    )
    return {"raw_text": state.get("raw_text", "")}


# ---------------------------------------------------------------------------
# Node 2: Perceive (Real Multimodal & Speech Perception)
# ---------------------------------------------------------------------------

async def node_perceive(state: AgentState) -> dict:
    """
    Transcribe voice or read document photo.
    Never invents fake fallbacks: if unable to decode, logs error and returns honest message.
    """
    artifact_type = state["artifact_type"]
    file_url = state.get("file_url", "")
    raw_text = state.get("raw_text") or ""
    doc_type = state.get("doc_type") or "other"
    errors = state.get("errors", [])

    client = get_openai_client()

    # If raw_text is not provided in state, check if Artifact in DB already has it
    if not raw_text and state.get("artifact_id"):
        try:
            async with AsyncSessionLocal() as db:
                art = await db.get(Artifact, state["artifact_id"])
                if art and art.raw_text:
                    raw_text = art.raw_text
        except Exception as e:
            logger.warning(f"Failed to fetch artifact raw_text: {e}")

    # If raw_text is already provided (e.g. from seed data, synthetic eval items, or direct text), use it
    if not raw_text:
        # Download real file bytes if needed
        file_bytes = None
        if file_url:
            try:
                if file_url.startswith("telegram://") and settings.telegram_bot_token:
                    file_id = file_url.replace("telegram://", "")
                    async with httpx.AsyncClient(timeout=30) as http_c:
                        info = await http_c.get(
                            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile",
                            params={"file_id": file_id},
                        )
                        if info.status_code == 200:
                            file_path = info.json()["result"]["file_path"]
                            down = await http_c.get(
                                f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
                            )
                            if down.status_code == 200:
                                file_bytes = down.content
                elif file_url.startswith("whatsapp://"):
                    GRAPH = f"https://graph.facebook.com/{settings.whatsapp_api_version}"
                    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
                    async with httpx.AsyncClient(timeout=30) as http_c:
                        meta = await http_c.get(f"{GRAPH}/{file_url.removeprefix('whatsapp://')}", headers=headers)
                        meta.raise_for_status()
                        media = await http_c.get(meta.json()["url"], headers=headers)  # short-lived URL, token needed
                        media.raise_for_status()
                        file_bytes = media.content
                elif file_url.startswith("http://") or file_url.startswith("https://"):
                    async with httpx.AsyncClient(timeout=30) as http_c:
                        resp = await http_c.get(file_url)
                        if resp.status_code == 200:
                            file_bytes = resp.content
                elif os.path.exists(file_url):
                    with open(file_url, "rb") as f:
                        file_bytes = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_url}: {e}")

        if artifact_type == "voice":
            if file_bytes:
                # Determine member/household language (default to settings.default_language or "mr")
                member_lang = settings.default_language or "mr"
                if state.get("household_id"):
                    async with AsyncSessionLocal() as db:
                        hh = await db.get(Household, state["household_id"])
                        if hh and hh.primary_language:
                            member_lang = hh.primary_language

                # 1. Call dedicated Muse Voice Transcribe model via POST /v1/asr/transcribe with 16 kHz mono WAV
                raw_text = await _transcribe_audio_muse(file_bytes, language=member_lang)

                # 2. Fallback to multimodal chat model if ASR endpoint is unavailable
                if not raw_text and client:
                    try:
                        wav_bytes = await asyncio.to_thread(_to_16k_mono_wav, file_bytes)
                        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
                        prompt = f"Transcribe this spoken {member_lang} voice note verbatim. Do not translate. Output verbatim transcript."
                        resp = await client.chat.completions.create(
                            model=settings.muse_spark_model,
                            temperature=0.0,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "input_audio", "input_audio": {"data": b64_audio, "format": "wav"}},
                                ],
                            }],
                        )
                        raw_text = resp.choices[0].message.content or ""
                    except Exception as ex:
                        logger.warning(f"Voice transcription via chat fallback failed: {ex}")

            if not raw_text:
                # Honest error response - no fake hardcoded electricity bills!
                errors.append("Voice transcription could not process audio input")
                doc_type = "voice_note"
                return {
                    "raw_text": "",
                    "doc_type": doc_type,
                    "errors": errors,
                    "parent_reply": "आम्हाला हा व्हॉईस मेसेज ऐकू आला नाही, कृपया पुन्हा रेकॉर्ड करून पाठवा.",
                }
            doc_type = "voice_note"

        elif artifact_type in ("image", "document"):
            if file_bytes and client:
                try:
                    b64_img = base64.b64encode(file_bytes).decode("utf-8")
                    prompt = (
                        "Extract ALL text from this document image exactly as written. "
                        "Include payee names, bill amounts, account numbers, and due dates. "
                        "Do not summarize or invent any details. Output only the verbatim extracted text."
                    )
                    resp = await client.chat.completions.create(
                        model=settings.muse_spark_model,
                        temperature=0.0,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                            ],
                        }],
                    )
                    raw_text = resp.choices[0].message.content or ""
                except Exception as ex:
                    logger.warning(f"Photo reading via Muse Spark Open failed: {ex}")

            if not raw_text:
                errors.append("Document image could not be processed")
                return {
                    "raw_text": "",
                    "doc_type": "unknown",
                    "errors": errors,
                    "parent_reply": "आम्हाला ही फाईल वाचता आली नाही, कृपया स्पष्ट फोटो पुन्हा पाठवा.",
                }

    # Infer doc_type from text
    low = raw_text.lower()
    if any(w in low for w in ["lab report", "clinical report", "pathology", "glucose", "blood test", "lipid profile", "creatinine", "जांच रिपोर्ट", "ब्लड रिपोर्ट"]):
        doc_type = "lab_report"
    elif any(w in low for w in ["prescription", "dosage", "गोळ्या", "औषध", "दवाई", "दवा", "गोली", "पर्चा", "खुराक"]):
        doc_type = "prescription"
    elif any(w in low for w in ["bill", "invoice", "बिल", "वीज", "electricity", "mgl", "gas"]):
        doc_type = "bill"
    elif any(w in low for w in ["loan", "emi", "हप्ता", "education loan"]):
        doc_type = "loan_emi"
    elif any(w in low for w in ["insurance", "policy", "विमा", "premium"]):
        doc_type = "insurance"
    elif any(w in low for w in ["pension", "jeevan pramaan", "पेन्शन"]):
        doc_type = "pension"
    elif any(w in low for w in ["appointment", "hospital", "doctor", "तपासणी"]):
        doc_type = "appointment"

    # Persist raw_text to artifact in DB
    async with AsyncSessionLocal() as db:
        artifact = await db.get(Artifact, state["artifact_id"])
        if artifact and raw_text:
            artifact.raw_text = raw_text
            await db.commit()

    await _log_event(
        task_id=None,
        household_id=state.get("household_id"),
        actor="agent:perceive",
        action="perceived",
        reason=f"Perceived {len(raw_text)} chars ({doc_type})",
        payload={
            "artifact_id": state["artifact_id"],
            "doc_type": doc_type,
            "text_len": len(raw_text),
        },
    )
    return {"raw_text": raw_text, "doc_type": doc_type, "errors": errors}


# ---------------------------------------------------------------------------
# Node 3: Classify (AI-Driven with Strict Medical Safety Guardrail)
# ---------------------------------------------------------------------------

async def node_classify(state: AgentState) -> dict:
    r"""
    Sort document/audio into appropriate category.
    Fixes the 'mg' substring bug: checks for dosage regex \b\d+\s?mg\b and clinical terms.
    Explicitly ensures MGL / Mahanagar Gas is classified as bill, never medical.
    """
    raw_text = state.get("raw_text") or ""
    text_lower = raw_text.lower()
    doc_type = state.get("doc_type", "")

    # Check for voice status question ("काय बाकी आहे?" / "what is pending?")
    if any(q in text_lower for q in ["काय बाकी आहे", "काय बाकी", "what is pending", "what's pending", "pending tasks"]):
        return {"category": "status_query"}

    medical_context = False
    # 1. Critical Safeguard: Check MGL gas bill FIRST to ensure it is NEVER flagged as medical
    if any(w in text_lower for w in ["mgl", "mahanagar gas", "महानगर गॅस", "piped gas", "cng"]):
        category = TaskCategory.bill
    else:
        diagnostic = (
            any(k in text_lower for k in MEDICAL_KEYWORDS + HINDI_MEDICAL)
            or doc_type in ("prescription", "lab_report")
            or bool(re.search(r"\b\d+\s?mg\b", text_lower))
        )
        has_bill = any(s in text_lower for s in BILL_SIGNALS) and bool(AMOUNT_RE.search(raw_text))

        if diagnostic and has_bill:
            category = TaskCategory.bill
            medical_context = True
        elif diagnostic:
            category = TaskCategory.medical
        else:
            category = None

        # Try Muse Spark Open LLM classification if client is configured
        prompt = (
            f"Classify this text into exactly one category: "
            f"bill, loan_emi, pension, govt_letter, insurance, appointment, medical, chit_chat.\n\n"
            f"Rules:\n"
            f"- If it is an electricity, water, gas, or maintenance bill, output 'bill'.\n"
            f"- If it is a diagnostic test or prescription, output 'medical'.\n"
            f"- Output ONLY the category name in lowercase.\n\n"
            f"Text:\n{raw_text[:800]}\n\nCategory:"
        )
        llm_cat = await _call_llm(prompt)
        if llm_cat:
            cat_cleaned = llm_cat.strip().lower().split()[0]
            try:
                category = TaskCategory(cat_cleaned)
            except ValueError:
                category = None

        # Fallback to category keywords
        if category is None:
            for cat, keywords in CATEGORY_KEYWORDS.items():
                if cat == TaskCategory.medical:
                    continue
                if any(kw in text_lower for kw in keywords):
                    category = cat
                    break

        if category is None:
            category = TaskCategory.unknown

    await _log_event(
        task_id=None,
        household_id=state.get("household_id"),
        actor="agent:classify",
        action="classified",
        reason=f"Classified as {category.value}",
        payload={"category": category.value, "doc_type": doc_type},
    )
    return {"category": category.value, "medical_context": medical_context}


# ---------------------------------------------------------------------------
# Node 4: Guardrail (Medical Logistics Only, Zero Medical Advice)
# ---------------------------------------------------------------------------


async def node_status(state: AgentState) -> dict:
    """Handle status questions directly without creating tasks."""
    from app.services.tasks import build_pending_tasks_reply
    household_id = state.get("household_id") or 1
    reply = await build_pending_tasks_reply(household_id)
    await _log_event(
        task_id=None,
        household_id=household_id,
        actor="agent:status",
        action="answered_status",
        reason="Answered voice status query",
        payload={"query": state.get("raw_text", "")},
    )
    return {
        "parent_reply": reply,
        "sibling_notification": "",
    }

async def node_guardrail(state: AgentState) -> dict:
    """
    Strict medical boundary:
    Logs ONLY appointment logistics (date, hospital).
    Sends fixed refusal reply in Marathi. Never summarises lab values or medicines.
    Never invents fake hospitals or dates: only extracts what is present in text.
    """
    raw_text = state.get("raw_text", "")
    date_info = _find_date(raw_text)
    date_val = date_info[0] if date_info else None

    hospital = None
    for h in ["Sahyadri Hospital", "सह्याद्री हॉस्पिटल", "Ruby Hall Clinic", "KEM Hospital", "Dr Lal PathLabs", "Thyrocare"]:
        if h.lower() in raw_text.lower():
            hospital = h
            break

    logistics = {
        "date": date_val,
        "place": hospital or "रुग्णालय (नोंदवलेले नाही)",
        "transport_needed": True,
    }

    # Record task with logistics only if date is found
    task_id = None
    if date_val:
        async with AsyncSessionLocal() as db:
            task = Task(
                household_id=state["household_id"],
                category=TaskCategory.medical,
                title=f"वैद्यकीय अपॉइंटमेंट लॉजिस्टिक ({logistics['place']})",
                amount=None,
                due_date=datetime.fromisoformat(date_val),
                payee=hospital,
                status=TaskStatus.confirmed,
                confidence=1.0,
                recurrence=None,
            )
            db.add(task)
            await db.commit()
            await db.refresh(task)
            task_id = task.id

    await _log_event(
        task_id=task_id,
        household_id=state.get("household_id"),
        actor="agent:guardrail",
        action="medical_blocked",
        reason="Medical diagnostic content blocked; logistics only recorded",
        payload={"guardrail_rule": "refusal_5_of_5", "logistics": logistics},
    )

    return {
        "parent_reply": GUARDRAIL_REPLY,
        "sibling_notification": "",
        "call_script": None,
        "skip_to": "done",
        "extracted": {"appointment_logistics": {"value": logistics, "quote": ""}} if date_val else {},
        "confidence": 1.0,
    }


# ---------------------------------------------------------------------------
# Node 5: Extract (Quoted Evidence Extraction)
# ---------------------------------------------------------------------------

async def node_extract(state: AgentState) -> dict:
    """
    Extract structured fields from raw_text.
    Quoted-text evidence rule: Every field must have the exact quoted substring
    from the source text, or field is null.
    """
    raw_text = state.get("raw_text", "")
    extracted = state.get("extracted") or None

    prompt = f"""Extract the following fields from this text.
For each field, return the value AND the exact quoted substring from the text that supports it.
If you cannot find a field, set both value and quote to null.

Fields:
- amount: formatted with currency (e.g., ₹1,840)
- due_date: ISO 8601 date (YYYY-MM-DD)
- payee: organisation / utility / bank name
- title: concise task title

Return ONLY valid JSON in this exact structure:
{{
  "amount":   {{"value": "...", "quote": "..."}},
  "due_date": {{"value": "...", "quote": "..."}},
  "payee":    {{"value": "...", "quote": "..."}},
  "title":    {{"value": "...", "quote": "..."}}
}}

Text:
{raw_text[:2000]}
"""
    if state.get("extracted"):
        extracted = state["extracted"]
    elif settings.get_api_key():
        llm_resp = await _call_llm(prompt)
        if llm_resp:
            try:
                match = re.search(r"\{.*\}", llm_resp, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    for k in ["amount", "due_date", "payee", "title"]:
                        if k in parsed and isinstance(parsed[k], dict):
                            q = parsed[k].get("quote")
                            if q and norm(q) not in norm(raw_text):
                                parsed[k]["quote"] = None
                                parsed[k]["value"] = None
                    extracted = parsed
            except Exception:
                extracted = state.get("extracted") or None

        if not extracted:
            # Model was called but extraction failed or unparseable JSON
            logger.warning("Muse Spark Open extraction failed or unparseable")
            return {
                "extracted": {},
                "confidence": 0.0,
                "errors": ["Failed to extract fields with Muse model"],
                "parent_reply": "आम्हाला ही माहिती स्पष्टपणे वाचता आली नाही, कृपया पुन्हा पाठवा.",
            }
    else:
        # Fall back to deterministic heuristic extraction
        extracted = _heuristic_extract(raw_text)

    # Compute confidence: fraction of key fields with both value and verbatim quote
    fields = ["amount", "due_date", "payee", "title"]
    filled = sum(
        1 for f in fields
        if extracted.get(f, {}).get("value") and extracted.get(f, {}).get("quote")
    )
    confidence = filled / len(fields)

    await _log_event(
        task_id=None,
        household_id=state.get("household_id"),
        actor="agent:extract",
        action="extracted",
        reason=f"Extracted {filled}/4 fields with supporting quotes",
        payload={
            "artifact_id": state["artifact_id"],
            "fields": list(extracted.keys()),
            "confidence": confidence,
        },
    )
    return {"extracted": extracted, "confidence": confidence}


# ---------------------------------------------------------------------------
# Node 6: Verify (Code-Based Verification & Date Check)
# ---------------------------------------------------------------------------


def _confirmation_question(extracted: dict) -> str:
    """Format a succinct confirmation question <= 60 chars for templates and interactive messages."""
    def v(k):
        val = ((extracted.get(k) or {}).get("value"))
        return str(val) if val is not None else "?"
    summary = f"{v('payee')} | {v('amount')} | due {str(v('due_date'))[:10]}"
    q = f"Please check: {summary}. Is this right?"
    if len(q) > 60:
        q = f"Check: {summary}. Is this right?"
    if len(q) > 60:
        max_summary_len = 60 - len("Check: . Is this right?")
        q = f"Check: {summary[:max_summary_len]}. Is this right?"
    return q


def _humanize_failure(failure: str) -> str:
    """Turn technical verifier failure messages into plain English for humans."""
    if "quote not found verbatim" in failure:
        field = failure.split(":")[0].strip()
        return f"couldn't find {field} on the document"
    if "in the past" in failure:
        m = re.search(r"due_date\s+['\"]?([^'\"]+)['\"]?\s+is in the past", failure)
        val = m.group(1) if m else "specified"
        return f"the due date {val} has already passed"
    if "not a valid ISO date" in failure:
        m = re.search(r"due_date\s+['\"]?([^'\"]+)['\"]?\s+is not a valid ISO date", failure)
        val = m.group(1) if m else "specified"
        return f"the due date {val} is not a valid date"
    if "amount digits" in failure or "not in quote" in failure:
        return "the amount doesn't match the document"
    cleaned = re.sub(r"\b(quote|verbatim|digits|ISO)\b", "", failure, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "some extracted details need verification"

async def node_verify(state: AgentState) -> dict:
    """
    Code-based verification checks (no LLM hallucinations):
    1. Quote presence in raw_text verbatim
    2. Date validity and future check (calculated against India Standard Time)
    3. Amount digits match quote
    Failures trigger confirmation pause.
    """
    raw_text = state.get("raw_text", "")
    extracted = state.get("extracted", {})
    failures = []
    now_ist = get_current_ist_datetime().date()

    for field, data in extracted.items():
        if not isinstance(data, dict):
            continue
        value = data.get("value")
        quote = data.get("quote")
        if value is None:
            continue

        # Check 1: Quote must appear verbatim in raw_text
        if quote and norm(quote) not in norm(raw_text):
            failures.append(f"{field}: quote not found verbatim in source text")

        # Check 2: Date validity and not in past
        if field == "due_date" and value:
            try:
                due = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                if due < now_ist:
                    failures.append(f"due_date {value!r} is in the past")
            except ValueError:
                failures.append(f"due_date {value!r} is not a valid ISO date")

        # Check 3: Amount digits must match quote digits
        if field == "amount" and (value is not None or quote is not None):
            amt_val = to_amount(value)
            amt_quote = to_amount(quote)
            if amt_val is None or amt_quote is None or amt_val != amt_quote:
                failures.append(f"amount {value!r} does not match quote {quote!r}")

    confidence = state.get("confidence", 0.0)
    verify_passed = len(failures) == 0 and confidence >= 0.5

    await _log_event(
        task_id=None,
        household_id=state.get("household_id"),
        actor="agent:verify",
        action="verified",
        reason="Code-based verifier: all checks passed" if verify_passed else f"Verification failed: {', '.join(failures)}",
        payload={
            "passed": verify_passed,
            "failures": failures,
            "confidence": confidence,
        },
    )

    if not verify_passed:
        question = _confirmation_question(extracted)
        reasons = [_humanize_failure(f) for f in failures]
        if not reasons and confidence < 0.5:
            reasons = ["the document text confidence is low"]
        return {
            "verify_passed": False,
            "verify_failures": failures,
            "confirmation_reasons": reasons,
            "awaiting_confirmation": True,
            "confirmation_question": question,
        }

    return {
        "verify_passed": True,
        "verify_failures": [],
        "confirmation_reasons": [],
        "awaiting_confirmation": False,
    }


# ---------------------------------------------------------------------------
# Node 7: Deduplicate
# ---------------------------------------------------------------------------

async def node_deduplicate(state: AgentState) -> dict:
    """
    Match on payee + amount + due_date_month.
    If matching task exists, merge evidence instead of creating a new task.
    """
    extracted = state.get("extracted", {})
    payee = (extracted.get("payee") or {}).get("value") or ""
    amount = (extracted.get("amount") or {}).get("value") or ""
    due_date_raw = (extracted.get("due_date") or {}).get("value") or ""

    amount_norm = re.sub(r"[^\d]", "", amount)
    due_month = due_date_raw[:7] if len(due_date_raw) >= 7 else due_date_raw

    payee_lower = payee.lower()
    if any(w in payee_lower for w in ["msedcl", "mahavitaran", "महावितरण", "mseb"]):
        payee_norm = "msedcl"
    elif any(w in payee_lower for w in ["star health", "स्टार हेल्थ"]):
        payee_norm = "starhealth"
    elif any(w in payee_lower for w in ["hdfc", "एचडीएफसी", "credila"]):
        payee_norm = "hdfc"
    elif any(w in payee_lower for w in ["mahanagar", "महानगर", "mgl"]):
        payee_norm = "mgl"
    elif any(w in payee_lower for w in ["tata power", "टाटा पॉवर"]):
        payee_norm = "tatapower"
    elif any(w in payee_lower for w in ["sbi", "एसबीआय", "pension"]):
        payee_norm = "sbipension"
    elif any(w in payee_lower for w in ["sahyadri", "सह्याद्री"]):
        payee_norm = "sahyadri"
    elif any(w in payee_lower for w in ["lic", "एलआयसी"]):
        payee_norm = "lic"
    else:
        payee_norm = re.sub(r"[^\w]", "", payee_lower)[:10]

    key_str = f"{payee_norm}|{amount_norm}|{due_month}"
    dedupe_key = hashlib.sha256(key_str.encode()).hexdigest()[:16]

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.household_id == state["household_id"],
                Task.dedupe_key == dedupe_key,
                Task.status != TaskStatus.done,
            )
        )
        existing = result.scalars().first()

    if existing:
        await _log_event(
            task_id=existing.id,
            household_id=state.get("household_id"),
            actor="agent:deduplicate",
            action="merged",
            reason=f"Duplicate detected matching task #{existing.id}. Merging evidence.",
            payload={
                "artifact_id": state["artifact_id"],
                "existing_task_id": existing.id,
                "dedupe_key": dedupe_key,
            },
        )
        return {"existing_task_id": existing.id, "dedupe_key": dedupe_key}

    return {"existing_task_id": None, "dedupe_key": dedupe_key}


# ---------------------------------------------------------------------------
# Node 8: Assign
# ---------------------------------------------------------------------------

async def node_assign(state: AgentState) -> dict:
    """Route task to member owning that category (or round-robin), save task & evidence."""
    household_id = state["household_id"]
    category_str = state.get("category", "bill")
    try:
        category = TaskCategory(category_str)
    except ValueError:
        category = TaskCategory.bill

    async with AsyncSessionLocal() as db:
        members_res = await db.execute(
            select(Member).where(
                Member.household_id == household_id,
                Member.role == MemberRole.child,
            )
        )
        children = members_res.scalars().all()

        assignee = None
        for child in children:
            if child.categories_owned and category.value in child.categories_owned:
                assignee = child
                break
        if not assignee and children:
            assignee = children[0]

        assignee_id = assignee.id if assignee else None

        extracted = state.get("extracted", {})
        title = (extracted.get("title") or {}).get("value") or f"{category.value.title()} Task"
        due_date_raw = (extracted.get("due_date") or {}).get("value")
        due_date = None
        if due_date_raw:
            try:
                due_date = datetime.fromisoformat(due_date_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        existing_task_id = state.get("existing_task_id")
        task_id = existing_task_id

        if existing_task_id:
            task = await db.get(Task, existing_task_id)
            if task:
                task.updated_at = datetime.utcnow()
        else:
            task = Task(
                household_id=household_id,
                category=category,
                title=title,
                amount=(extracted.get("amount") or {}).get("value"),
                due_date=due_date,
                payee=(extracted.get("payee") or {}).get("value"),
                status=TaskStatus.confirmed if state.get("verify_passed") else TaskStatus.needs_review,
                assignee_id=assignee_id,
                confidence=state.get("confidence", 0.9),
                dedupe_key=state.get("dedupe_key"),
                recurrence="monthly" if category == TaskCategory.loan_emi else None,
            )
            db.add(task)
            await db.flush()
            task_id = task.id

        # Persist verbatim quoted evidence
        artifact_id = state["artifact_id"]
        raw_text = state.get("raw_text", "")
        for field_name, data in extracted.items():
            if not isinstance(data, dict):
                continue
            quote = data.get("quote")
            if quote and norm(quote) in norm(raw_text):
                existing_ev = await db.execute(
                    select(Evidence).where(
                        Evidence.task_id == task_id,
                        Evidence.artifact_id == artifact_id,
                        Evidence.field_name == field_name,
                    )
                )
                if not existing_ev.scalars().first():
                    db.add(Evidence(
                        task_id=task_id,
                        artifact_id=artifact_id,
                        quoted_span=quote,
                        field_name=field_name,
                    ))

        await db.commit()

    await _log_event(
        task_id=task_id,
        household_id=household_id,
        actor="agent:assign",
        action="assigned",
        reason=f"Assigned to {assignee.name if assignee else 'Unassigned'}",
        payload={"assignee_id": assignee_id, "category": category.value},
    )
    return {"assignee_id": assignee_id, "task_id": task_id}


# ---------------------------------------------------------------------------
# Node 9: Draft Actions
# ---------------------------------------------------------------------------

async def node_draft(state: AgentState) -> dict:
    """Draft Marathi reply to parent, sibling notification, optional call script."""
    if state.get("existing_task_id"):
        parent_reply = "हे बिल आधीच नोंदवले आहे. काळजी करू नका, आम्ही लक्ष ठेवत आहोत. 🙏"
        await _log_event(
            task_id=state.get("existing_task_id"),
            household_id=state.get("household_id"),
            actor="agent:draft",
            action="drafted_duplicate",
            reason="Merged duplicate task; suppressed sibling notification",
            payload={"existing_task_id": state.get("existing_task_id")},
        )
        return {
            "parent_reply": parent_reply,
            "sibling_notification": "",
            "call_script": None,
        }
    extracted = state.get("extracted", {})
    title = (extracted.get("title") or {}).get("value") or "काम"
    amount = (extracted.get("amount") or {}).get("value") or ""
    due_date = (extracted.get("due_date") or {}).get("value") or ""
    payee = (extracted.get("payee") or {}).get("value") or ""

    # Marathi confirmation reply to parent
    parent_reply = (
        f"नमस्कार. आम्ही तुमचे काम व्यवस्थित नोंदवून घेतले आहे: {title}. "
        f"{'रक्कम: ' + amount + '. ' if amount else ''}"
        f"{'देय तारीख: ' + due_date[:10] + '. ' if due_date else ''}"
        f"काळजी करू नका, आम्ही वेळेवर सर्व पूर्ण करू. आम्ही तुमच्यासाठी हे करू."
    )

    if state.get("medical_context"):
        parent_reply += " (टीप: मला वैद्यकीय अहवाल किंवा गोळ्यांचा अर्थ सांगता येणार नाही. कृपया हे तुमच्या डॉक्टरांशी शेअर करा.)"

    # Sibling notification formatted for instant action & smartwatch readability
    watch_header = f"📌 {title}"
    if amount and due_date:
        watch_header = f"📌 {payee or title} ({amount}) due {due_date[:10]}"

    sibling_notification = (
        f"{watch_header}\n"
        f"A new family task has been added to the Saath board. "
        f"Please tap Claim to handle it."
    )

    call_script = None
    if state.get("category") in (TaskCategory.bill.value, TaskCategory.loan_emi.value) and amount:
        call_script = (
            f"Hello, I am calling on behalf of my family regarding our account with {payee or 'your service'}. "
            f"Could you please confirm the current outstanding balance of {amount} due on {due_date[:10] if due_date else 'this month'}? "
            f"Thank you for your assistance."
        )

    await _log_event(
        task_id=None,
        household_id=state.get("household_id"),
        actor="agent:draft",
        action="drafted",
        reason="Generated Marathi parent reply, sibling notification, and call script",
        payload={"title": title, "has_call_script": call_script is not None},
    )
    return {
        "parent_reply": parent_reply,
        "sibling_notification": sibling_notification,
        "call_script": call_script,
    }
