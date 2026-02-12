"""Public Routes - 구독자 대면 페이지"""

import re
import json
import secrets
import hashlib
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.config import settings
from src.database import get_session
from src.database.models import Recipient, Article, EmailVerification
from src.reporter import ReportGenerator
from src.mailer import GmailSender

logger = logging.getLogger(__name__)

router = APIRouter()

# Templates setup
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["now"] = datetime.now

# Constants
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_EXPIRY_MINUTES = 10
MAX_VERIFICATION_ATTEMPTS = 5


def generate_token(email: str) -> str:
    data = f"{email}{secrets.token_hex(16)}{datetime.now().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def generate_verification_code() -> str:
    return ''.join(random.choices(string.digits, k=VERIFICATION_CODE_LENGTH))


def keywords_to_json(keywords_str: str) -> Optional[str]:
    if not keywords_str:
        return None
    keyword_list = [k.strip() for k in keywords_str.split(",") if k.strip()]
    return json.dumps(keyword_list, ensure_ascii=False) if keyword_list else None


def get_today_article_count() -> int:
    with get_session() as session:
        today = datetime.now().date()
        count = session.query(Article).filter(
            Article.is_processed == True,
            Article.collected_at >= datetime.combine(today, datetime.min.time())
        ).count()
        return count


def send_verification_email(email: str, name: str, code: str) -> bool:
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
                    <p>&copy; {datetime.now().year} HealthPulse. All rights reserved.</p>
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
        logger.exception("Failed to send verification email: %s", e)
        return False


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "HealthPulse - 헬스케어 뉴스레터"
    })


@router.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request):
    return templates.TemplateResponse("subscribe.html", {
        "request": request,
        "title": "구독 신청 - HealthPulse"
    })


@router.post("/subscribe", response_class=HTMLResponse)
async def subscribe_submit(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default="")
):
    name = name.strip()[:50]
    email = email.strip().lower()
    keywords = keywords.strip()[:200]

    if not name or len(name) < 1:
        return templates.TemplateResponse("subscribe.html", {
            "request": request, "title": "구독 신청 - HealthPulse",
            "error": "이름을 입력해주세요.", "email": email, "name": name, "keywords": keywords
        })

    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(email):
        return templates.TemplateResponse("subscribe.html", {
            "request": request, "title": "구독 신청 - HealthPulse",
            "error": "올바른 이메일 형식이 아닙니다.", "email": email, "name": name, "keywords": keywords
        })

    with get_session() as session:
        existing = session.query(Recipient).filter(Recipient.email == email).first()

        if existing:
            if existing.is_active:
                article_count = get_today_article_count()
                if not existing.unsubscribe_token:
                    existing.unsubscribe_token = generate_token(email)
                    session.commit()
                return templates.TemplateResponse("already_subscribed.html", {
                    "request": request, "title": "이미 등록된 구독자",
                    "email": email, "name": existing.name,
                    "token": existing.unsubscribe_token, "article_count": article_count
                })

        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=VERIFICATION_EXPIRY_MINUTES)

        session.query(EmailVerification).filter(EmailVerification.email == email).delete()
        verification = EmailVerification(
            email=email, name=name, code=code, is_verified=False,
            attempts=0, created_at=datetime.now(), expires_at=expires_at
        )
        session.add(verification)
        session.commit()
        verification_id = verification.id

        if send_verification_email(email, name, code):
            return templates.TemplateResponse("verify_code.html", {
                "request": request, "title": "이메일 인증 - HealthPulse",
                "email": email, "name": name, "keywords": keywords,
                "verification_id": verification_id, "expiry_minutes": VERIFICATION_EXPIRY_MINUTES
            })
        else:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request, "title": "인증 코드 발송 실패",
                "success": False, "message": "인증 코드 이메일 발송에 실패했습니다."
            })


@router.post("/verify", response_class=HTMLResponse)
async def verify_code(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default=""),
    verification_id: int = Form(...),
    code: str = Form(...)
):
    with get_session() as session:
        verification = session.query(EmailVerification).filter(
            EmailVerification.id == verification_id, EmailVerification.email == email
        ).first()

        if not verification:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request, "title": "인증 실패",
                "success": False, "message": "인증 정보를 찾을 수 없습니다."
            })

        if datetime.now() > verification.expires_at:
            return templates.TemplateResponse("verify_code.html", {
                "request": request, "title": "이메일 인증 - HealthPulse",
                "email": email, "name": name, "keywords": keywords,
                "verification_id": verification_id, "expiry_minutes": VERIFICATION_EXPIRY_MINUTES,
                "error": "인증 코드가 만료되었습니다."
            })

        if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request, "title": "인증 실패",
                "success": False, "message": "인증 시도 횟수를 초과했습니다."
            })

        if verification.code != code.strip():
            verification.attempts += 1
            session.commit()
            remaining = MAX_VERIFICATION_ATTEMPTS - verification.attempts
            return templates.TemplateResponse("verify_code.html", {
                "request": request, "title": "이메일 인증 - HealthPulse",
                "email": email, "name": name, "keywords": keywords,
                "verification_id": verification_id, "expiry_minutes": VERIFICATION_EXPIRY_MINUTES,
                "error": f"인증 코드가 일치하지 않습니다. (남은 시도: {remaining}회)"
            })

        verification.is_verified = True
        session.commit()
        article_count = get_today_article_count()
        return templates.TemplateResponse("subscribe_option.html", {
            "request": request, "title": "구독 옵션 선택 - HealthPulse",
            "email": email, "name": name, "keywords": keywords, "article_count": article_count
        })


