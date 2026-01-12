"""
뉴스 수집 테스트 스크립트

사용법:
    python scripts/test_collection.py
    python scripts/test_collection.py --keyword "디지털헬스케어" --count 5
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from src.collector import NaverNewsCollector


def main():
    parser = argparse.ArgumentParser(description="네이버 뉴스 수집 테스트")
    parser.add_argument("--keyword", default="디지털헬스케어", help="검색 키워드")
    parser.add_argument("--count", type=int, default=5, help="수집 건수")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"네이버 뉴스 검색 테스트")
    print(f"키워드: {args.keyword}")
    print(f"{'='*60}\n")

    try:
        with NaverNewsCollector() as collector:
            articles = collector.search(args.keyword, display=args.count)

            if not articles:
                print("검색 결과가 없습니다.")
                return

            print(f"총 {len(articles)}건 검색됨\n")

            for i, article in enumerate(articles, 1):
                print(f"[{i}] {article.title}")
                print(f"    출처: {article.source or '알 수 없음'}")
                print(f"    날짜: {article.pub_date}")
                print(f"    링크: {article.link}")
                print(f"    설명: {article.description[:100]}..." if len(article.description) > 100 else f"    설명: {article.description}")
                print()

    except ValueError as e:
        print(f"\n오류: {e}")
        print("\n.env 파일에 네이버 API 키를 설정하세요:")
        print("  NAVER_CLIENT_ID=your_client_id")
        print("  NAVER_CLIENT_SECRET=your_client_secret")


if __name__ == "__main__":
    main()
