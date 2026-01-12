"""
Gmail SMTP 이메일 발송 모듈
"""

import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from dataclasses import dataclass
from typing import Optional

import aiosmtplib

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """발송 결과"""
    recipient: str
    success: bool
    error_message: Optional[str] = None


class GmailSender:
    """Gmail SMTP 이메일 발송기"""

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SMTP_PORT_SSL = 465

    def __init__(
        self,
        sender_email: str = None,
        app_password: str = None
    ):
        """
        Args:
            sender_email: 발신자 이메일 (Gmail 주소)
            app_password: Gmail 앱 비밀번호

        Note:
            Gmail 앱 비밀번호는 Google 계정 설정에서 생성해야 합니다.
            https://myaccount.google.com/apppasswords
        """
        self.sender_email = sender_email or settings.gmail_address
        self.app_password = app_password or settings.gmail_app_password

        if not self.sender_email or not self.app_password:
            logger.warning(
                "Gmail 설정이 완료되지 않았습니다. "
                ".env 파일에 GMAIL_ADDRESS와 GMAIL_APP_PASSWORD를 설정하세요."
            )

    @property
    def is_configured(self) -> bool:
        """Gmail 설정 완료 여부"""
        return bool(self.sender_email and self.app_password)

    def send(
        self,
        recipient: str,
        subject: str,
        html_content: str,
        sender_name: str = "HealthPulse"
    ) -> SendResult:
        """
        이메일 발송 (동기)

        Args:
            recipient: 수신자 이메일
            subject: 제목
            html_content: HTML 본문
            sender_name: 발신자 이름

        Returns:
            SendResult 객체
        """
        if not self.is_configured:
            return SendResult(
                recipient=recipient,
                success=False,
                error_message="Gmail 설정이 완료되지 않았습니다."
            )

        try:
            # 이메일 메시지 구성
            message = MIMEMultipart("alternative")
            message["Subject"] = Header(subject, "utf-8")
            message["From"] = f"{sender_name} <{self.sender_email}>"
            message["To"] = recipient

            # HTML 본문 추가
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            # SMTP 연결 및 발송
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.sendmail(
                    self.sender_email,
                    recipient,
                    message.as_string()
                )

            logger.info(f"이메일 발송 성공: {recipient}")
            return SendResult(recipient=recipient, success=True)

        except smtplib.SMTPAuthenticationError as e:
            error_msg = "Gmail 인증 실패. 앱 비밀번호를 확인하세요."
            logger.error(f"이메일 발송 실패: {error_msg}")
            return SendResult(recipient=recipient, success=False, error_message=error_msg)

        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"수신자 거부: {recipient}"
            logger.error(f"이메일 발송 실패: {error_msg}")
            return SendResult(recipient=recipient, success=False, error_message=error_msg)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"이메일 발송 실패: {error_msg}")
            return SendResult(recipient=recipient, success=False, error_message=error_msg)

    async def send_async(
        self,
        recipient: str,
        subject: str,
        html_content: str,
        sender_name: str = "HealthPulse"
    ) -> SendResult:
        """
        이메일 발송 (비동기)

        Args:
            recipient: 수신자 이메일
            subject: 제목
            html_content: HTML 본문
            sender_name: 발신자 이름

        Returns:
            SendResult 객체
        """
        if not self.is_configured:
            return SendResult(
                recipient=recipient,
                success=False,
                error_message="Gmail 설정이 완료되지 않았습니다."
            )

        try:
            # 이메일 메시지 구성
            message = MIMEMultipart("alternative")
            message["Subject"] = Header(subject, "utf-8")
            message["From"] = f"{sender_name} <{self.sender_email}>"
            message["To"] = recipient

            # HTML 본문 추가
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            # 비동기 SMTP 연결 및 발송
            await aiosmtplib.send(
                message,
                hostname=self.SMTP_SERVER,
                port=self.SMTP_PORT,
                start_tls=True,
                username=self.sender_email,
                password=self.app_password,
            )

            logger.info(f"이메일 발송 성공: {recipient}")
            return SendResult(recipient=recipient, success=True)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"이메일 발송 실패 ({recipient}): {error_msg}")
            return SendResult(recipient=recipient, success=False, error_message=error_msg)

    def send_batch(
        self,
        recipients: list[str],
        subject: str,
        html_content: str,
        sender_name: str = "HealthPulse"
    ) -> list[SendResult]:
        """
        다수 수신자에게 일괄 발송 (동기)

        Args:
            recipients: 수신자 이메일 리스트
            subject: 제목
            html_content: HTML 본문
            sender_name: 발신자 이름

        Returns:
            SendResult 리스트
        """
        results = []
        for recipient in recipients:
            result = self.send(recipient, subject, html_content, sender_name)
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        logger.info(f"일괄 발송 완료: {success_count}/{len(recipients)} 성공")

        return results

    async def send_batch_async(
        self,
        recipients: list[str],
        subject: str,
        html_content: str,
        sender_name: str = "HealthPulse"
    ) -> list[SendResult]:
        """
        다수 수신자에게 일괄 발송 (비동기)

        Args:
            recipients: 수신자 이메일 리스트
            subject: 제목
            html_content: HTML 본문
            sender_name: 발신자 이름

        Returns:
            SendResult 리스트
        """
        tasks = [
            self.send_async(recipient, subject, html_content, sender_name)
            for recipient in recipients
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외를 SendResult로 변환
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(SendResult(
                    recipient=recipients[i],
                    success=False,
                    error_message=str(result)
                ))
            else:
                final_results.append(result)

        success_count = sum(1 for r in final_results if r.success)
        logger.info(f"비동기 일괄 발송 완료: {success_count}/{len(recipients)} 성공")

        return final_results


# 편의 함수
_sender: Optional[GmailSender] = None


def get_sender() -> GmailSender:
    """싱글톤 발송기 반환"""
    global _sender
    if _sender is None:
        _sender = GmailSender()
    return _sender


if __name__ == "__main__":
    # 테스트 실행
    import os
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    sender = GmailSender()

    print(f"Gmail 설정 완료: {sender.is_configured}")

    if sender.is_configured:
        # 테스트 이메일 발송
        test_html = """
        <html>
        <body>
            <h1>HealthPulse 테스트 이메일</h1>
            <p>이 메일은 테스트용입니다.</p>
        </body>
        </html>
        """

        # 본인 이메일로 테스트
        result = sender.send(
            recipient=sender.sender_email,
            subject="[테스트] HealthPulse 이메일 발송 테스트",
            html_content=test_html
        )

        print(f"발송 결과: {'성공' if result.success else '실패'}")
        if not result.success:
            print(f"에러: {result.error_message}")
    else:
        print("Gmail 설정이 필요합니다. .env 파일을 확인하세요.")
