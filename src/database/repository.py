"""
데이터베이스 저장소 패턴 구현
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Article, Recipient, SendHistory, Category, CategoryType, RecipientGroup


# 데이터베이스 엔진 및 세션
_engine = None
_SessionLocal = None


def init_db(database_url: str = "sqlite:///./data/healthpulse.db") -> None:
    """데이터베이스 초기화"""
    global _engine, _SessionLocal

    # data 디렉토리 생성
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # 테이블 생성
    Base.metadata.create_all(bind=_engine)

    # 기본 카테고리 데이터 초기화
    _init_default_categories()


def _init_default_categories() -> None:
    """기본 카테고리 데이터 삽입"""
    with get_session() as session:
        existing = session.query(Category).count()
        if existing > 0:
            return

        default_categories = [
            Category(
                name=CategoryType.REGULATORY.value,
                keywords=json.dumps(["식약처", "FDA", "인허가", "규제", "승인", "허가", "의료기기법", "임상"], ensure_ascii=False),
                description="규제 및 정책 관련 뉴스",
                priority=1
            ),
            Category(
                name=CategoryType.MARKET.value,
                keywords=json.dumps(["시장", "투자", "M&A", "IPO", "인수", "합병", "펀딩", "상장"], ensure_ascii=False),
                description="시장 및 산업 동향",
                priority=2
            ),
            Category(
                name=CategoryType.TECHNOLOGY.value,
                keywords=json.dumps(["임상시험", "연구", "개발", "특허", "기술", "AI", "신기술", "바이오마커"], ensure_ascii=False),
                description="기술 및 R&D 관련 뉴스",
                priority=3
            ),
            Category(
                name=CategoryType.COMPETITOR.value,
                keywords=json.dumps(["씨젠", "SD바이오센서", "수젠텍", "래피젠", "휴마시스"], ensure_ascii=False),
                description="경쟁사 동향",
                priority=4
            ),
            Category(
                name=CategoryType.PRODUCT.value,
                keywords=json.dumps(["신제품", "출시", "런칭", "제품", "서비스", "솔루션"], ensure_ascii=False),
                description="제품 및 서비스 소식",
                priority=5
            ),
            Category(
                name=CategoryType.GENERAL.value,
                keywords=json.dumps([], ensure_ascii=False),
                description="기타 일반 뉴스",
                priority=99
            ),
        ]

        for cat in default_categories:
            session.add(cat)
        session.commit()


@contextmanager
def get_session():
    """세션 컨텍스트 매니저"""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class ArticleRepository:
    """기사 저장소"""

    @staticmethod
    def create(session: Session, article_data: dict) -> Article:
        """기사 생성"""
        # 컨텐츠 해시 생성
        hash_content = f"{article_data.get('title', '')}{article_data.get('description', '')}"
        content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

        article = Article(
            title=article_data.get("title"),
            description=article_data.get("description"),
            link=article_data.get("link"),
            original_link=article_data.get("original_link"),
            pub_date=article_data.get("pub_date"),
            source=article_data.get("source"),
            keyword=article_data.get("keyword"),
            content_hash=content_hash,
        )

        session.add(article)
        session.flush()
        return article

    @staticmethod
    def get_by_link(session: Session, link: str) -> Optional[Article]:
        """링크로 기사 조회"""
        return session.query(Article).filter(Article.link == link).first()

    @staticmethod
    def get_by_hash(session: Session, content_hash: str) -> Optional[Article]:
        """해시로 기사 조회"""
        return session.query(Article).filter(Article.content_hash == content_hash).first()

    @staticmethod
    def exists_by_link(session: Session, link: str) -> bool:
        """링크 존재 여부 확인"""
        return session.query(Article).filter(Article.link == link).count() > 0

    @staticmethod
    def get_unprocessed(session: Session, limit: int = 100) -> list[Article]:
        """미처리 기사 조회"""
        return (
            session.query(Article)
            .filter(
                and_(
                    Article.is_processed == False,
                    Article.is_duplicate == False
                )
            )
            .order_by(Article.collected_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_today_articles(session: Session, processed_only: bool = True) -> list[Article]:
        """오늘 수집된 기사 조회"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        query = session.query(Article).filter(
            and_(
                Article.collected_at >= today_start,
                Article.is_duplicate == False
            )
        )

        if processed_only:
            query = query.filter(Article.is_processed == True)

        return query.order_by(Article.importance_score.desc()).all()

    @staticmethod
    def get_articles_by_date(
        session: Session,
        target_date: datetime,
        processed_only: bool = True
    ) -> list[Article]:
        """특정 날짜의 기사 조회"""
        date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        query = session.query(Article).filter(
            and_(
                Article.collected_at >= date_start,
                Article.collected_at < date_end,
                Article.is_duplicate == False
            )
        )

        if processed_only:
            query = query.filter(Article.is_processed == True)

        return query.order_by(Article.importance_score.desc()).all()

    @staticmethod
    def get_recent_hashes(session: Session, days: int = 7) -> list[str]:
        """최근 N일간 기사의 해시 목록"""
        since = datetime.utcnow() - timedelta(days=days)
        results = (
            session.query(Article.content_hash)
            .filter(Article.collected_at >= since)
            .all()
        )
        return [r[0] for r in results if r[0]]

    @staticmethod
    def update_analysis(
        session: Session,
        article_id: int,
        category: CategoryType,
        summary: str,
        importance_score: float
    ) -> None:
        """AI 분석 결과 업데이트"""
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.category = category
            article.summary = summary
            article.importance_score = importance_score
            article.is_processed = True
            article.processed_at = datetime.utcnow()

    @staticmethod
    def mark_as_duplicate(session: Session, article_id: int) -> None:
        """중복 기사로 마킹"""
        article = session.query(Article).filter(Article.id == article_id).first()
        if article:
            article.is_duplicate = True

    @staticmethod
    def mark_as_sent(session: Session, article_ids: list[int]) -> None:
        """발송 완료로 마킹"""
        session.query(Article).filter(Article.id.in_(article_ids)).update(
            {"is_sent": True},
            synchronize_session=False
        )


