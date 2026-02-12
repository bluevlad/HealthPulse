"""Admin Routes - 관리자 페이지"""

import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import bcrypt
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from src.config import settings
from src.database import get_session
from src.database.models import Recipient, Article, SendHistory

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["now"] = datetime.now

# Admin session management
ADMIN_SESSION_COOKIE = "hp_admin_session"
ADMIN_SESSION_MAX_AGE = 3600 * 8

_admin_sessions: dict[str, datetime] = {}


def verify_admin_session(session_token: str) -> bool:
    if not session_token or session_token not in _admin_sessions:
        return False
    expires_at = _admin_sessions[session_token]
    if datetime.now() > expires_at:
        _admin_sessions.pop(session_token, None)
        return False
    return True


def _require_admin_or_redirect(request: Request):
    session_token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not verify_admin_session(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)
    return None


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    session_token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if verify_admin_session(session_token):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse("admin/login.html", {
        "request": request, "title": "관리자 로그인 - HealthPulse",
    })


@router.post("/admin/login", response_class=HTMLResponse)
async def admin_login_submit(request: Request, password: str = Form(...)):
    if not settings.admin_password:
        security_logger.error("ADMIN_PASSWORD not configured")
        raise HTTPException(status_code=500, detail="Admin password not configured")

    if password == settings.admin_password:
        security_logger.info("Admin login success from %s", request.client.host)
        token = secrets.token_hex(32)
        _admin_sessions[token] = datetime.now() + timedelta(seconds=ADMIN_SESSION_MAX_AGE)
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            key=ADMIN_SESSION_COOKIE, value=token,
            max_age=ADMIN_SESSION_MAX_AGE, httponly=True, samesite="lax",
        )
        return response
    else:
        security_logger.warning("Admin login failed from %s", request.client.host)
        return templates.TemplateResponse("admin/login.html", {
            "request": request, "title": "관리자 로그인 - HealthPulse",
            "error": "비밀번호가 올바르지 않습니다.",
        })


@router.get("/admin/logout")
async def admin_logout(request: Request):
    session_token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if session_token:
        _admin_sessions.pop(session_token, None)
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(ADMIN_SESSION_COOKIE)
    return response


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, date: Optional[str] = None):
    redirect = _require_admin_or_redirect(request)
    if redirect:
        return redirect

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

        total_subscribers = session.query(Recipient).filter(Recipient.is_active == True).count()

        articles = session.query(Article).filter(
            Article.collected_at >= start_of_day, Article.collected_at <= end_of_day
        ).order_by(Article.importance_score.desc()).all()

        send_history = session.query(SendHistory).options(
            joinedload(SendHistory.recipient)
        ).filter(
            SendHistory.sent_at >= start_of_day, SendHistory.sent_at <= end_of_day
        ).all()

        total_sent = len(send_history)
        successful_sends = sum(1 for h in send_history if h.is_success)

        send_details = []
        for history in send_history:
            r = history.recipient
            send_details.append({
                "recipient_name": r.name if r else "삭제된 사용자",
                "recipient_email": r.email if r else "-",
                "subject": history.subject,
                "article_count": history.article_count,
                "is_success": history.is_success,
                "error_message": history.error_message,
                "sent_at": history.sent_at
            })

        available_dates = session.query(
            func.date(Article.collected_at).label('date')
        ).distinct().order_by(func.date(Article.collected_at).desc()).limit(30).all()

        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request, "title": "관리자 대시보드 - HealthPulse",
            "selected_date": selected_date,
            "total_subscribers": total_subscribers,
            "articles": articles, "article_count": len(articles),
            "total_sent": total_sent,
            "successful_sends": successful_sends,
            "failed_sends": total_sent - successful_sends,
            "send_details": send_details,
            "available_dates": [d[0] for d in available_dates]
        })


