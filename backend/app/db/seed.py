"""
Seed script for the Saath demo household.
Populates the database with realistic family data, tasks, quoted evidence, and audit events.
Can be executed via: python -m app.db.seed
"""
import asyncio
from datetime import datetime, timezone, timedelta
from app.db.session import AsyncSessionLocal, init_db
from app.db.models import (
    Household, Member, MemberRole, Artifact, ArtifactType,
    Task, TaskCategory, TaskStatus, Evidence, Event,
)
from sqlalchemy import select, delete


async def seed_data():
    await init_db()
    async with AsyncSessionLocal() as db:
        # Check if household 1 already exists
        existing = await db.get(Household, 1)
        if existing:
            print("Household 1 already exists. Use reset.py to wipe and re-seed.")
            return

        # 1. Household
        household = Household(
            id=1,
            name="Kulkarni Family (पुणे)",
            primary_language="mr",
        )
        db.add(household)
        await db.flush()

        # 2. Members
        import os
        baba = Member(
            household_id=household.id,
            name="Baba (दिलीप कुलकर्णी)",
            role=MemberRole.parent,
            telegram_id="baba_pune",
            phone=os.getenv("DEMO_BABA_PHONE", "+919800000001"),
            categories_owned=[],
        )
        aai = Member(
            household_id=household.id,
            name="Aai (सुनीता कुलकर्णी)",
            role=MemberRole.parent,
            telegram_id="aai_pune",
            phone=os.getenv("DEMO_AAI_PHONE", "+919800000002"),
            categories_owned=[],
        )
        # Children in different cities
        rohan = Member(
            household_id=household.id,
            name="Rohan (बेंगळुरू)",  # Earner
            role=MemberRole.child,
            telegram_id="rohan_blr",
            phone=os.getenv("DEMO_ROHAN_PHONE", "+919800000003"),
            categories_owned=["bill", "loan_emi", "insurance"],
        )
        priya = Member(
            household_id=household.id,
            name="Priya (मुंबई)",
            role=MemberRole.child,
            telegram_id="priya_mum",
            phone=os.getenv("DEMO_PRIYA_PHONE", "+919800000004"),
            categories_owned=["appointment", "medical"],
        )
        amit = Member(
            household_id=household.id,
            name="Amit (दिल्ली)",
            role=MemberRole.child,
            telegram_id="amit_del",
            phone=os.getenv("DEMO_AMIT_PHONE", "+919800000005"),
            categories_owned=["pension", "govt_letter"],
        )

        db.add_all([baba, aai, rohan, priya, amit])
        await db.flush()

        # 3. Artifacts (Raw voice transcripts and OCR documents)
        now = datetime.now(timezone.utc)

        art_bill = Artifact(
            household_id=household.id,
            type=ArtifactType.voice,
            file_url="telegram://voice_msedcl_nov2026.ogg",
            raw_text="रोहन, महावितरणचे वीज बिल आले आहे. रक्कम ₹१,८४० आहे. देय तारीख ३ नोव्हेंबर २०२६ आहे. वेळेवर भरून देशील का?",
            received_at=now - timedelta(hours=4),
        )
        art_emi = Artifact(
            household_id=household.id,
            type=ArtifactType.image,
            file_url="https://s3.amazonaws.com/saath-docs/hdfc_loan_notice.png",
            raw_text="HDFC CREDILA EDUCATION LOAN. Loan A/C: 40982-ED. Monthly EMI Amount: INR 18,500. Due Date: 2026-11-10. Payee: HDFC Bank. Borrower: Rohan Kulkarni.",
            received_at=now - timedelta(days=1),
        )
        art_ins = Artifact(
            household_id=household.id,
            type=ArtifactType.image,
            file_url="https://s3.amazonaws.com/saath-docs/star_health_renewal.png",
            raw_text="STAR HEALTH AND ALLIED INSURANCE. Senior Citizen Red Carpet Policy Renewal. Policy No: P/191214/01/2026/001420. Renewal Premium: ₹24,800. Renewal Due Date: 2026-11-25. Insured Person: Dilip R. Kulkarni.",
            received_at=now - timedelta(days=2),
        )
        art_app = Artifact(
            household_id=household.id,
            type=ArtifactType.voice,
            file_url="telegram://voice_sahyadri_nov2026.ogg",
            raw_text="प्रिया, सह्याद्री हॉस्पिटलमध्ये डॉ. जोशींची तपासणी अपॉइंटमेंट ५ नोव्हेंबर २०२६ रोजी सकाळी १० वाजता ठरवली आहे. गाडीची सोय करावी लागेल.",
            received_at=now - timedelta(hours=6),
        )
        art_pension = Artifact(
            household_id=household.id,
            type=ArtifactType.image,
            file_url="https://s3.amazonaws.com/saath-docs/sbi_jeevan_pramaan.png",
            raw_text="STATE BANK OF INDIA PENSION CELL. Annual Life Certificate Submission (Jeevan Pramaan). PPO Number: 892341-PUN. Payee: SBI Pension Cell. Target Submission: 2026-11-15.",
            received_at=now - timedelta(days=3),
        )
        art_medical = Artifact(
            household_id=household.id,
            type=ArtifactType.image,
            file_url="https://s3.amazonaws.com/saath-docs/lal_pathlabs_report.png",
            raw_text="DR LAL PATHLABS CLINICAL REPORT. Patient: Dilip Kulkarni (67M). Fasting Glucose: 168 mg/dL. HbA1c: 7.8%. Logistics: Follow-up consultation at Sahyadri Hospital on 2026-11-08.",
            received_at=now - timedelta(days=4),
        )

        db.add_all([art_bill, art_emi, art_ins, art_app, art_pension, art_medical])
        await db.flush()

        # 4. Tasks
        # Task 1: Unclaimed bill due in 2 days -> perfect for testing escalation!
        task_electricity = Task(
            household_id=household.id,
            category=TaskCategory.bill,
            title="महावितरण वीज बिल (MSEDCL Electricity)",
            amount="₹1,840",
            due_date=now + timedelta(days=2),
            payee="Mahavitaran (MSEDCL)",
            status=TaskStatus.confirmed,
            assignee_id=None,  # Unclaimed for escalation demo!
            confidence=0.95,
            dedupe_key="msedcl|1840|2026-11",
            recurrence="monthly",
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=4),
        )

        # Task 2: Earner's own education loan EMI -> for 30-day total commitment
        task_loan = Task(
            household_id=household.id,
            category=TaskCategory.loan_emi,
            title="HDFC Education Loan EMI (Rohan)",
            amount="₹18,500",
            due_date=now + timedelta(days=12),
            payee="HDFC Bank",
            status=TaskStatus.claimed,
            assignee_id=rohan.id,
            confidence=1.0,
            dedupe_key="hdfc|18500|2026-11",
            recurrence="monthly",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )

        # Task 3: Star Health Insurance Renewal
        task_insurance = Task(
            household_id=household.id,
            category=TaskCategory.insurance,
            title="Star Health Senior Citizen Policy Renewal",
            amount="₹24,800",
            due_date=now + timedelta(days=27),
            payee="Star Health and Allied Insurance",
            status=TaskStatus.new,
            assignee_id=rohan.id,
            confidence=0.92,
            dedupe_key="starhealth|24800|2026-11",
            recurrence="annual",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )

        # Task 4: Hospital follow-up appointment
        task_appointment = Task(
            household_id=household.id,
            category=TaskCategory.appointment,
            title="सह्याद्री हॉस्पिटल डॉ. जोशी तपासणी",
            amount=None,
            due_date=now + timedelta(days=7),
            payee="Sahyadri Hospital Pune",
            status=TaskStatus.claimed,
            assignee_id=priya.id,
            confidence=0.90,
            dedupe_key="sahyadri|0|2026-11",
            recurrence=None,
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=6),
        )

        # Task 5: Pension Jeevan Pramaan
        task_pension = Task(
            household_id=household.id,
            category=TaskCategory.pension,
            title="SBI वार्षिक जीवन प्रमाणपत्र (Jeevan Pramaan)",
            amount=None,
            due_date=now + timedelta(days=17),
            payee="SBI Pension Cell",
            status=TaskStatus.new,
            assignee_id=amit.id,
            confidence=0.88,
            dedupe_key="sbipension|0|2026-11",
            recurrence="annual",
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        )

        # Task 6: Medical logistics only (Guardrail refused interpretation)
        task_medical = Task(
            household_id=household.id,
            category=TaskCategory.medical,
            title="डॉ. लाल पॅथलॅब चाचणी फॉलो-अप (लॉजिस्टिक मात्र)",
            amount=None,
            due_date=now + timedelta(days=10),
            payee="Sahyadri Hospital",
            status=TaskStatus.done,
            assignee_id=priya.id,
            confidence=1.0,
            dedupe_key="lallogistics|0|2026-11",
            recurrence=None,
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=1),
        )

        db.add_all([task_electricity, task_loan, task_insurance, task_appointment, task_pension, task_medical])
        await db.flush()

        # 5. Evidence rows (Exact quoted spans from the sources)
        evidences = [
            # Electricity Bill Evidence
            Evidence(task_id=task_electricity.id, artifact_id=art_bill.id, field_name="amount", quoted_span="₹१,८४०"),
            Evidence(task_id=task_electricity.id, artifact_id=art_bill.id, field_name="payee", quoted_span="महावितरण"),
            Evidence(task_id=task_electricity.id, artifact_id=art_bill.id, field_name="due_date", quoted_span="३ नोव्हेंबर २०२६"),

            # Loan EMI Evidence
            Evidence(task_id=task_loan.id, artifact_id=art_emi.id, field_name="amount", quoted_span="INR 18,500"),
            Evidence(task_id=task_loan.id, artifact_id=art_emi.id, field_name="due_date", quoted_span="2026-11-10"),
            Evidence(task_id=task_loan.id, artifact_id=art_emi.id, field_name="payee", quoted_span="HDFC Bank"),

            # Insurance Renewal Evidence
            Evidence(task_id=task_insurance.id, artifact_id=art_ins.id, field_name="amount", quoted_span="₹24,800"),
            Evidence(task_id=task_insurance.id, artifact_id=art_ins.id, field_name="due_date", quoted_span="2026-11-25"),
            Evidence(task_id=task_insurance.id, artifact_id=art_ins.id, field_name="payee", quoted_span="STAR HEALTH AND ALLIED INSURANCE"),

            # Appointment Evidence
            Evidence(task_id=task_appointment.id, artifact_id=art_app.id, field_name="payee", quoted_span="सह्याद्री हॉस्पिटलमध्ये डॉ. जोशींची"),
            Evidence(task_id=task_appointment.id, artifact_id=art_app.id, field_name="due_date", quoted_span="५ नोव्हेंबर २०२६"),

            # Pension Evidence
            Evidence(task_id=task_pension.id, artifact_id=art_pension.id, field_name="payee", quoted_span="STATE BANK OF INDIA PENSION CELL"),
            Evidence(task_id=task_pension.id, artifact_id=art_pension.id, field_name="due_date", quoted_span="2026-11-15"),

            # Medical Guardrail Evidence
            Evidence(task_id=task_medical.id, artifact_id=art_medical.id, field_name="payee", quoted_span="Sahyadri Hospital on 2026-11-08"),
        ]
        db.add_all(evidences)

        # 6. Events / Audit Log
        events = [
            Event(
                household_id=household.id,
                task_id=task_electricity.id,
                actor="agent:perceive",
                action="transcribed",
                reason="Muse Voice Transcribe completed Marathi voice note",
                payload={"audio_file": "voice_msedcl_nov2026.ogg", "language": "mr"},
                created_at=now - timedelta(hours=4),
            ),
            Event(
                household_id=household.id,
                task_id=task_electricity.id,
                actor="agent:verify",
                action="verified",
                reason="All 3 code-based checks passed: quote in source, valid future date, amount digits match",
                payload={"verify_passed": True, "confidence": 0.95},
                created_at=now - timedelta(hours=4),
            ),
            Event(
                household_id=household.id,
                task_id=task_medical.id,
                actor="agent:guardrail",
                action="medical_blocked",
                reason="Medical report detected: refused diagnostic interpretation, extracted logistics only",
                payload={"guardrail_rule": "strict_logistics_only", "reply_language": "mr"},
                created_at=now - timedelta(days=4),
            ),
            Event(
                household_id=household.id,
                task_id=task_loan.id,
                actor="agent:assign",
                action="assigned",
                reason="Auto-assigned to Rohan by category owner (loan_emi)",
                payload={"category": "loan_emi", "assignee": "Rohan (बेंगळुरू)"},
                created_at=now - timedelta(days=1),
            ),
        ]
        db.add_all(events)

        await db.commit()
        print("Saath demo data seeded successfully for Household 1!")


if __name__ == "__main__":
    asyncio.run(seed_data())