@router.post("/complete-subscription", response_class=HTMLResponse)
async def complete_subscription(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default=""),
    subscription_type: str = Form(...)
):
    with get_session() as session:
        existing = session.query(Recipient).filter(Recipient.email == email).first()

        if existing:
            existing.is_active = True
            existing.name = name
            existing.keywords = keywords_to_json(keywords)
            existing.unsubscribe_token = generate_token(email)
            session.commit()
            recipient = existing
        else:
            new_recipient = Recipient(
                email=email, name=name, is_active=True,
                keywords=keywords_to_json(keywords),
                unsubscribe_token=generate_token(email), created_at=datetime.now()
            )
            session.add(new_recipient)
            session.commit()
            recipient = new_recipient

        send_today = subscription_type in ["once", "daily"]
        if subscription_type == "once":
            recipient.is_active = False
            session.commit()

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
                            articles=articles, report_date=report_date, recipient_name=name
                        )
                        result = sender.send(recipient=email, subject=subject, html_content=html_content)
                        if result.success:
                            newsletter_sent = True
                            logger.info("Newsletter sent to %s", email)
                except Exception as e:
                    logger.exception("Error sending newsletter: %s", e)

        if subscription_type == "once":
            message = f"{name}님, 오늘의 뉴스 브리핑이 발송되었습니다!" if newsletter_sent else "오늘 수집된 뉴스가 없습니다."
            sub_message = "일회성 발송으로 별도 구독 등록은 하지 않았습니다." if newsletter_sent else "내일 다시 시도해주세요."
        elif subscription_type == "daily":
            message = f"{name}님, HealthPulse 뉴스레터 구독을 환영합니다!"
            sub_message = "오늘의 뉴스 브리핑이 발송되었으며, 내일부터 매일 아침 뉴스를 받아보실 수 있습니다." if newsletter_sent else "내일부터 매일 아침 뉴스 브리핑을 받아보실 수 있습니다."
        else:
            message = f"{name}님, HealthPulse 뉴스레터 구독을 환영합니다!"
            sub_message = "내일부터 매일 아침 뉴스 브리핑을 받아보실 수 있습니다."

        return templates.TemplateResponse("subscribe_result.html", {
            "request": request, "title": "구독 완료",
            "success": True, "message": message, "sub_message": sub_message
        })


@router.post("/resend-code", response_class=HTMLResponse)
async def resend_verification_code(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    keywords: str = Form(default="")
):
    with get_session() as session:
        code = generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=VERIFICATION_EXPIRY_MINUTES)
        session.query(EmailVerification).filter(EmailVerification.email == email).delete()
        verification = EmailVerification(
            email=email, name=name, code=code, is_verified=False,
            attempts=0, created_at=datetime.now(), expires_at=expires_at
        )
        session.add(verification)
        session.commit()
        verification_id = verification.id

        if send_verification_email(email, name, code):
            return templates.TemplateResponse("verify_code.html", {
                "request": request, "title": "이메일 인증 - HealthPulse",
                "email": email, "name": name, "keywords": keywords,
                "verification_id": verification_id, "expiry_minutes": VERIFICATION_EXPIRY_MINUTES,
                "message": "새로운 인증 코드가 발송되었습니다."
            })
        else:
            return templates.TemplateResponse("subscribe_result.html", {
                "request": request, "title": "인증 코드 발송 실패",
                "success": False, "message": "인증 코드 이메일 발송에 실패했습니다."
            })


