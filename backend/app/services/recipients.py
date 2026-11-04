"""Who receives family alerts: every child and every guardian (MemberRole.helper)."""
from typing import Iterable, Optional

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Member, MemberRole
from app.db.session import AsyncSessionLocal

ALERT_ROLES = (MemberRole.child, MemberRole.helper)


def is_alert_recipient(member: Member) -> bool:
    return member.role in ALERT_ROLES and bool(member.phone or member.telegram_id)


def guardians_of(members: Iterable[Member]) -> list[Member]:
    """Guardians with a reachable contact, from an already-loaded member list."""
    return [m for m in members if m.role == MemberRole.helper and is_alert_recipient(m)]


async def get_alert_recipients(household_id: int, db: Optional[AsyncSession] = None) -> list[Member]:
    """Children and guardians of the household with a phone or Telegram ID, children first."""
    stmt = (
        select(Member)
        .where(
            Member.household_id == household_id,
            Member.role.in_(ALERT_ROLES),
            or_(Member.phone.isnot(None), Member.telegram_id.isnot(None)),
        )
        .order_by(case((Member.role == MemberRole.child, 0), else_=1), Member.id)
    )
    if db is not None:
        return list((await db.execute(stmt)).scalars().all())
    async with AsyncSessionLocal() as session:
        return list((await session.execute(stmt)).scalars().all())
