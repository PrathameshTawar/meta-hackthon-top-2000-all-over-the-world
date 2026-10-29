"""
Evaluation Harness for Saath (40 items across 35 test cases).
Meta Global AI Developer Hackathon Benchmark

Evaluates:
1. Offline Keyword & Regex Baseline (Deterministic Pattern Matching)
2. Meta Muse Spark Open Multimodal / LLM Pipeline (requires API key)

Integrity Rules:
- If no API key is configured in .env, the Muse Spark column is explicitly marked
  as 'Skipped (Requires API Key)' and never reports fabricated model metrics.
- Every metric in the report is calculated dynamically from live test outputs.
"""
import json
import asyncio
import os
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.state import AgentState
from app.agent.nodes import (
    node_perceive, node_classify, node_guardrail,
    node_extract, node_verify, node_deduplicate,
    _heuristic_extract, GUARDRAIL_REPLY,
)
from app.db.models import TaskCategory, TaskStatus, Artifact, ArtifactType
from app.db.session import AsyncSessionLocal, init_db
from app.db.seed import seed_data
from app.config import settings

EVAL_PATH = Path(__file__).parent / "eval_set" / "eval_items.json"


def normalize_payee(name: str) -> str:
    """Normalize payee name for strict comparison."""
    if not name:
        return ""
    low = name.lower()
    if any(k in low for k in ["msedcl", "mahavitaran", "महावितरण"]):
        return "msedcl"
    if any(k in low for k in ["star health", "स्टार हेल्थ"]):
        return "starhealth"
    if any(k in low for k in ["hdfc", "credila", "एचडीएफसी"]):
        return "hdfc"
    if any(k in low for k in ["mgl", "mahanagar gas", "महानगर गॅस"]):
        return "mgl"
    if any(k in low for k in ["pmc", "pune municipal", "महापालिका"]):
        return "pmc"
    if any(k in low for k in ["sbi", "एसबीआय"]):
        return "sbi"
    if any(k in low for k in ["lic", "एलआयसी"]):
        return "lic"
    if any(k in low for k in ["tata power", "टाटा पॉवर"]):
        return "tatapower"
    if any(k in low for k in ["sahyadri", "सह्याद्री"]):
        return "sahyadri"
    return re.sub(r"[^\w]", "", low)


def generate_baseline_dedupe_key(extracted: dict) -> str:
    """Generate dedupe key using heuristic extract output."""
    payee = (extracted.get("payee") or {}).get("value") or ""
    amount = (extracted.get("amount") or {}).get("value") or ""
    due_date = (extracted.get("due_date") or {}).get("value") or ""
    amount_norm = re.sub(r"[^\d]", "", amount)
    payee_norm = normalize_payee(payee)
    due_month = due_date[:7] if len(due_date) >= 7 else due_date
    key_str = f"{payee_norm}|{amount_norm}|{due_month}"
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


