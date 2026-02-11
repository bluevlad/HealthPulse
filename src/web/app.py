"""
HealthPulse Web Application
Subscription management and newsletter preview
"""

import re
import secrets
import hashlib
import json
import logging
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.database import init_db, get_session, RecipientRepository, ArticleRepository
from src.database.models import Recipient, Article, EmailVerification
from src.reporter import ReportGenerator
from src.mailer import GmailSender

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="HealthPulse",
    description="디지털 헬스케어 뉴스 구독 서비스",
    version="1.0.0"
)

# Setup templates and static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["now"] = datetime.now
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Initialize database
init_db(settings.database_url)

# Constants
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_EXPIRY_MINUTES = 10
MAX_VERIFICATION_ATTEMPTS = 5


def generate_token(email: str) -> str:
    """Generate a unique token for email verification/unsubscribe"""
    data = f"{email}{secrets.token_hex(16)}{datetime.now().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=VERIFICATION_CODE_LENGTH))


def keywords_to_json(keywords_str: str) -> Optional[str]:
    """Convert comma-separated keywords to JSON string"""
    if not keywords_str:
        return None
    keyword_list = [k.strip() for k in keywords_str.split(",") if k.strip()]
    return json.dumps(keyword_list, ensure_ascii=False) if keyword_list else None


def json_to_keywords(json_str: Optional[str]) -> List[str]:
    """Convert JSON string to keyword list"""
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except:
        return []


def get_today_article_count() -> int:
    """Get count of today's processed articles"""
    with get_session() as session:
        today = datetime.now().date()
        count = session.query(Article).filter(
            Article.is_processed == True,
            Article.collected_at >= datetime.combine(today, datetime.min.time())
        ).count()
        return count


def get_db():
    """Database session dependency"""
    with get_session() as session:
        yield session


def send_verification_email(email: str, name: str, code: str) -> bool:
    """Send verification code email"""
    try:
        sender = GmailSender()
        if not sender.is_configured:
            logger.error("Gmail sender not configured")
            return False

        subject = "[HealthPulse] 이메일 인증 코드"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .code {{ font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 8px; text-align: center; padding: 20px; background: white; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>HealthPulse</h1>
                    <p>이메일 인증</p>
                </div>
                <div class="content">
                    <p>안녕하세요, <strong>{name}</strong>님!</p>
                    <p>HealthPulse 뉴스레터 구독을 위한 인증 코드입니다:</p>
                    <div class="code">{code}</div>
                    <p>이 코드는 <strong>{VERIFICATION_EXPIRY_MINUTES}분</strong> 후에 만료됩니다.</p>
                    <p>본인이 요청하지 않은 경우 이 이메일을 무시해주세요.</p>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} HealthPulse. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        result = sender.send(
            recipient=email,
            subject=subject,
            html_content=html_content
        )

        return result.success

    except Exception as e:
        logger.exception(f"Failed to send verification email: {e}")
        return False


# ==================== Pages ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with subscription form"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "HealthPulse - 헬스케어 뉴스레터"
    })


@app.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request):
    """Subscription page"""
    return templates.TemplateResponse("subscribe.html", {
        "request": request,
        "title": "구독 신청 - HealthPulse"
    })


