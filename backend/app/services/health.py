import enum
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import (
    Medication, DoseLog, DoseStatus, Member, MemberRole, Event, Household
)
from app.agent.nodes import get_current_ist_datetime
from app.api.webhooks import notify

logger = logging.getLogger(__name__)


class DoseTakenResult(str, enum.Enum):
    ok = "ok"
    already_taken = "already_taken"
    late_ok = "late_ok"
    not_found = "not_found"
    household_mismatch = "household_mismatch"


async def ensure_todays_doses(now: Optional[datetime] = None) -> int:
    """
    For each active medication and each time today (IST), create a DoseLog if missing.
    Rely on the unique constraint on (medication_id, scheduled_for) to avoid duplicates.
    """
    if now is None:
        now = get_current_ist_datetime()

    created = 0
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Medication).where(Medication.active == True))
        active_meds = res.scalars().all()

        for med in active_meds:
            for t_str in (med.times or []):
                try:
                    parts = t_str.strip().split(":")
                    hour, minute = int(parts[0]), int(parts[1])
                    scheduled_for = datetime(now.year, now.month, now.day, hour, minute)
                except Exception:
                    continue

                # Check if dose exists
                existing = await db.execute(
                    select(DoseLog).where(
                        DoseLog.medication_id == med.id,
                        DoseLog.scheduled_for == scheduled_for,
                    )
                )
                if not existing.scalars().first():
                    dose = DoseLog(
                        medication_id=med.id,
                        scheduled_for=scheduled_for,
                        status=DoseStatus.pending,
                    )
                    db.add(dose)
                    created += 1

        if created > 0:
            await db.commit()

    return created


async def send_due_reminders(now: Optional[datetime] = None) -> int:
    """
    For pending doses with scheduled_for <= now and reminder_sent_at is None,
    send the parent a reminder notification.
    """
    if now is None:
        now = get_current_ist_datetime()

    sent_count = 0
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(DoseLog)
            .join(Medication, DoseLog.medication_id == Medication.id)
            .options(
                selectinload(DoseLog.medication).selectinload(Medication.member),
                selectinload(DoseLog.medication).selectinload(Medication.household),
            )
            .where(
                DoseLog.status == DoseStatus.pending,
                DoseLog.scheduled_for <= now,
                DoseLog.reminder_sent_at.is_(None),
            )
        )
        due_doses = res.scalars().all()

        for dose in due_doses:
            med = dose.medication
            parent = med.member if med else None
            if not parent:
                continue

            parent_name = parent.name
            med_name = med.name
            dose_text = med.dose_text or "1 मात्रा"

            text = f"🙏 नमस्कार {parent_name}, {med_name} ({dose_text}) घेण्याची वेळ झाली आहे. घेतल्यावर खालील बटण दाबा."
            btn_id = f"dose_taken:{dose.id}"

            await notify(
                member=parent,
                text=text,
                buttons=[{"id": btn_id, "title": "घेतली ✅"}],
                template_name="saath_med_reminder",
                template_language="mr",
                template_params=[parent_name, med_name],
                template_button_payloads=[btn_id],
            )

            dose.reminder_sent_at = now
            sent_count += 1

            db.add(
                Event(
                    household_id=med.household_id,
                    actor="system:health",
                    action="reminder_sent",
                    reason=f"Medication reminder sent for {med_name} to {parent_name}",
                    payload={"dose_id": dose.id, "medication_id": med.id, "scheduled_for": dose.scheduled_for.isoformat()},
                )
            )

        if sent_count > 0:
            await db.commit()

    return sent_count


