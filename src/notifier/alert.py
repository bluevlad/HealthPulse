"""
HealthPulse Alert Notification System
Sends alerts when email delivery fails or other critical events occur
"""

import logging
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from dataclasses import dataclass

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class AlertMessage:
    """Alert message structure"""
    title: str
    message: str
    severity: str = "warning"  # info, warning, error, critical
    timestamp: datetime = None
    details: dict = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AlertNotifier(ABC):
    """Base class for alert notifications"""

    @abstractmethod
    def send_alert(self, alert: AlertMessage) -> bool:
        """Send an alert notification"""
        pass


class EmailAlertNotifier(AlertNotifier):
    """Send alerts via email"""

    def __init__(
        self,
        admin_email: str = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587
    ):
        self.admin_email = admin_email or settings.gmail_address
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = settings.gmail_address
        self.sender_password = settings.gmail_app_password

    def send_alert(self, alert: AlertMessage) -> bool:
        """Send alert email to admin"""
        if not self.sender_email or not self.sender_password:
            logger.warning("Email credentials not configured for alerts")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[HealthPulse Alert] [{alert.severity.upper()}] {alert.title}"
            msg["From"] = self.sender_email
            msg["To"] = self.admin_email

            # Create HTML content
            html_content = self._create_alert_html(alert)
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Alert sent to {self.admin_email}: {alert.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
            return False

    def _create_alert_html(self, alert: AlertMessage) -> str:
        """Create HTML content for alert email"""
        severity_colors = {
            "info": "#17a2b8",
            "warning": "#ffc107",
            "error": "#dc3545",
            "critical": "#721c24"
        }
        color = severity_colors.get(alert.severity, "#6c757d")

        details_html = ""
        if alert.details:
            details_html = "<h3>Details:</h3><ul>"
            for key, value in alert.details.items():
                details_html += f"<li><strong>{key}:</strong> {value}</li>"
            details_html += "</ul>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .alert-box {{
                    border-left: 4px solid {color};
                    background-color: #f8f9fa;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .severity {{
                    display: inline-block;
                    background-color: {color};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }}
                .timestamp {{ color: #6c757d; font-size: 14px; margin-top: 10px; }}
                h2 {{ margin-top: 0; }}
            </style>
        </head>
        <body>
            <h1>HealthPulse System Alert</h1>
            <div class="alert-box">
                <span class="severity">{alert.severity}</span>
                <h2>{alert.title}</h2>
                <p>{alert.message}</p>
                {details_html}
                <p class="timestamp">Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <hr>
            <p style="color: #6c757d; font-size: 12px;">
                This is an automated alert from HealthPulse system.
            </p>
        </body>
        </html>
        """


class ConsoleAlertNotifier(AlertNotifier):
    """Log alerts to console (for development/testing)"""

    def send_alert(self, alert: AlertMessage) -> bool:
        severity_prefix = {
            "info": "INFO",
            "warning": "WARN",
            "error": "ERROR",
            "critical": "CRITICAL"
        }
        prefix = severity_prefix.get(alert.severity, "ALERT")
        logger.warning(f"[{prefix}] {alert.title}: {alert.message}")
        return True


# Alert helper functions
_notifier: Optional[AlertNotifier] = None


def get_notifier() -> AlertNotifier:
    """Get the configured alert notifier"""
    global _notifier
    if _notifier is None:
        _notifier = EmailAlertNotifier()
    return _notifier


def send_delivery_failure_alert(
    recipient_email: str,
    error_message: str,
    article_count: int = 0
):
    """Send alert when email delivery fails"""
    alert = AlertMessage(
        title="Email Delivery Failed",
        message=f"Failed to deliver newsletter to {recipient_email}",
        severity="error",
        details={
            "Recipient": recipient_email,
            "Error": error_message,
            "Article Count": article_count
        }
    )
    get_notifier().send_alert(alert)


def send_collection_failure_alert(
    keyword: str,
    error_message: str
):
    """Send alert when news collection fails"""
    alert = AlertMessage(
        title="News Collection Failed",
        message=f"Failed to collect news for keyword: {keyword}",
        severity="warning",
        details={
            "Keyword": keyword,
            "Error": error_message
        }
    )
    get_notifier().send_alert(alert)


def send_daily_summary_alert(
    total_articles: int,
    sent_count: int,
    failed_count: int
):
    """Send daily operation summary"""
    severity = "info" if failed_count == 0 else "warning"
    alert = AlertMessage(
        title="Daily Newsletter Summary",
        message=f"Newsletter delivery completed. {sent_count} sent, {failed_count} failed.",
        severity=severity,
        details={
            "Total Articles": total_articles,
            "Emails Sent": sent_count,
            "Emails Failed": failed_count,
            "Success Rate": f"{(sent_count / (sent_count + failed_count) * 100):.1f}%" if (sent_count + failed_count) > 0 else "N/A"
        }
    )
    get_notifier().send_alert(alert)