@app.post("/subscribe", response_class=HTMLResponse)
async def subscribe_submit(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default="")
):
    """Handle subscription form submission - send verification code"""
    # Validate email format
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(email):
        return templates.TemplateResponse("subscribe.html", {
            "request": request,
            "title": "구독 신청 - HealthPulse",
            "error": "올바른 이메일 형식이 아닙니다. 다시 확인해주세요.",
            "email": email,
            "name": name,
            "keywords": keywords
        })

    with get_session() as session:
        # Check if already subscribed
        existing = session.query(Recipient).filter(Recipient.email == email).first()

        if existing:
            if existing.is_active:
                # Already subscribed - show option to receive today's newsletter
                article_count = get_today_article_count()

                # Generate token if not exists
                if not existing.unsubscribe_token:
                    existing.unsubscribe_token = generate_token(email)
                    session.commit()

                return templates.TemplateResponse("already_subscribed.html", {
                    "request": request,
                    "title": "이미 등록된 구독자",
                    "email": email,
                    "name": existing.name,
                    "token": existing.unsubscribe_token,
                    "article_count": article_count
                })
            else:
                # Reactivate - also need verification
                pass

        # Generate verification code
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=VERIFICATION_EXPIRY_MINUTES)

        # Delete old verification records for this email
        session.query(EmailVerification).filter(
            EmailVerification.email == email
        ).delete()

        # Create new verification record
        verification = EmailVerification(
            email=email,
            name=name,
            code=code,
            is_verified=False,
            attempts=0,
            created_at=datetime.now(),
            expires_at=expires_at
        )
        session.add(verification)
        session.commit()

        # Store keywords in session (we'll use a hidden field)
        verification_id = verification.id

        # Send verification email
        if send_verification_email(email, name, code):
            return templates.TemplateResponse("verify_code.html", {
                "request": request,
                "title": "이메일 인증 - HealthPulse",
                "email": email,
                "name": name,
                "keywords": keywords,
                "verification_id": verification_id,
                "expiry_minutes": VERIFICATION_EXPIRY_MINUTES
            })
        else:
            # Failed to send email
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request,
                "title": "인증 코드 발송 실패",
                "success": False,
                "message": "인증 코드 이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요."
            })


@app.post("/verify", response_class=HTMLResponse)
async def verify_code(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default=""),
    verification_id: int = Form(...),
    code: str = Form(...)
):
    """Verify the email verification code"""
    with get_session() as session:
        # Find verification record
        verification = session.query(EmailVerification).filter(
            EmailVerification.id == verification_id,
            EmailVerification.email == email
        ).first()

        if not verification:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request,
                "title": "인증 실패",
                "success": False,
                "message": "인증 정보를 찾을 수 없습니다. 다시 구독 신청해주세요."
            })

        # Check if expired
        if datetime.now() > verification.expires_at:
            return templates.TemplateResponse("verify_code.html", {
                "request": request,
                "title": "이메일 인증 - HealthPulse",
                "email": email,
                "name": name,
                "keywords": keywords,
                "verification_id": verification_id,
                "expiry_minutes": VERIFICATION_EXPIRY_MINUTES,
                "error": "인증 코드가 만료되었습니다. 재발송 버튼을 눌러주세요."
            })

        # Check attempts
        if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request,
                "title": "인증 실패",
                "success": False,
                "message": "인증 시도 횟수를 초과했습니다. 다시 구독 신청해주세요."
            })

        # Verify code
        if verification.code != code.strip():
            verification.attempts += 1
            session.commit()
            remaining = MAX_VERIFICATION_ATTEMPTS - verification.attempts

            return templates.TemplateResponse("verify_code.html", {
                "request": request,
                "title": "이메일 인증 - HealthPulse",
                "email": email,
                "name": name,
                "keywords": keywords,
                "verification_id": verification_id,
                "expiry_minutes": VERIFICATION_EXPIRY_MINUTES,
                "error": f"인증 코드가 일치하지 않습니다. (남은 시도: {remaining}회)"
            })

        # Code verified! Show subscription options
        verification.is_verified = True
        session.commit()

        # Get today's article count
        article_count = get_today_article_count()

        return templates.TemplateResponse("subscribe_option.html", {
            "request": request,
            "title": "구독 옵션 선택 - HealthPulse",
            "email": email,
            "name": name,
            "keywords": keywords,
            "article_count": article_count
        })