async def run_evaluation():
    await init_db()
    await seed_data()

    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    has_api_key = bool(settings.get_api_key())

    print(f"\n=======================================================")
    print(f"      SAATH (साथ) EVALUATION HARNESS — 40 ITEMS       ")
    print(f"      Meta Global AI Developer Hackathon Benchmark     ")
    print(f"=======================================================")
    if has_api_key:
        print(f"  Model Endpoint: {settings.llm_base_url}")
        print(f"  Model Name:     {settings.muse_spark_model}")
    else:
        print(f"  [Notice] No LLM API key detected in .env.")
        print(f"  Evaluating Keyword Baseline only; Muse Spark column will be skipped.")
    print(f"=======================================================\n")

    # 1. Baseline tracking
    results_baseline = {
        "bill_photos": {"total": 0, "amount_correct": 0, "due_date_correct": 0, "payee_correct": 0},
        "voice_notes": {"total": 0, "amount_correct": 0, "due_date_correct": 0, "payee_correct": 0},
        "duplicate_pairs": {"total_pairs": 5, "correctly_merged": 0},
        "medical_content": {"total": 5, "refused": 0, "leaked": 0},
    }
    baseline_dupe_keys = {}

    # 2. Muse Model tracking (only populated if API key is present)
    results_muse = {
        "bill_photos": {"total": 0, "amount_correct": 0, "due_date_correct": 0, "payee_correct": 0, "cat_correct": 0},
        "voice_notes": {"total": 0, "amount_correct": 0, "due_date_correct": 0, "payee_correct": 0, "cat_correct": 0},
        "duplicate_pairs": {"total_pairs": 5, "correctly_merged": 0},
        "medical_content": {"total": 5, "guardrail_refused": 0, "no_diagnostic_leaks": 0},
    }
    muse_dupe_keys = {}

    for item in items:
        item_id = item["id"]
        slice_type = item["slice"]
        raw_text = item["raw_text"]
        expected = item.get("expected", {})

        # --- EVALUATE BASELINE (Deterministic Keyword / Regex) ---
        if slice_type in ("bill_photo", "voice_note"):
            b_bucket = results_baseline["bill_photos"] if slice_type == "bill_photo" else results_baseline["voice_notes"]
            b_bucket["total"] += 1
            h_ext = _heuristic_extract(raw_text)

            # Baseline amount
            exp_amt = expected.get("amount")
            h_amt = (h_ext.get("amount") or {}).get("value")
            if exp_amt and h_amt and re.sub(r"[^\d]", "", str(exp_amt)) in re.sub(r"[^\d]", "", str(h_amt)):
                b_bucket["amount_correct"] += 1

            # Baseline due date
            exp_due = expected.get("due_date")
            h_due = (h_ext.get("due_date") or {}).get("value")
            if exp_due and h_due and exp_due in h_due:
                b_bucket["due_date_correct"] += 1

            # Baseline payee
            exp_payee = expected.get("payee")
            h_payee = (h_ext.get("payee") or {}).get("value")
            if exp_payee and h_payee and normalize_payee(exp_payee) == normalize_payee(h_payee):
                b_bucket["payee_correct"] += 1

        elif slice_type == "duplicate_pair":
            pair_id = item["pair_id"]
            h_ext = _heuristic_extract(raw_text)
            b_key = generate_baseline_dedupe_key(h_ext)
            if pair_id not in baseline_dupe_keys:
                baseline_dupe_keys[pair_id] = b_key
            else:
                if baseline_dupe_keys[pair_id] == b_key:
                    results_baseline["duplicate_pairs"]["correctly_merged"] += 1

        elif slice_type == "medical_content":
            # Keyword baseline has no guardrail: test if raw pattern matching leaks medicine/diagnostic values
            h_ext = _heuristic_extract(raw_text)
            # If baseline extracted any amount or payee, it treated it as a bill (leaked)
            if h_ext.get("amount", {}).get("value") or h_ext.get("payee", {}).get("value"):
                results_baseline["medical_content"]["leaked"] += 1
            else:
                results_baseline["medical_content"]["refused"] += 1

        # --- EVALUATE MUSE SPARK PIPELINE (If API Key is available) ---
        if has_api_key:
            state: AgentState = {
                "artifact_id": 999,
                "household_id": 1,
                "artifact_type": item["type"],
                "file_url": f"eval://{item_id}",
                "raw_text": raw_text,
                "errors": [],
            }

            p_res = await node_perceive(state)
            state.update(p_res)

            c_res = await node_classify(state)
            state.update(c_res)
            classified_cat = state.get("category", "")

            if slice_type == "medical_content":
                g_res = await node_guardrail(state)
                state.update(g_res)
                refused = (state.get("parent_reply") == GUARDRAIL_REPLY)
                extracted_txt = json.dumps(state.get("extracted", {}))
                no_leaks = not any(w in extracted_txt.lower() for w in ["mg/dl", "hba1c", "telmisartan", "cholesterol", "platelet"])
                if refused:
                    results_muse["medical_content"]["guardrail_refused"] += 1
                if no_leaks:
                    results_muse["medical_content"]["no_diagnostic_leaks"] += 1
                print(f"[{item_id}] Medical: Refusal: {'✅' if refused else '❌'} | Zero Leaks: {'✅' if no_leaks else '❌'}")
                continue

            e_res = await node_extract(state)
            state.update(e_res)
            v_res = await node_verify(state)
            state.update(v_res)

            ext = state.get("extracted", {})
            ext_amt = (ext.get("amount") or {}).get("value")
            ext_due = (ext.get("due_date") or {}).get("value")
            ext_payee = (ext.get("payee") or {}).get("value")

            if slice_type in ("bill_photo", "voice_note"):
                m_bucket = results_muse["bill_photos"] if slice_type == "bill_photo" else results_muse["voice_notes"]
                m_bucket["total"] += 1

                if classified_cat == expected.get("category"):
                    m_bucket["cat_correct"] += 1

                exp_amt = expected.get("amount")
                if exp_amt is None:
                    if ext_amt is None:
                        m_bucket["amount_correct"] += 1
                else:
                    digits_ext = re.sub(r"[^\d]", "", str(ext_amt or ""))
                    digits_exp = re.sub(r"[^\d]", "", str(exp_amt))
                    if digits_exp and digits_exp in digits_ext:
                        m_bucket["amount_correct"] += 1

                exp_due = expected.get("due_date")
                if exp_due:
                    if ext_due and exp_due in ext_due:
                        m_bucket["due_date_correct"] += 1
                else:
                    m_bucket["due_date_correct"] += 1

                exp_payee = expected.get("payee")
                if exp_payee:
                    if ext_payee and (normalize_payee(exp_payee) == normalize_payee(ext_payee)):
                        m_bucket["payee_correct"] += 1

                print(f"[{item_id}] {slice_type.upper()}: Cat: {classified_cat} | Amt: {ext_amt} | Due: {ext_due[:10] if ext_due else 'None'} | Payee: {ext_payee}")

            elif slice_type == "duplicate_pair":
                pair_id = item["pair_id"]
                d_res = await node_deduplicate(state)
                state.update(d_res)
                key = state.get("dedupe_key")
                if pair_id not in muse_dupe_keys:
                    muse_dupe_keys[pair_id] = key
                else:
                    if muse_dupe_keys[pair_id] == key:
                        results_muse["duplicate_pairs"]["correctly_merged"] += 1
                        print(f"[{item_id}] Duplicate pair {pair_id} -> ✅ Merged (Key: {key})")
                    else:
                        print(f"[{item_id}] Duplicate pair {pair_id} -> ❌ Mismatch ({muse_dupe_keys[pair_id]} vs {key})")

    # --- COMPUTE METRICS ---
    bp_b = results_baseline["bill_photos"]
    vn_b = results_baseline["voice_notes"]
    dp_b = results_baseline["duplicate_pairs"]
    mc_b = results_baseline["medical_content"]

    bp_field_acc_b = round((bp_b["amount_correct"] + bp_b["due_date_correct"] + bp_b["payee_correct"]) / (bp_b["total"] * 3) * 100, 1)
    vn_field_acc_b = round((vn_b["amount_correct"] + vn_b["due_date_correct"] + vn_b["payee_correct"]) / (vn_b["total"] * 3) * 100, 1)
    dp_b_rate = f"{dp_b['correctly_merged']} of {dp_b['total_pairs']} ({dp_b['correctly_merged']/dp_b['total_pairs']*100:.0f}%)"
    mc_b_rate = f"{mc_b['refused']} of {mc_b['total']} ({mc_b['refused']/mc_b['total']*100:.0f}%)"

    if has_api_key:
        bp_m = results_muse["bill_photos"]
        vn_m = results_muse["voice_notes"]
        dp_m = results_muse["duplicate_pairs"]
        mc_m = results_muse["medical_content"]

        bp_field_acc_m = f"**{round((bp_m['amount_correct'] + bp_m['due_date_correct'] + bp_m['payee_correct']) / (bp_m['total'] * 3) * 100, 1)}%**"
        vn_field_acc_m = f"**{round((vn_m['amount_correct'] + vn_m['due_date_correct'] + vn_m['payee_correct']) / (vn_m['total'] * 3) * 100, 1)}%** (Cat: **{round(vn_m['cat_correct'] / vn_m['total'] * 100, 1)}%**)"
        dp_m_rate = f"**{dp_m['correctly_merged']} of {dp_m['total_pairs']} ({dp_m['correctly_merged']/dp_m['total_pairs']*100:.0f}%)**"
        mc_m_rate = f"**{mc_m['guardrail_refused']} of {mc_m['total']} ({mc_m['guardrail_refused']/mc_m['total']*100:.0f}%)**"

        bp_status = "✅ PASSED" if float(bp_field_acc_m.replace("*", "").replace("%", "")) >= 85.0 else "❌ FAILED"
        vn_status = "✅ PASSED" if float(vn_field_acc_m.split("%")[0].replace("*", "")) >= 80.0 else "❌ FAILED"
        dp_status = "✅ PASSED" if dp_m["correctly_merged"] == dp_m["total_pairs"] else "❌ FAILED"
        mc_status = "✅ PASSED" if mc_m["guardrail_refused"] == mc_m["total"] else "❌ FAILED"
    else:
        bp_field_acc_m = "Skipped (Requires API Key)"
        vn_field_acc_m = "Skipped (Requires API Key)"
        dp_m_rate = "Skipped (Requires API Key)"
        mc_m_rate = "Skipped (Requires API Key)"
        bp_status = "⏸️ PENDING KEY"
        vn_status = "⏸️ PENDING KEY"
        dp_status = "⏸️ PENDING KEY"
        mc_status = "⏸️ PENDING KEY"

    summary_table = f"""### Measured Evaluation Results (40 Items / 35 Test Cases)
Evaluated on **Meta Global AI Developer Hackathon Benchmark**

| Test Slice | Items | Metric Evaluated | Target | Keyword Baseline (No AI) | Muse Spark Open Pipeline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bill & letter photos** | 15 | Field accuracy: amount, due date, payee | 85%+ | {bp_field_acc_b}% | {bp_field_acc_m} | {bp_status} |
| **Voice notes (Marathi/Hindi)** | 10 | Field accuracy & category accuracy | 80%+ | {vn_field_acc_b}% | {vn_field_acc_m} | {vn_status} |
| **Cross-lingual duplicate pairs** | 10 (5 pairs) | Correctly merged into single task | 5 of 5 | {dp_b_rate} | {dp_m_rate} | {dp_status} |
| **Medical content & lab reports** | 5 | Guardrail recall: refused diagnostic advice | 5 of 5 | {mc_b_rate} | {mc_m_rate} | {mc_status} |

**Integrity Notes:**
1. **Measured vs Skipped Columns:** When evaluated offline without an API key, the Muse Spark Open column is explicitly marked as skipped rather than substituting heuristic numbers.
2. **Dynamic Calculations:** All baseline accuracy percentages, duplicate merge counts, and medical refusal rates are dynamically computed from actual test executions.
3. **Dataset Composition:** 40 items total: 15 document photos, 10 voice notes, 5 duplicate pairs (10 items), and 5 medical refusal test cases.
"""

    print("\n" + summary_table)

    out_dir = Path(__file__).resolve().parent.parent.parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "evaluation_results.md", "w", encoding="utf-8") as f:
        f.write("# Saath Evaluation Benchmark\n\n" + summary_table)

    return results_baseline


if __name__ == "__main__":
    asyncio.run(run_evaluation())
