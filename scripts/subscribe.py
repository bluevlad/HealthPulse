"""
구독 신청 스크립트

사용법:
    python scripts/subscribe.py --email user@example.com --keywords "수젠텍,디지털헬스케어,현장진단"
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from src.subscription.manager import SubscriptionManager
from src.subscription.email_service import SubscriptionEmailService


def main():
    parser = argparse.ArgumentParser(description="HealthPulse 구독 신청")
    parser.add_argument("--email", required=True, help="이메일 주소")
    parser.add_argument("--keywords", required=True, help="검색 키워드 (쉼표 구분)")
    parser.add_argument("--name", help="구독자 이름")

    args = parser.parse_args()

    # 키워드 파싱
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    if not keywords:
        print("오류: 최소 하나 이상의 키워드가 필요합니다.")
        return

    print("\n" + "=" * 50)
    print("HealthPulse 구독 신청")
    print("=" * 50)

    # 구독 신청
    manager = SubscriptionManager()
    subscriber, subscription_key = manager.subscribe(
        email=args.email,
        keywords=keywords,
        name=args.name
    )

    print(f"\n구독 신청 완료!")
    print(f"  - 이메일: {args.email}")
    print(f"  - 키워드: {', '.join(keywords)}")
    print(f"  - 구독 키: {subscription_key}")

    # 이메일 발송
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if gmail_address and gmail_password:
        print("\n구독 키 이메일 발송 중...")

        email_service = SubscriptionEmailService(
            sender_email=gmail_address,
            app_password=gmail_password
        )

        success = email_service.send_subscription_key(
            recipient_email=args.email,
            subscription_key=subscription_key,
            keywords=keywords
        )

        if success:
            print(f"  ✓ 구독 키가 {args.email}로 발송되었습니다.")
            print("\n다음 단계:")
            print("  1. 이메일에서 구독 키를 확인하세요.")
            print("  2. python scripts/verify_subscription.py 를 실행하세요.")
            print("  3. 이메일과 구독 키를 입력하여 인증을 완료하세요.")
        else:
            print("  ✗ 이메일 발송에 실패했습니다.")
            print(f"  수동 인증 키: {subscription_key}")
    else:
        print("\n⚠ Gmail 설정이 없어 이메일을 발송하지 못했습니다.")
        print(f"  수동 인증 키: {subscription_key}")
        print("\n.env 파일에 다음을 설정하세요:")
        print("  GMAIL_ADDRESS=your_email@gmail.com")
        print("  GMAIL_APP_PASSWORD=your_app_password")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