@app.post("/complete-subscription", response_class=HTMLResponse)
async def complete_subscription(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default=""),
    subscription_type: str = Form(...)
):
    """Complete subscription with selected option"""
    with get_session() as session:
        # Check if user exists (reactivation case)
        existing = session.query(Recipient).filter(Recipient.email == email).first()

        if existing:
            existing.is_active = True
            existing.name = name
            existing.keywords = keywords_to_json(keywords)
            existing.unsubscribe_token = generate_token(email)
            session.commit()
            recipient = existing
        else:
            # Create new subscription
            new_recipient = Recipient(
                email=email,
                name=name,
                is_active=True,
                keywords=keywords_to_json(keywords),
                unsubscribe_token=generate_token(email),
                created_at=datetime.now()
            )
            session.add(new_recipient)
            session.commit()
            recipient = new_recipient

        # Handle based on subscription type
        send_today = subscription_type in ["once", "daily"]
        is_daily_subscription = subscription_type in ["daily", "daily_only"]

        # If "once" option, mark as inactive after sending
        if subscription_type == "once":
            recipient.is_active = False
            session.commit()

        # Send today's newsletter if requested
        newsletter_sent = False
        if send_today:
            today = datetime.now().date()
            articles = session.query(Article).filter(
                Article.is_processed == True,
                Article.collected_at >= datetime.combine(today, datetime.min.time())
            ).order_by(Article.importance_score.desc()).all()

            if articles:
                try:
                    generator = ReportGenerator()
                    sender = GmailSender()

                    if sender.is_configured:
                        report_date = datetime.now()
                        subject = f"[HealthPulse] {report_date.strftime('%Y-%m-%d')} 헬스케어 뉴스 브리핑"

                        html_content = generator.generate_daily_report(
                            articles=articles,
                            report_date=report_date,
                            recipient_name=name
                        )

                        result = sender.send(
                            recipient=email,
                            subject=subject,
                            html_content=html_content
                        )

                        if result.success:
                            newsletter_sent = True
                            logger.info(f"Newsletter sent to {email}")
                except Exception as e:
                    logger.exception(f"Error sending newsletter: {e}")

        # Generate result message
        if subscription_type == "once":
            if newsletter_sent:
                message = f"{name}님, 오늘의 뉴스 브리핑이 발송되었습니다!"
                sub_message = "일회성 발송으로 별도 구독 등록은 하지 않았습니다."
            else:
                message = "오늘 수집된 뉴스가 없습니다."
                sub_message = "내일 다시 시도해주세요."
        elif subscription_type == "daily":
            message = f"{name}님, HealthPulse 뉴스레터 구독을 환영합니다!"
            if newsletter_sent:
                sub_message = "오늘의 뉴스 브리핑이 발송되었으며, 내일부터 매일 아침 뉴스를 받아보실 수 있습니다."
            else:
                sub_message = "내일부터 매일 아침 뉴스 브리핑을 받아보실 수 있습니다."
        else:  # daily_only
            message = f"{name}님, HealthPulse 뉴스레터 구독을 환영합니다!"
            sub_message = "내일부터 매일 아침 뉴스 브리핑을 받아보실 수 있습니다."

        return templates.TemplateResponse("subscribe_result.html", {
            "request": request,
            "title": "구독 완료",
            "success": True,
            "message": message,
            "sub_message": sub_message
        })


@app.post("/resend-code", response_class=HTMLResponse)
async def resend_verification_code(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default="")
):
    """Resend verification code"""
    with get_session() as session:
        # Generate new verification code
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=VERIFICATION_EXPIRY_MINUTES)

        # Delete old verification records for this email
        session.query(EmailVerification).filter(
            EmailVerification.email == email
        ).delete()

        # Create new verification record
        verification = EmailVerification(
            email=email,
            name=name,
            code=code,
            is_verified=False,
            attempts=0,
            created_at=datetime.now(),
            expires_at=expires_at
        )
        session.add(verification)
        session.commit()

        verification_id = verification.id

        # Send verification email
        if send_verification_email(email, name, code):
            return templates.TemplateResponse("verify_code.html", {
                "request": request,
                "title": "이메일 인증 - HealthPulse",
                "email": email,
                "name": name,
                "keywords": keywords,
                "verification_id": verification_id,
                "expiry_minutes": VERIFICATION_EXPIRY_MINUTES,
                "message": "새로운 인증 코드가 발송되었습니다."
            })
        else:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request,
                "title": "인증 코드 발송 실패",
                "success": False,
                "message": "인증 코드 이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요."
            })


