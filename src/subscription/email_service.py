"""
구독 이메일 서비스 - 구독키 발송 및 뉴스 브리핑 발송
"""

import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


class SubscriptionEmailService:
    """구독 이메일 서비스"""

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(
        self,
        sender_email: str,
        app_password: str,
        template_dir: str = None
    ):
        self.sender_email = sender_email
        self.app_password = app_password

        if template_dir is None:
            template_dir = Path(__file__).parent.parent.parent / "templates"

        self.template_dir = Path(template_dir)

        # Jinja2 환경 설정
        self._env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def is_configured(self) -> bool:
        """이메일 설정 완료 여부"""
        return bool(self.sender_email and self.app_password)

    def send_subscription_key(
        self,
        recipient_email: str,
        subscription_key: str,
        keywords: list[str]
    ) -> bool:
        """
        구독 키 이메일 발송

        Args:
            recipient_email: 수신자 이메일
            subscription_key: 구독 인증 키
            keywords: 구독 키워드 목록

        Returns:
            발송 성공 여부
        """
        subject = "[HealthPulse] 구독 인증 키가 발급되었습니다"

        html_content = self._generate_subscription_key_email(
            subscription_key=subscription_key,
            keywords=keywords,
            email=recipient_email
        )

        return self._send_email(recipient_email, subject, html_content)

    def send_news_briefing(
        self,
        recipient_email: str,
        recipient_name: str,
        news_data: dict,
        keywords: list[str]
    ) -> bool:
        """
        뉴스 브리핑 이메일 발송

        Args:
            recipient_email: 수신자 이메일
            recipient_name: 수신자 이름
            news_data: 뉴스 데이터 딕셔너리
            keywords: 검색 키워드 목록

        Returns:
            발송 성공 여부
        """
        today = datetime.now().strftime("%Y년 %m월 %d일")
        subject = f"[HealthPulse] {today} 헬스케어 뉴스 브리핑"

        html_content = self._generate_news_briefing_email(
            recipient_name=recipient_name,
            news_data=news_data,
            keywords=keywords,
            report_date=datetime.now()
        )

        return self._send_email(recipient_email, subject, html_content)

    def _generate_subscription_key_email(
        self,
        subscription_key: str,
        keywords: list[str],
        email: str
    ) -> str:
        """구독 키 이메일 HTML 생성"""
        try:
            template = self._env.get_template("subscription_key.html")
            return template.render(
                subscription_key=subscription_key,
                keywords=keywords,
                email=email,
                generated_at=datetime.now()
            )
        except Exception as e:
            logger.error(f"템플릿 렌더링 실패: {e}")
            # 폴백 HTML
            return self._fallback_subscription_key_html(subscription_key, keywords)

    def _generate_news_briefing_email(
        self,
        recipient_name: str,
        news_data: dict,
        keywords: list[str],
        report_date: datetime
    ) -> str:
        """뉴스 브리핑 이메일 HTML 생성"""
        try:
            template = self._env.get_template("news_briefing.html")
            return template.render(
                recipient_name=recipient_name,
                news_data=news_data,
                keywords=keywords,
                report_date=report_date,
                generated_at=datetime.now()
            )
        except Exception as e:
            logger.error(f"템플릿 렌더링 실패: {e}")
            # 폴백 HTML
            return self._fallback_news_briefing_html(recipient_name, news_data, keywords)

    def _fallback_subscription_key_html(
        self,
        subscription_key: str,
        keywords: list[str]
    ) -> str:
        """구독 키 폴백 HTML"""
        keywords_str = ", ".join(keywords)
        return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #1e88e5, #1565c0); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="margin: 0;">HealthPulse</h1>
        <p style="margin: 10px 0 0 0;">헬스케어 뉴스 브리핑 서비스</p>
    </div>

    <div style="padding: 30px; background: #f9f9f9; border: 1px solid #ddd;">
        <h2 style="color: #333;">구독 인증 키가 발급되었습니다</h2>

        <p>아래 인증 키를 사용하여 구독을 활성화해 주세요:</p>

        <div style="background: #fff; border: 2px dashed #1e88e5; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px;">
            <span style="font-size: 28px; font-weight: bold; letter-spacing: 3px; color: #1565c0;">
                {subscription_key}
            </span>
        </div>

        <h3 style="color: #555;">구독 키워드</h3>
        <p style="background: #e3f2fd; padding: 15px; border-radius: 5px; color: #1565c0;">
            {keywords_str}
        </p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

        <p style="color: #888; font-size: 12px;">
            이 메일은 HealthPulse 시스템에서 자동 발송되었습니다.<br>
            구독을 신청하지 않으셨다면 이 메일을 무시해 주세요.
        </p>
    </div>
</body>
</html>
"""

    def _fallback_news_briefing_html(
        self,
        recipient_name: str,
        news_data: dict,
        keywords: list[str]
    ) -> str:
        """뉴스 브리핑 폴백 HTML"""
        today = datetime.now().strftime("%Y년 %m월 %d일")
        keywords_str = ", ".join(keywords)

        news_items_html = ""
        for category, items in news_data.items():
            if items:
                news_items_html += f"<h3 style='color: #1565c0; border-bottom: 2px solid #1e88e5; padding-bottom: 10px;'>{category}</h3>"
                for item in items[:5]:
                    title = item.get('title', '')
                    source = item.get('source', '')
                    link = item.get('link', '#')
                    summary = item.get('summary', item.get('description', ''))[:200]

                    news_items_html += f"""
                    <div style="margin-bottom: 20px; padding: 15px; background: #fff; border-left: 4px solid #1e88e5; border-radius: 0 5px 5px 0;">
                        <h4 style="margin: 0 0 8px 0;"><a href="{link}" style="color: #333; text-decoration: none;">{title}</a></h4>
                        <p style="color: #666; font-size: 13px; margin: 0 0 8px 0;">{source}</p>
                        <p style="color: #555; font-size: 14px; margin: 0;">{summary}...</p>
                    </div>
                    """

        return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
    <div style="background: linear-gradient(135deg, #1e88e5, #1565c0); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="margin: 0;">HealthPulse</h1>
        <p style="margin: 10px 0 0 0;">헬스케어 뉴스 브리핑</p>
        <p style="margin: 5px 0 0 0; font-size: 18px;">{today}</p>
    </div>

    <div style="padding: 30px; background: #fff; border: 1px solid #ddd;">
        <p style="color: #333;">{recipient_name or '구독자'}님, 안녕하세요.</p>
        <p style="color: #555;">오늘의 헬스케어 뉴스를 전해드립니다.</p>

        <div style="background: #e3f2fd; padding: 10px 15px; border-radius: 5px; margin: 20px 0;">
            <strong style="color: #1565c0;">검색 키워드:</strong> {keywords_str}
        </div>

        {news_items_html}

        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

        <p style="color: #888; font-size: 12px; text-align: center;">
            이 메일은 HealthPulse 시스템에서 자동 발송되었습니다.<br>
            구독 해지를 원하시면 회신해 주세요.
        </p>
    </div>
</body>
</html>
"""

    def _send_email(
        self,
        recipient: str,
        subject: str,
        html_content: str
    ) -> bool:
        """이메일 발송"""
        if not self.is_configured:
            logger.error("Gmail 설정이 완료되지 않았습니다.")
            return False

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = Header(subject, "utf-8")
            message["From"] = f"HealthPulse <{self.sender_email}>"
            message["To"] = recipient

            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, recipient, message.as_string())

            logger.info(f"이메일 발송 성공: {recipient}")
            return True

        except Exception as e:
            logger.error(f"이메일 발송 실패: {e}")
            return False
