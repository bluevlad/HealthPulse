"""API Routes - REST API 엔드포인트"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import func, case

from src.database import get_session
from src.database.models import Recipient, Article, SendHistory

from .admin import verify_admin_session, ADMIN_SESSION_COOKIE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/subscribers/count")
async def get_subscriber_count():
    with get_session() as session:
        count = session.query(Recipient).filter(Recipient.is_active == True).count()
        return {"count": count}


@router.get("/admin/stats")
async def get_admin_stats(request: Request, date: Optional[str] = None):
    session_token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not verify_admin_session(session_token):
        raise HTTPException(status_code=401, detail="Admin authentication required")

    with get_session() as session:
        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.now().date()
        else:
            selected_date = datetime.now().date()

        start_of_day = datetime.combine(selected_date, datetime.min.time())
        end_of_day = datetime.combine(selected_date, datetime.max.time())

        article_count = session.query(Article).filter(
            Article.collected_at >= start_of_day, Article.collected_at <= end_of_day
        ).count()

        send_stats = session.query(
            func.count(SendHistory.id).label('total'),
            func.count(case((SendHistory.is_success == True, 1))).label('success')
        ).filter(
            SendHistory.sent_at >= start_of_day, SendHistory.sent_at <= end_of_day
        ).one()

        subscriber_count = session.query(Recipient).filter(Recipient.is_active == True).count()

        return {
            "date": selected_date.isoformat(),
            "article_count": article_count,
            "send_count": send_stats.total,
            "success_count": send_stats.success,
            "subscriber_count": subscriber_count
        }


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
