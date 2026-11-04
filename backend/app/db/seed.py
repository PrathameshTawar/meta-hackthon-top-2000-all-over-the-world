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
    Medication, Vital, VitalThreshold, VitalKind, VitalOp, DoseLog, DoseStatus,
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
            language="mr",
        )
        aai = Member(
            household_id=household.id,
            name="Poonam Tawre (Aai)",
            role=MemberRole.parent,
            telegram_id="aai_pune",
            phone=os.getenv("DEMO_AAI_PHONE", "+919800000002"),
            categories_owned=[],
            language="mr",
        )
        # Children in different cities
        rohan = Member(
            household_id=household.id,
            name="Rohan (बेंगळुरू)",  # Earner
            role=MemberRole.child,
            telegram_id="rohan_blr",
            phone=os.getenv("DEMO_ROHAN_PHONE", "+919800000003"),
            categories_owned=["bill", "loan_emi", "insurance"],
            language="en",
        )
        priya = Member(
            household_id=household.id,
            name="Priya (मुंबई)",
            role=MemberRole.child,
            telegram_id="priya_mum",
            phone=os.getenv("DEMO_PRIYA_PHONE", "+919800000004"),
            categories_owned=["appointment", "medical"],
            language="en",
        )
        amit = Member(
            household_id=household.id,
            name="Amit (दिल्ली)",
            role=MemberRole.child,
            telegram_id="amit_del",
            phone=os.getenv("DEMO_AMIT_PHONE", "+919800000005"),
            categories_owned=["pension", "govt_letter"],
            language="en",
        )

        # Guardian who lives near the parents and gets a copy of every alert
        poonam = Member(
            household_id=household.id,
            name="Poonam Dhumal (नाशिक)",
            role=MemberRole.helper,
            telegram_id="poonam_nsk",
            phone=os.getenv("DEMO_GUARDIAN_PHONE", "+919800000006"),
            categories_owned=[],
            language="mr",
        )

        db.add_all([baba, aai, rohan, priya, amit, poonam])
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
        art_bp = Artifact(
            household_id=household.id,
            type=ArtifactType.voice,
            file_url="telegram://voice_baba_bp.ogg",
            raw_text="आज सकाळी बीपी तपासले, ते १५२/९४ आले आहे.",
            received_at=now - timedelta(days=2),
        )

        db.add_all([art_bill, art_emi, art_ins, art_app, art_pension, art_medical, art_bp])
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

        # 7. Health Module Seeds (H-6)
        # Medication for Aai (08:00 and 20:00), owner child Rohan
        med_aai = Medication(
            household_id=household.id,
            member_id=aai.id,
            name="सकाळची गोळी (Amlodipine)",
            dose_text="1 tablet",
            times=["08:00", "20:00"],
            owner_child_id=rohan.id,
            active=True,
        )
        db.add(med_aai)
        await db.flush()

        # Today's dose logs for demo
        today_naive = now.replace(tzinfo=None)
        dose_morning = DoseLog(
            medication_id=med_aai.id,
            scheduled_for=datetime(today_naive.year, today_naive.month, today_naive.day, 8, 0),
            status=DoseStatus.taken,
            reminder_sent_at=today_naive - timedelta(hours=2),
            responded_at=today_naive - timedelta(hours=1, minutes=45),
        )
        dose_evening = DoseLog(
            medication_id=med_aai.id,
            scheduled_for=datetime(today_naive.year, today_naive.month, today_naive.day, 20, 0),
            status=DoseStatus.pending,
        )
        db.add_all([dose_morning, dose_evening])

        # Family Threshold for Baba: BP value_1 gt 150
        thresh_baba = VitalThreshold(
            household_id=household.id,
            member_id=baba.id,
            kind=VitalKind.bp,
            field="value_1",
            op=VitalOp.gt,
            limit=150.0,
            note="Doctor advised",
            set_by_member_id=rohan.id,
            active=True,
        )
        db.add(thresh_baba)

        # Three past BP readings for Baba over the last week
        v1 = Vital(
            household_id=household.id,
            member_id=baba.id,
            kind=VitalKind.bp,
            value_1=138.0,
            value_2=86.0,
            unit="mmHg",
            measured_at=today_naive - timedelta(days=6),
            artifact_id=None,
            quote="138/86",
        )
        v2 = Vital(
            household_id=household.id,
            member_id=baba.id,
            kind=VitalKind.bp,
            value_1=142.0,
            value_2=88.0,
            unit="mmHg",
            measured_at=today_naive - timedelta(days=4),
            artifact_id=None,
            quote="142/88",
        )
        v3 = Vital(
            household_id=household.id,
            member_id=baba.id,
            kind=VitalKind.bp,
            value_1=152.0,
            value_2=94.0,
            unit="mmHg",
            measured_at=today_naive - timedelta(days=2),
            artifact_id=art_bp.id,
            quote="१५२/९४",
        )
        db.add_all([v1, v2, v3])

        await db.commit()
        print("Saath demo data seeded successfully for Household 1!")


if __name__ == "__main__":
    asyncio.run(seed_data())
