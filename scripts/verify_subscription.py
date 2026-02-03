"""
구독 인증 스크립트

사용법:
    python scripts/verify_subscription.py
    python scripts/verify_subscription.py --email user@example.com --key ABCD1234EFGH5678
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


def main():
    parser = argparse.ArgumentParser(description="HealthPulse 구독 인증")
    parser.add_argument("--email", help="이메일 주소")
    parser.add_argument("--key", help="구독 인증 키")

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("HealthPulse 구독 인증")
    print("=" * 50)

    # 인자로 받지 않은 경우 입력 받기
    email = args.email
    subscription_key = args.key

    if not email:
        email = input("\n이메일 주소를 입력하세요: ").strip()

    if not subscription_key:
        subscription_key = input("구독 인증 키를 입력하세요: ").strip().upper()

    if not email or not subscription_key:
        print("\n오류: 이메일과 구독 키를 모두 입력해야 합니다.")
        return

    # 인증 시도
    manager = SubscriptionManager()
    success = manager.verify(email, subscription_key)

    if success:
        print("\n" + "=" * 50)
        print("  ✓ 구독 인증이 완료되었습니다!")
        print("=" * 50)
        print(f"\n등록된 이메일: {email}")

        # 키워드 조회
        keywords = manager.get_keywords(email)
        if keywords:
            print(f"검색 키워드: {', '.join(keywords)}")

        print("\n매일 오전에 헬스케어 뉴스 브리핑을 받아보실 수 있습니다.")
        print("\n구독 해지를 원하시면:")
        print("  python scripts/unsubscribe.py --email " + email)
    else:
        print("\n" + "=" * 50)
        print("  ✗ 인증에 실패했습니다.")
        print("=" * 50)
        print("\n다음 사항을 확인해 주세요:")
        print("  1. 이메일 주소가 정확한지 확인")
        print("  2. 구독 인증 키가 정확한지 확인 (대문자)")
        print("  3. 구독 신청이 완료되었는지 확인")
        print("\n구독 신청:")
        print('  python scripts/subscribe.py --email your@email.com --keywords "키워드1,키워드2"')

    print()


if __name__ == "__main__":
    main()