@router.post("/send-now", response_class=HTMLResponse)
async def send_now(request: Request, email: str = Form(...)):
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.email == email, Recipient.is_active == True
        ).first()

        if not recipient:
            return templates.TemplateResponse("send_result.html", {
                "request": request, "title": "발송 실패",
                "success": False, "message": "구독 정보를 찾을 수 없습니다.", "email": email
            })

        today = datetime.now().date()
        articles = session.query(Article).filter(
            Article.is_processed == True,
            Article.collected_at >= datetime.combine(today, datetime.min.time())
        ).order_by(Article.importance_score.desc()).all()

        if not articles:
            return templates.TemplateResponse("send_result.html", {
                "request": request, "title": "발송 실패",
                "success": False, "message": "오늘 수집된 뉴스가 없습니다.", "email": email
            })

        try:
            generator = ReportGenerator()
            sender = GmailSender()
            if not sender.is_configured:
                return templates.TemplateResponse("send_result.html", {
                    "request": request, "title": "발송 실패",
                    "success": False, "message": "이메일 발송 설정이 완료되지 않았습니다.", "email": email
                })

            report_date = datetime.now()
            subject = f"[HealthPulse] {report_date.strftime('%Y-%m-%d')} 헬스케어 뉴스 브리핑"
            html_content = generator.generate_daily_report(
                articles=articles, report_date=report_date, recipient_name=recipient.name
            )
            result = sender.send(recipient=recipient.email, subject=subject, html_content=html_content)

            if result.success:
                logger.info("Newsletter sent to %s", email)
                return templates.TemplateResponse("send_result.html", {
                    "request": request, "title": "발송 완료",
                    "success": True, "message": f"오늘의 뉴스 브리핑 ({len(articles)}건)이 발송되었습니다!", "email": email
                })
            else:
                return templates.TemplateResponse("send_result.html", {
                    "request": request, "title": "발송 실패",
                    "success": False, "message": f"발송 중 오류가 발생했습니다: {result.error_message}", "email": email
                })
        except Exception as e:
            logger.exception("Error sending newsletter: %s", e)
            return templates.TemplateResponse("send_result.html", {
                "request": request, "title": "발송 실패",
                "success": False, "message": f"발송 중 오류가 발생했습니다: {str(e)}", "email": email
            })


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_page(request: Request, token: str):
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token, Recipient.is_active == True
        ).first()
        if not recipient:
            return templates.TemplateResponse("unsubscribe_result.html", {
                "request": request, "title": "구독 해지",
                "success": False, "message": "유효하지 않은 링크이거나 이미 해지된 구독입니다."
            })
        return templates.TemplateResponse("unsubscribe.html", {
            "request": request, "title": "구독 해지 - HealthPulse",
            "email": recipient.email, "name": recipient.name, "token": token
        })


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_confirm(request: Request, token: str):
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token, Recipient.is_active == True
        ).first()
        if not recipient:
            return templates.TemplateResponse("unsubscribe_result.html", {
                "request": request, "title": "구독 해지",
                "success": False, "message": "유효하지 않은 링크이거나 이미 해지된 구독입니다."
            })
        recipient.is_active = False
        session.commit()
        logger.info("Unsubscribed: %s", recipient.email)
        return templates.TemplateResponse("unsubscribe_result.html", {
            "request": request, "title": "구독 해지 완료",
            "success": True, "message": f"{recipient.name}님의 구독이 해지되었습니다."
        })


@router.get("/manage/{token}", response_class=HTMLResponse)
async def manage_page(request: Request, token: str):
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token, Recipient.is_active == True
        ).first()
        if not recipient:
            return templates.TemplateResponse("unsubscribe_result.html", {
                "request": request, "title": "구독 관리",
                "success": False, "message": "유효하지 않은 링크이거나 이미 해지된 구독입니다."
            })
        keywords = []
        if recipient.keywords:
            try:
                keywords = json.loads(recipient.keywords)
            except Exception:
                pass
        return templates.TemplateResponse("manage.html", {
            "request": request, "title": "구독 관리 - HealthPulse",
            "email": recipient.email, "name": recipient.name,
            "keywords": ", ".join(keywords), "token": token
        })


@router.post("/manage/{token}", response_class=HTMLResponse)
async def manage_update(
    request: Request, token: str,
    name: str = Form(...), keywords: str = Form(default="")
):
    with get_session() as session:
        recipient = session.query(Recipient).filter(
            Recipient.unsubscribe_token == token, Recipient.is_active == True
        ).first()
        if not recipient:
            return templates.TemplateResponse("unsubscribe_result.html", {
                "request": request, "title": "구독 관리",
                "success": False, "message": "유효하지 않은 링크입니다."
            })
        recipient.name = name.strip()[:50]
        recipient.keywords = keywords_to_json(keywords)
        session.commit()
        return templates.TemplateResponse("manage.html", {
            "request": request, "title": "구독 관리 - HealthPulse",
            "email": recipient.email, "name": recipient.name,
            "keywords": keywords, "token": token, "message": "설정이 저장되었습니다."
        })
