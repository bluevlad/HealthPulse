"""
HealthPulse 메인 실행 파일

디지털 헬스케어 뉴스 모니터링 시스템
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.database import init_db, get_session, ArticleRepository, RecipientRepository, SendHistoryRepository
from src.database.models import CategoryType
from src.collector import NaverNewsCollector
from src.processor import OllamaSummarizer, ArticleClassifier, ArticleDeduplicator
from src.reporter import ReportGenerator
from src.mailer import GmailSender

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            settings.BASE_DIR / "logs" / "healthpulse.log",
            encoding="utf-8"
        ),
    ],
)

logger = logging.getLogger(__name__)


# 기본 검색 키워드
DEFAULT_KEYWORDS = [
    "디지털헬스케어",
    "진단키트",
    "체외진단",
    "IVD",
    "식약처 의료기기",
    "FDA 승인",
    "AI 진단",
    "바이오마커",
    "분자진단",
    "헬스케어 투자",
]


def run_daily_job():
    """
    일일 작업 실행

    1. 뉴스 수집
    2. 중복 제거 및 AI 분석
    3. 리포트 생성
    4. 이메일 발송
    """
    logger.info("=" * 50)
    logger.info("HealthPulse 일일 작업 시작")
    logger.info("=" * 50)

    try:
        # 1. 뉴스 수집
        logger.info("[1/4] 뉴스 수집 시작...")
        articles = collect_news()
        logger.info(f"[1/4] 수집 완료: {len(articles)}건")

        if not articles:
            logger.warning("수집된 뉴스가 없습니다.")
            return

        # 2. AI 분석
        logger.info("[2/4] AI 분석 시작...")
        processed_count = process_articles()
        logger.info(f"[2/4] 분석 완료: {processed_count}건")

        # 3. 리포트 생성 및 발송
        logger.info("[3/4] 리포트 생성 및 발송 시작...")
        send_count = generate_and_send_reports()
        logger.info(f"[3/4] 발송 완료: {send_count}건")

        logger.info("=" * 50)
        logger.info("일일 작업 완료")
        logger.info("=" * 50)

    except Exception as e:
        logger.exception(f"일일 작업 중 오류 발생: {e}")


def collect_news() -> list:
    """뉴스 수집"""
    try:
        collector = NaverNewsCollector()
        deduplicator = ArticleDeduplicator()

        with get_session() as session:
            # 기존 해시 목록 조회
            existing_hashes = set(ArticleRepository.get_recent_hashes(session, days=7))

            all_articles = []
            new_count = 0

            for keyword in DEFAULT_KEYWORDS:
                logger.info(f"  키워드 검색: {keyword}")
                articles = collector.search(keyword, display=30)

                for article in articles:
                    # 중복 체크
                    if article.content_hash in existing_hashes:
                        continue

                    # 링크 중복 체크
                    if ArticleRepository.exists_by_link(session, article.link):
                        continue

                    # 새 기사 저장
                    db_article = ArticleRepository.create(session, article.to_dict())
                    all_articles.append(db_article)
                    existing_hashes.add(article.content_hash)
                    new_count += 1

            logger.info(f"  신규 기사 {new_count}건 저장 완료")
            return all_articles

    except ValueError as e:
        logger.error(f"뉴스 수집 실패: {e}")
        return []


def process_articles() -> int:
    """기사 AI 분석"""
    summarizer = OllamaSummarizer()
    classifier = ArticleClassifier()

    processed_count = 0

    with get_session() as session:
        # 미처리 기사 조회
        unprocessed = ArticleRepository.get_unprocessed(session, limit=100)

        for article in unprocessed:
            try:
                # 카테고리 분류
                category = classifier.classify(article.title, article.description or "")

                # 요약 생성
                summary = summarizer.summarize(article.title, article.description or "")

                # 중요도 점수
                importance = summarizer.score_importance(article.title, article.description or "")

                # 결과 저장
                ArticleRepository.update_analysis(
                    session,
                    article.id,
                    category,
                    summary,
                    importance
                )

                processed_count += 1
                logger.debug(f"  분석 완료: {article.title[:30]}... [{category.value}]")

            except Exception as e:
                logger.error(f"  기사 분석 실패: {e}")

    return processed_count


def generate_and_send_reports() -> int:
    """리포트 생성 및 발송"""
    generator = ReportGenerator()
    sender = GmailSender()

    if not sender.is_configured:
        logger.warning("이메일 설정이 완료되지 않아 발송을 건너뜁니다.")
        return 0

    sent_count = 0

    with get_session() as session:
        # 오늘 기사 조회
        articles = ArticleRepository.get_today_articles(session, processed_only=True)

        if not articles:
            logger.warning("발송할 기사가 없습니다.")
            return 0

        # 활성 수신자 조회
        recipients = RecipientRepository.get_all_active(session)

        if not recipients:
            logger.warning("등록된 수신자가 없습니다.")
            return 0

        # 리포트 생성
        report_date = datetime.now()
        subject = f"[HealthPulse] {report_date.strftime('%Y-%m-%d')} 일일 헬스케어 뉴스 브리핑"

        for recipient in recipients:
            try:
                # 이미 오늘 발송했는지 확인
                if SendHistoryRepository.already_sent_today(session, recipient.id):
                    logger.debug(f"  이미 발송됨: {recipient.email}")
                    continue

                # 리포트 HTML 생성
                html_content = generator.generate_daily_report(
                    articles=articles,
                    report_date=report_date,
                    recipient_name=recipient.name
                )

                # 이메일 발송
                result = sender.send(
                    recipient=recipient.email,
                    subject=subject,
                    html_content=html_content
                )

                # 발송 이력 저장
                SendHistoryRepository.create(
                    session,
                    recipient_id=recipient.id,
                    subject=subject,
                    article_count=len(articles),
                    report_date=report_date,
                    is_success=result.success,
                    error_message=result.error_message
                )

                if result.success:
                    sent_count += 1
                    logger.info(f"  발송 성공: {recipient.email}")
                else:
                    logger.error(f"  발송 실패: {recipient.email} - {result.error_message}")

            except Exception as e:
                logger.error(f"  리포트 발송 중 오류: {e}")

    return sent_count


def run_scheduler():
    """스케줄러 실행"""
    logger.info("HealthPulse 스케줄러 시작")

    scheduler = BlockingScheduler()

    # 매일 지정 시간에 실행
    trigger = CronTrigger(
        hour=settings.schedule_hour,
        minute=settings.schedule_minute
    )

    scheduler.add_job(
        run_daily_job,
        trigger=trigger,
        id="daily_job",
        name="Daily News Collection and Report",
    )

    logger.info(
        f"스케줄 설정: 매일 {settings.schedule_hour:02d}:{settings.schedule_minute:02d}에 실행"
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")
        scheduler.shutdown()


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="HealthPulse - 디지털 헬스케어 뉴스 모니터링")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="즉시 한 번 실행 (스케줄러 없이)"
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="뉴스 수집만 실행"
    )
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="AI 분석만 실행"
    )
    parser.add_argument(
        "--send-only",
        action="store_true",
        help="리포트 발송만 실행"
    )

    args = parser.parse_args()

    # 환경 변수 로드
    load_dotenv()

    # 로그 디렉토리 생성
    (settings.BASE_DIR / "logs").mkdir(exist_ok=True)

    # 데이터베이스 초기화
    logger.info("데이터베이스 초기화...")
    init_db(settings.database_url)

    if args.collect_only:
        logger.info("뉴스 수집만 실행")
        collect_news()
    elif args.process_only:
        logger.info("AI 분석만 실행")
        process_articles()
    elif args.send_only:
        logger.info("리포트 발송만 실행")
        generate_and_send_reports()
    elif args.run_once:
        logger.info("즉시 실행 모드")
        run_daily_job()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