@app.post("/send-now", response_class=HTMLResponse)
async def send_now(
    request: Request,
    email: str = Form(...)
):
    """Send today's newsletter immediately to the subscriber"""
    with get_session() as session:
        # Find recipient
        recipient = session.query(Recipient).filter(
            Recipient.email == email,
            Recipient.is_active == True
        ).first()

        if not recipient:
            return templates.TemplateResponse("send_result.html", {
                "request": request,
                "title": "발송 실패",
                "success": False,
                "message": "구독 정보를 찾을 수 없습니다.",
                "email": email
            })

        # Get today's processed articles
        today = datetime.now().date()
        articles = session.query(Article).filter(
            Article.is_processed == True,
            Article.collected_at >= datetime.combine(today, datetime.min.time())
        ).order_by(Article.importance_score.desc()).all()

        if not articles:
            return templates.TemplateResponse("send_result.html", {
                "request": request,
                "title": "발송 실패",
                "success": False,
                "message": "오늘 수집된 뉴스가 없습니다. 잠시 후 다시 시도해주세요.",
                "email": email
            })

        # Generate report
        try:
            generator = ReportGenerator()
            sender = GmailSender()

            if not sender.is_configured:
                return templates.TemplateResponse("send_result.html", {
                    "request": request,
                    "title": "발송 실패",
                    "success": False,
                    "message": "이메일 발송 설정이 완료되지 않았습니다.",
                    "email": email
                })

            # Generate HTML report
            report_date = datetime.now()
            subject = f"[HealthPulse] {report_date.strftime('%Y-%m-%d')} 헬스케어 뉴스 브리핑"

            html_content = generator.generate_daily_report(
                articles=articles,
                report_date=report_date,
                recipient_name=recipient.name
            )

            # Send email
            result = sender.send(
                recipient=recipient.email,
                subject=subject,
                html_content=html_content
            )

            if result.success:
                logger.info(f"Newsletter sent to {email}")
                return templates.TemplateResponse("send_result.html", {
                    "request": request,
                    "title": "발송 완료",
                    "success": True,
                    "message": f"오늘의 뉴스 브리핑 ({len(articles)}건)이 발송되었습니다!",
                    "email": email
                })
            else:
                logger.error(f"Failed to send newsletter to {email}: {result.error_message}")
                return templates.TemplateResponse("send_result.html", {
                    "request": request,
                    "title": "발송 실패",
                    "success": False,
                    "message": f"발송 중 오류가 발생했습니다: {result.error_message}",
                    "email": email
                })

        except Exception as e:
            logger.exception(f"Error sending newsletter: {e}")
            return templates.TemplateResponse("send_result.html", {
                "request": request,
                "title": "발송 실패",
                "success": False,
                "message": f"발송 중 오류가 발생했습니다: {str(e)}",
                "email": email
            })


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_page(request: Request, token: str):
    """Unsubscribe confirmation page"""
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token,
            Recipient.is_active == True
        ).first()

        if not recipient:
            return templates.TemplateResponse("unsubscribe_result.html", {
                "request": request,
                "title": "유효하지 않은 링크",
                "success": False,
                "message": "유효하지 않거나 이미 사용된 구독 해지 링크입니다."
            })

        return templates.TemplateResponse("unsubscribe.html", {
            "request": request,
            "title": "구독 해지 - HealthPulse",
            "token": token,
            "email": recipient.email
        })


@app.post("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_submit(request: Request, token: str):
    """Handle unsubscribe confirmation"""
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token,
            Recipient.is_active == True
        ).first()

        if not recipient:
            return templates.TemplateResponse("unsubscribe_result.html", {
                "request": request,
                "title": "유효하지 않은 링크",
                "success": False,
                "message": "유효하지 않거나 이미 사용된 구독 해지 링크입니다."
            })

        # Deactivate subscription
        recipient.is_active = False
        session.commit()

        return templates.TemplateResponse("unsubscribe_result.html", {
            "request": request,
            "title": "구독 해지 완료",
            "success": True,
            "message": "HealthPulse 뉴스레터 구독이 해지되었습니다."
        })


@app.get("/manage/{token}", response_class=HTMLResponse)
async def manage_subscription(request: Request, token: str):
    """Subscription management page"""
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token
        ).first()

        if not recipient:
            raise HTTPException(status_code=404, detail="구독 정보를 찾을 수 없습니다")

        # Convert keywords JSON to list for template
        keywords_list = json_to_keywords(recipient.keywords)

        return templates.TemplateResponse("manage.html", {
            "request": request,
            "title": "구독 관리 - HealthPulse",
            "recipient": recipient,
            "keywords_list": keywords_list,
            "token": token
        })