@router.get("/admin/subscribers", response_class=HTMLResponse)
async def admin_subscribers(request: Request, page: int = 1, status: str = "all"):
    redirect = _require_admin_or_redirect(request)
    if redirect:
        return redirect

    with get_session() as session:
        per_page = 20
        offset = (page - 1) * per_page

        query = session.query(Recipient)
        if status == "active":
            query = query.filter(Recipient.is_active == True)
        elif status == "inactive":
            query = query.filter(Recipient.is_active == False)

        total_count = query.count()
        subscribers = query.order_by(Recipient.created_at.desc()).offset(offset).limit(per_page).all()
        total_pages = (total_count + per_page - 1) // per_page
        active_count = session.query(Recipient).filter(Recipient.is_active == True).count()
        inactive_count = session.query(Recipient).filter(Recipient.is_active == False).count()

        return templates.TemplateResponse("admin/subscribers.html", {
            "request": request, "title": "구독자 관리 - HealthPulse",
            "subscribers": subscribers, "page": page,
            "total_pages": total_pages, "total_count": total_count,
            "active_count": active_count, "inactive_count": inactive_count,
            "status_filter": status
        })


@router.get("/admin/send-history", response_class=HTMLResponse)
async def admin_send_history(request: Request, date: Optional[str] = None, page: int = 1):
    redirect = _require_admin_or_redirect(request)
    if redirect:
        return redirect

    with get_session() as session:
        per_page = 30
        offset = (page - 1) * per_page
        query = session.query(SendHistory)

        selected_date = None
        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
                start_of_day = datetime.combine(selected_date, datetime.min.time())
                end_of_day = datetime.combine(selected_date, datetime.max.time())
                query = query.filter(SendHistory.sent_at >= start_of_day, SendHistory.sent_at <= end_of_day)
            except ValueError:
                pass

        total_count = query.count()
        history_items = query.options(
            joinedload(SendHistory.recipient)
        ).order_by(SendHistory.sent_at.desc()).offset(offset).limit(per_page).all()
        total_pages = (total_count + per_page - 1) // per_page

        history_details = []
        for item in history_items:
            r = item.recipient
            history_details.append({
                "id": item.id,
                "recipient_name": r.name if r else "삭제된 사용자",
                "recipient_email": r.email if r else "-",
                "subject": item.subject, "article_count": item.article_count,
                "report_date": item.report_date, "is_success": item.is_success,
                "error_message": item.error_message, "sent_at": item.sent_at
            })

        available_dates = session.query(
            func.date(SendHistory.sent_at).label('date')
        ).distinct().order_by(func.date(SendHistory.sent_at).desc()).limit(30).all()

        return templates.TemplateResponse("admin/send_history.html", {
            "request": request, "title": "발송 이력 - HealthPulse",
            "history_items": history_details, "page": page,
            "total_pages": total_pages, "total_count": total_count,
            "selected_date": selected_date, "available_dates": [d[0] for d in available_dates]
        })


@router.get("/admin/articles", response_class=HTMLResponse)
async def admin_articles(request: Request, date: Optional[str] = None, page: int = 1):
    redirect = _require_admin_or_redirect(request)
    if redirect:
        return redirect

    with get_session() as session:
        per_page = 30
        offset = (page - 1) * per_page
        query = session.query(Article)

        selected_date = None
        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
                start_of_day = datetime.combine(selected_date, datetime.min.time())
                end_of_day = datetime.combine(selected_date, datetime.max.time())
                query = query.filter(Article.collected_at >= start_of_day, Article.collected_at <= end_of_day)
            except ValueError:
                pass

        total_count = query.count()
        articles = query.order_by(Article.collected_at.desc()).offset(offset).limit(per_page).all()
        total_pages = (total_count + per_page - 1) // per_page

        available_dates = session.query(
            func.date(Article.collected_at).label('date')
        ).distinct().order_by(func.date(Article.collected_at).desc()).limit(30).all()

        return templates.TemplateResponse("admin/articles.html", {
            "request": request, "title": "수집 기사 - HealthPulse",
            "articles": articles, "page": page,
            "total_pages": total_pages, "total_count": total_count,
            "selected_date": selected_date, "available_dates": [d[0] for d in available_dates]
        })