async def escalate_missed_doses(now: Optional[datetime] = None) -> int:
    """
    Pending doses with reminder_sent_at older than dose_escalate_after_minutes:
    status -> missed, set escalated_at, notify owner_child_id (or all children).
    Idempotent: escalated at most once.
    """
    if now is None:
        now = get_current_ist_datetime()

    cutoff = now - timedelta(minutes=settings.dose_escalate_after_minutes)
    escalated_count = 0

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(DoseLog)
            .join(Medication, DoseLog.medication_id == Medication.id)
            .options(
                selectinload(DoseLog.medication).selectinload(Medication.member),
                selectinload(DoseLog.medication).selectinload(Medication.owner_child),
                selectinload(DoseLog.medication).selectinload(Medication.household).selectinload(Household.members),
            )
            .where(
                DoseLog.status == DoseStatus.pending,
                DoseLog.reminder_sent_at <= cutoff,
                DoseLog.escalated_at.is_(None),
            )
        )
        missed_doses = res.scalars().all()

        for dose in missed_doses:
            med = dose.medication
            parent = med.member
            parent_name = parent.name if parent else "Parent"
            med_name = med.name
            hh_mm = dose.scheduled_for.strftime("%H:%M")

            dose.status = DoseStatus.missed
            dose.escalated_at = now
            escalated_count += 1

            # Determine who to notify
            recipients: List[Member] = []
            if med.owner_child:
                recipients.append(med.owner_child)
            elif med.household and med.household.members:
                recipients = [m for m in med.household.members if m.role == MemberRole.child]

            msg_text = f"{parent_name} hasn't confirmed taking {med_name} (scheduled {hh_mm}). Please check in with them."

            for child in recipients:
                await notify(
                    member=child,
                    text=msg_text,
                    template_name="saath_dose_missed",
                    template_language="en_US",
                    template_params=[parent_name, med_name, hh_mm],
                )

            db.add(
                Event(
                    household_id=med.household_id,
                    actor="system:health",
                    action="dose_missed_escalated",
                    reason=f"Missed dose escalated for {med_name} ({parent_name})",
                    payload={"dose_id": dose.id, "medication_id": med.id, "scheduled_for": dose.scheduled_for.isoformat()},
                )
            )

        if escalated_count > 0:
            await db.commit()

    return escalated_count


async def record_dose_taken(dose_id: int, member: Member) -> Tuple[DoseTakenResult, Optional[DoseLog], str]:
    """
    Handle dose confirmation tap (dose_taken:<id>).
    """
    now = get_current_ist_datetime()

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(DoseLog)
            .options(
                selectinload(DoseLog.medication).selectinload(Medication.member),
                selectinload(DoseLog.medication).selectinload(Medication.owner_child),
                selectinload(DoseLog.medication).selectinload(Medication.household).selectinload(Household.members),
            )
            .where(DoseLog.id == dose_id)
        )
        dose = res.scalars().first()
        if not dose:
            return DoseTakenResult.not_found, None, "माहिती सापडली नाही."

        med = dose.medication
        if not med or med.household_id != member.household_id:
            return DoseTakenResult.household_mismatch, None, "⚠️ ही नोंदणी तुमच्या कुटुंबाची नाही."

        if dose.status == DoseStatus.taken:
            return DoseTakenResult.already_taken, dose, "आधीच नोंदवले आहे 🙏"

        was_missed = (dose.status == DoseStatus.missed)
        dose.status = DoseStatus.taken
        dose.responded_at = now

        db.add(
            Event(
                household_id=med.household_id,
                actor=f"member:{member.name}",
                action="dose_taken",
                reason=f"Dose marked taken by {member.name}",
                payload={"dose_id": dose.id, "medication_id": med.id, "was_missed": was_missed},
            )
        )
        await db.commit()
        await db.refresh(dose)

        if was_missed:
            parent_name = med.member.name if med.member else "Parent"
            med_name = med.name
            update_text = f"Update: {parent_name} has now taken {med_name}."

            recipients: List[Member] = []
            if med.owner_child:
                recipients.append(med.owner_child)
            elif med.household and med.household.members:
                recipients = [m for m in med.household.members if m.role == MemberRole.child]

            for child in recipients:
                await notify(member=child, text=update_text)

            return DoseTakenResult.late_ok, dose, "✅ नोंद केली. धन्यवाद! 🙏"

        return DoseTakenResult.ok, dose, "✅ नोंद केली. धन्यवाद! 🙏"