@app.post("/manage/{token}", response_class=HTMLResponse)
async def update_subscription(
    request: Request,
    token: str,
    name: str = Form(...),
    keywords: str = Form(default="")
):
    """Update subscription preferences"""
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token
        ).first()

        if not recipient:
            raise HTTPException(status_code=404, detail="구독 정보를 찾을 수 없습니다")

        recipient.name = name
        recipient.keywords = keywords_to_json(keywords)
        session.commit()

        keywords_list = json_to_keywords(recipient.keywords)

        return templates.TemplateResponse("manage.html", {
            "request": request,
            "title": "구독 관리 - HealthPulse",
            "recipient": recipient,
            "keywords_list": keywords_list,
            "token": token,
            "message": "설정이 저장되었습니다."
        })


# ==================== Admin Pages ====================

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, date: Optional[str] = None):
    """Admin dashboard - daily overview"""
    with get_session() as session:
        # Parse date parameter or use today
        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.now().date()
        else:
            selected_date = datetime.now().date()

        start_of_day = datetime.combine(selected_date, datetime.min.time())
        end_of_day = datetime.combine(selected_date, datetime.max.time())

        # Get statistics for the selected date
        # 1. Total subscribers
        total_subscribers = session.query(Recipient).filter(Recipient.is_active == True).count()

        # 2. Articles collected on the date
        articles = session.query(Article).filter(
            Article.collected_at >= start_of_day,
            Article.collected_at <= end_of_day
        ).order_by(Article.importance_score.desc()).all()

        # 3. Send history for the date
        from src.database.models import SendHistory
        send_history = session.query(SendHistory).filter(
            SendHistory.sent_at >= start_of_day,
            SendHistory.sent_at <= end_of_day
        ).all()

        # Calculate stats
        total_sent = len(send_history)
        successful_sends = sum(1 for h in send_history if h.is_success)
        failed_sends = total_sent - successful_sends

        # Get recipient details for send history
        send_details = []
        for history in send_history:
            recipient = session.query(Recipient).filter(Recipient.id == history.recipient_id).first()
            send_details.append({
                "recipient_name": recipient.name if recipient else "삭제된 사용자",
                "recipient_email": recipient.email if recipient else "-",
                "subject": history.subject,
                "article_count": history.article_count,
                "is_success": history.is_success,
                "error_message": history.error_message,
                "sent_at": history.sent_at
            })

        # Get list of dates with data (for navigation)
        available_dates = session.query(
            func.date(Article.collected_at).label('date')
        ).distinct().order_by(func.date(Article.collected_at).desc()).limit(30).all()

        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request,
            "title": "관리자 대시보드 - HealthPulse",
            "selected_date": selected_date,
            "total_subscribers": total_subscribers,
            "articles": articles,
            "article_count": len(articles),
            "total_sent": total_sent,
            "successful_sends": successful_sends,
            "failed_sends": failed_sends,
            "send_details": send_details,
            "available_dates": [d[0] for d in available_dates]
        })


@app.get("/admin/subscribers", response_class=HTMLResponse)
async def admin_subscribers(request: Request, page: int = 1, status: str = "all"):
    """Admin page - subscriber list"""
    with get_session() as session:
        per_page = 20
        offset = (page - 1) * per_page

        # Build query based on status filter
        query = session.query(Recipient)
        if status == "active":
            query = query.filter(Recipient.is_active == True)
        elif status == "inactive":
            query = query.filter(Recipient.is_active == False)

        total_count = query.count()
        subscribers = query.order_by(Recipient.created_at.desc()).offset(offset).limit(per_page).all()

        total_pages = (total_count + per_page - 1) // per_page

        # Get subscriber statistics
        active_count = session.query(Recipient).filter(Recipient.is_active == True).count()
        inactive_count = session.query(Recipient).filter(Recipient.is_active == False).count()

        return templates.TemplateResponse("admin/subscribers.html", {
            "request": request,
            "title": "구독자 관리 - HealthPulse",
            "subscribers": subscribers,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "active_count": active_count,
            "inactive_count": inactive_count,
            "status_filter": status
        })


