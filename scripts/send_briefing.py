"""
뉴스 브리핑 발송 스크립트

인증된 구독자들에게 뉴스 브리핑을 발송합니다.

사용법:
    python scripts/send_briefing.py
    python scripts/send_briefing.py --email specific@email.com
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

from src.subscription.manager import SubscriptionManager
from src.subscription.email_service import SubscriptionEmailService


def collect_news_for_keywords(keywords: list[str]) -> dict:
    """
    키워드 기반으로 뉴스 수집 (웹 검색 시뮬레이션)

    실제 구현에서는 NaverNewsCollector를 사용하거나
    웹 검색 결과를 활용합니다.
    """
    # 현재는 샘플 데이터 사용 (실제 운영 시 API 연동)
    sample_news = {
        "수젠텍 동향": [
            {
                "title": "수젠텍, 디지털 헬스케어 부문 성장세 지속",
                "description": "수젠텍은 여성호르몬 진단 제품 시장 확대로 디지털 헬스케어 부문이 성장 중이며, 원가 부담 완화와 비용 절감으로 영업손실이 개선되고 있다.",
                "source": "바이오타임즈",
                "link": "https://example.com/news1",
                "pub_date": "2025-01-12",
                "importance_score": 0.85
            },
            {
                "title": "수젠텍, DGIST와 알츠하이머 치매 조기진단 키트 공동 개발",
                "description": "수젠텍이 대구경북과학기술원(DGIST)과 함께 국가 연구과제를 수행하며 알츠하이머 치매 조기진단 키트 개발에 나섰다.",
                "source": "연합뉴스",
                "link": "https://example.com/news2",
                "pub_date": "2025-01-11",
                "importance_score": 0.9
            },
        ],
        "체외진단/진단키트": [
            {
                "title": "글로벌 체외진단 시장, 2026년 180조원 규모 전망",
                "description": "세계적인 고령화 추세와 감염성 질환 증가 등으로 체외진단 시장이 더욱 성장할 전망이다. 현재 글로벌 시장 규모는 130조원에 달한다.",
                "source": "바이오타임즈",
                "link": "https://example.com/news3",
                "pub_date": "2025-01-10",
                "importance_score": 0.75
            },
        ],
        "현장진단(POCT)": [
            {
                "title": "분자진단 POC 시장, 연평균 12% 성장 전망",
                "description": "분자진단 POC 시장은 2019년 11.7억 달러에서 2029년 37.3억 달러로 연평균 12.27% 성장이 예상된다.",
                "source": "BRIC",
                "link": "https://example.com/news4",
                "pub_date": "2025-01-09",
                "importance_score": 0.7
            },
        ],
        "디지털 헬스케어": [
            {
                "title": "디지털의료제품법 시행, 한국 의료 현장 변화 시작",
                "description": "2025년 1월 24일 세계 최초로 디지털의료제품법이 시행되어 한국 의료 현장에 가시적인 변화가 포착되고 있다.",
                "source": "한국시니어신문",
                "link": "https://example.com/news5",
                "pub_date": "2025-01-12",
                "importance_score": 0.95
            },
            {
                "title": "디지털헬스케어 투자, 전년 대비 50.7% 급증",
                "description": "헬스케어 분야 투자가 2024년 상반기 892억원에서 2025년 상반기 1,344억원으로 50.7% 급증했다.",
                "source": "KB금융 리서치",
                "link": "https://example.com/news6",
                "pub_date": "2025-01-11",
                "importance_score": 0.85
            },
        ],
    }

    # 키워드에 맞는 뉴스만 필터링
    result = {}
    keywords_lower = [k.lower() for k in keywords]

    for category, news_list in sample_news.items():
        # 카테고리나 키워드가 매칭되는지 확인
        category_lower = category.lower()
        for keyword in keywords_lower:
            if keyword in category_lower or any(keyword in n.get('title', '').lower() for n in news_list):
                if category not in result:
                    result[category] = news_list
                break

    return result


def main():
    parser = argparse.ArgumentParser(description="HealthPulse 뉴스 브리핑 발송")
    parser.add_argument("--email", help="특정 이메일에만 발송")

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("HealthPulse 뉴스 브리핑 발송")
    print("=" * 50)

    # Gmail 설정 확인
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        print("\n오류: Gmail 설정이 필요합니다.")
        print(".env 파일에 다음을 설정하세요:")
        print("  GMAIL_ADDRESS=your_email@gmail.com")
        print("  GMAIL_APP_PASSWORD=your_app_password")
        return

    manager = SubscriptionManager()
    email_service = SubscriptionEmailService(
        sender_email=gmail_address,
        app_password=gmail_password
    )

    # 발송 대상 조회
    if args.email:
        subscriber = manager.get_subscriber_by_email(args.email)
        if not subscriber:
            print(f"\n오류: 구독자를 찾을 수 없습니다: {args.email}")
            return
        if not subscriber.is_verified:
            print(f"\n오류: 인증되지 않은 구독자입니다: {args.email}")
            return
        subscribers = [subscriber]
    else:
        subscribers = manager.get_verified_subscribers()

    if not subscribers:
        print("\n발송할 구독자가 없습니다.")
        return

    print(f"\n발송 대상: {len(subscribers)}명")

    # 각 구독자에게 발송
    success_count = 0
    for subscriber in subscribers:
        try:
            # 키워드 파싱
            keywords = json.loads(subscriber.keywords) if subscriber.keywords else []

            if not keywords:
                logger.warning(f"키워드 없음: {subscriber.email}")
                continue

            print(f"\n처리 중: {subscriber.email}")
            print(f"  키워드: {', '.join(keywords)}")

            # 뉴스 수집
            news_data = collect_news_for_keywords(keywords)

            if not news_data:
                print("  수집된 뉴스 없음, 건너뜀")
                continue

            total_news = sum(len(items) for items in news_data.values())
            print(f"  수집된 뉴스: {total_news}건")

            # 이메일 발송
            success = email_service.send_news_briefing(
                recipient_email=subscriber.email,
                recipient_name=subscriber.name,
                news_data=news_data,
                keywords=keywords
            )

            if success:
                manager.update_last_sent(subscriber.email)
                success_count += 1
                print(f"  ✓ 발송 완료")
            else:
                print(f"  ✗ 발송 실패")

        except Exception as e:
            logger.error(f"발송 오류 ({subscriber.email}): {e}")

    print("\n" + "=" * 50)
    print(f"발송 완료: {success_count}/{len(subscribers)}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
