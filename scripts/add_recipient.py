"""
수신자 추가 스크립트

사용법:
    python scripts/add_recipient.py --email user@example.com --name "홍길동" --group executives
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.config import settings
from src.database import init_db, get_session, RecipientRepository
from src.database.models import RecipientGroup


def main():
    parser = argparse.ArgumentParser(description="HealthPulse 수신자 추가")
    parser.add_argument("--email", required=True, help="이메일 주소")
    parser.add_argument("--name", required=True, help="수신자 이름")
    parser.add_argument(
        "--group",
        choices=["executive", "rnd", "marketing", "sales", "all"],
        default="all",
        help="수신자 그룹 (기본값: all)"
    )

    args = parser.parse_args()

    # 그룹 매핑
    group_map = {
        "executive": RecipientGroup.EXECUTIVE,
        "rnd": RecipientGroup.RND,
        "marketing": RecipientGroup.MARKETING,
        "sales": RecipientGroup.SALES,
        "all": RecipientGroup.ALL,
    }

    # 데이터베이스 초기화
    init_db(settings.database_url)

    with get_session() as session:
        # 이미 존재하는지 확인
        existing = RecipientRepository.get_by_email(session, args.email)
        if existing:
            print(f"이미 등록된 이메일입니다: {args.email}")
            return

        # 수신자 추가
        recipient = RecipientRepository.create(
            session,
            email=args.email,
            name=args.name,
            group=group_map[args.group]
        )

        print(f"수신자 추가 완료:")
        print(f"  - 이메일: {recipient.email}")
        print(f"  - 이름: {recipient.name}")
        print(f"  - 그룹: {recipient.group.value}")


if __name__ == "__main__":
    main()
