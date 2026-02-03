"""
전체 파이프라인 테스트 스크립트

수집 → 분석 → 리포트 생성까지 테스트합니다.

사용법:
    python scripts/test_full_pipeline.py
"""

import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

from src.config import settings
from src.database import init_db, get_session, ArticleRepository
from src.database.models import Article, CategoryType
from src.collector import NaverNewsCollector
from src.processor import OllamaSummarizer, ArticleClassifier, ArticleDeduplicator
from src.reporter import ReportGenerator


def main():
    print("\n" + "="*60)
    print("HealthPulse 전체 파이프라인 테스트")
    print("="*60 + "\n")

    # 1. 데이터베이스 초기화
    print("[1/5] 데이터베이스 초기화...")
    init_db(settings.database_url)
    print("      완료\n")

    # 2. 뉴스 수집
    print("[2/5] 뉴스 수집 테스트...")
    try:
        with NaverNewsCollector() as collector:
            articles = collector.search("디지털헬스케어", display=5)
            print(f"      {len(articles)}건 수집됨")
    except ValueError as e:
        print(f"      실패: {e}")
        print("      네이버 API 키를 확인하세요.\n")
        articles = []

    # 3. AI 분석 테스트
    print("\n[3/5] AI 분석 테스트...")

    summarizer = OllamaSummarizer()
    classifier = ArticleClassifier()

    print(f"      Ollama 사용 가능: {summarizer.is_available}")

    if articles:
        test_article = articles[0]
        print(f"\n      테스트 기사: {test_article.title[:40]}...")

        # 요약
        summary = summarizer.summarize(test_article.title, test_article.description)
        print(f"      요약: {summary[:100]}..." if len(summary) > 100 else f"      요약: {summary}")

        # 분류
        category = classifier.classify(test_article.title, test_article.description)
        print(f"      카테고리: {category.value}")

        # 중요도
        importance = summarizer.score_importance(test_article.title, test_article.description)
        print(f"      중요도: {importance:.2%}")

    # 4. 중복 탐지 테스트
    print("\n[4/5] 중복 탐지 테스트...")

    dedup = ArticleDeduplicator()
    print(f"      Sentence-BERT 사용 가능: {dedup.is_available}")

    if len(articles) >= 2:
        # 같은 기사로 중복 테스트
        result = dedup.check_duplicate(
            articles[0].title,
            articles[0].description,
            [dedup.compute_hash(articles[0].title, articles[0].description)],
            {}
        )
        print(f"      동일 기사 중복 테스트: {result.is_duplicate} (유사도: {result.similarity_score:.2%})")

    # 5. 리포트 생성 테스트
    print("\n[5/5] 리포트 생성 테스트...")

    generator = ReportGenerator()

    # 테스트용 Article 객체 생성
    test_articles = []
    for i, art in enumerate(articles):
        test_article = Article(
            id=i+1,
            title=art.title,
            description=art.description,
            link=art.link,
            pub_date=art.pub_date,
            source=art.source,
            category=CategoryType.GENERAL,
            summary=art.description[:100] if art.description else "",
            importance_score=0.5 + (i * 0.1),
        )
        test_articles.append(test_article)

    if test_articles:
        html_report = generator.generate_daily_report(
            articles=test_articles,
            report_date=datetime.now(),
            recipient_name="테스트 사용자"
        )

        # 리포트 저장
        output_path = settings.BASE_DIR / "data" / "test_report.html"
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(html_report, encoding="utf-8")
        print(f"      리포트 저장됨: {output_path}")

    print("\n" + "="*60)
    print("테스트 완료")
    print("="*60 + "\n")

    # 결과 요약
    print("결과 요약:")
    print(f"  - 뉴스 수집: {'성공' if articles else '실패 (API 키 확인 필요)'}")
    print(f"  - Ollama AI: {'사용 가능' if summarizer.is_available else '사용 불가 (키워드 기반 폴백 사용)'}")
    print(f"  - Sentence-BERT: {'사용 가능' if dedup.is_available else '사용 불가 (해시 기반 폴백 사용)'}")
    print(f"  - 리포트 생성: 완료")
    print()


if __name__ == "__main__":
    main()
