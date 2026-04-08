"""
Shared CRUD helpers used by multiple route modules.

Centralizes _get_admin_settings so it is not duplicated across admin.py
and chat.py (Issue 3.5 fix from UPGRADED_DEEP_REPO_AUDIT).
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import AdminSettings

logger = logging.getLogger(__name__)


async def get_admin_settings(db: AsyncSession) -> AdminSettings:
    """
    Fetch the single AdminSettings row, creating it with defaults if absent.
    """
    s = (await db.execute(select(AdminSettings))).scalars().first()
    if not s:
        s = AdminSettings()
        db.add(s)
        await db.commit()
        await db.refresh(s)
        logger.info("Created default AdminSettings row")
    return s