@app.get("/admin/send-history", response_class=HTMLResponse)
async def admin_send_history(request: Request, date: Optional[str] = None, page: int = 1):
    """Admin page - send history"""
    with get_session() as session:
        from src.database.models import SendHistory

        per_page = 30
        offset = (page - 1) * per_page

        # Build query
        query = session.query(SendHistory)

        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
                start_of_day = datetime.combine(selected_date, datetime.min.time())
                end_of_day = datetime.combine(selected_date, datetime.max.time())
                query = query.filter(
                    SendHistory.sent_at >= start_of_day,
                    SendHistory.sent_at <= end_of_day
                )
            except ValueError:
                selected_date = None
        else:
            selected_date = None

        total_count = query.count()
        history_items = query.order_by(SendHistory.sent_at.desc()).offset(offset).limit(per_page).all()

        total_pages = (total_count + per_page - 1) // per_page

        # Enrich with recipient info
        history_details = []
        for item in history_items:
            recipient = session.query(Recipient).filter(Recipient.id == item.recipient_id).first()
            history_details.append({
                "id": item.id,
                "recipient_name": recipient.name if recipient else "삭제된 사용자",
                "recipient_email": recipient.email if recipient else "-",
                "subject": item.subject,
                "article_count": item.article_count,
                "report_date": item.report_date,
                "is_success": item.is_success,
                "error_message": item.error_message,
                "sent_at": item.sent_at
            })

        # Get available dates for filter
        available_dates = session.query(
            func.date(SendHistory.sent_at).label('date')
        ).distinct().order_by(func.date(SendHistory.sent_at).desc()).limit(30).all()

        return templates.TemplateResponse("admin/send_history.html", {
            "request": request,
            "title": "발송 이력 - HealthPulse",
            "history_items": history_details,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "selected_date": selected_date,
            "available_dates": [d[0] for d in available_dates]
        })


@app.get("/admin/articles", response_class=HTMLResponse)
async def admin_articles(request: Request, date: Optional[str] = None, page: int = 1):
    """Admin page - collected articles"""
    with get_session() as session:
        per_page = 30
        offset = (page - 1) * per_page

        # Build query
        query = session.query(Article)

        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
                start_of_day = datetime.combine(selected_date, datetime.min.time())
                end_of_day = datetime.combine(selected_date, datetime.max.time())
                query = query.filter(
                    Article.collected_at >= start_of_day,
                    Article.collected_at <= end_of_day
                )
            except ValueError:
                selected_date = None
        else:
            selected_date = None

        total_count = query.count()
        articles = query.order_by(Article.collected_at.desc()).offset(offset).limit(per_page).all()

        total_pages = (total_count + per_page - 1) // per_page

        # Get available dates for filter
        available_dates = session.query(
            func.date(Article.collected_at).label('date')
        ).distinct().order_by(func.date(Article.collected_at).desc()).limit(30).all()

        return templates.TemplateResponse("admin/articles.html", {
            "request": request,
            "title": "수집 기사 - HealthPulse",
            "articles": articles,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "selected_date": selected_date,
            "available_dates": [d[0] for d in available_dates]
        })


# ==================== API Endpoints ====================

@app.get("/api/subscribers/count")
async def get_subscriber_count():
    """Get active subscriber count"""
    with get_session() as session:
        count = session.query(Recipient).filter(Recipient.is_active == True).count()
        return {"count": count}


@app.get("/api/admin/stats")
async def get_admin_stats(date: Optional[str] = None):
    """Get admin statistics for a specific date"""
    with get_session() as session:
        from src.database.models import SendHistory

        if date:
            try:
                selected_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.now().date()
        else:
            selected_date = datetime.now().date()

        start_of_day = datetime.combine(selected_date, datetime.min.time())
        end_of_day = datetime.combine(selected_date, datetime.max.time())

        # Statistics
        article_count = session.query(Article).filter(
            Article.collected_at >= start_of_day,
            Article.collected_at <= end_of_day
        ).count()

        send_count = session.query(SendHistory).filter(
            SendHistory.sent_at >= start_of_day,
            SendHistory.sent_at <= end_of_day
        ).count()

        success_count = session.query(SendHistory).filter(
            SendHistory.sent_at >= start_of_day,
            SendHistory.sent_at <= end_of_day,
            SendHistory.is_success == True
        ).count()

        subscriber_count = session.query(Recipient).filter(Recipient.is_active == True).count()

        return {
            "date": selected_date.isoformat(),
            "article_count": article_count,
            "send_count": send_count,
            "success_count": success_count,
            "subscriber_count": subscriber_count
        }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== Run Server ====================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