class RecipientRepository:
    """수신자 저장소"""

    @staticmethod
    def create(session: Session, email: str, name: str, group: RecipientGroup) -> Recipient:
        """수신자 생성"""
        recipient = Recipient(email=email, name=name, group=group)
        session.add(recipient)
        session.flush()
        return recipient

    @staticmethod
    def get_by_email(session: Session, email: str) -> Optional[Recipient]:
        """이메일로 수신자 조회"""
        return session.query(Recipient).filter(Recipient.email == email).first()

    @staticmethod
    def get_active_by_group(session: Session, group: RecipientGroup) -> list[Recipient]:
        """그룹별 활성 수신자 조회"""
        if group == RecipientGroup.ALL:
            return session.query(Recipient).filter(Recipient.is_active == True).all()
        return (
            session.query(Recipient)
            .filter(and_(Recipient.group == group, Recipient.is_active == True))
            .all()
        )

    @staticmethod
    def get_all_active(session: Session) -> list[Recipient]:
        """모든 활성 수신자 조회"""
        return session.query(Recipient).filter(Recipient.is_active == True).all()


class SendHistoryRepository:
    """발송 이력 저장소"""

    @staticmethod
    def create(
        session: Session,
        recipient_id: int,
        subject: str,
        article_count: int,
        report_date: datetime,
        is_success: bool,
        error_message: str = None
    ) -> SendHistory:
        """발송 이력 생성"""
        history = SendHistory(
            recipient_id=recipient_id,
            subject=subject,
            article_count=article_count,
            report_date=report_date,
            is_success=is_success,
            error_message=error_message
        )
        session.add(history)
        session.flush()
        return history

    @staticmethod
    def get_by_date(session: Session, report_date: datetime) -> list[SendHistory]:
        """날짜별 발송 이력 조회"""
        date_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        return (
            session.query(SendHistory)
            .filter(
                and_(
                    SendHistory.report_date >= date_start,
                    SendHistory.report_date < date_end
                )
            )
            .all()
        )

    @staticmethod
    def already_sent_today(session: Session, recipient_id: int) -> bool:
        """오늘 이미 발송했는지 확인"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        return (
            session.query(SendHistory)
            .filter(
                and_(
                    SendHistory.recipient_id == recipient_id,
                    SendHistory.sent_at >= today_start,
                    SendHistory.is_success == True
                )
            )
            .count() > 0
        )
