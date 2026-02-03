"""
구독 관리자 - 구독 신청, 인증, 발송 관리
"""

import json
import secrets
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Subscriber

logger = logging.getLogger(__name__)

# 데이터베이스 설정
_engine = None
_SessionLocal = None


def init_subscription_db(database_url: str = None) -> None:
    """구독 데이터베이스 초기화"""
    global _engine, _SessionLocal

    if database_url is None:
        # 기본 경로
        db_path = Path(__file__).parent.parent.parent / "data" / "subscriptions.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{db_path}"

    _engine = create_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # 테이블 생성
    Base.metadata.create_all(bind=_engine)
    logger.info(f"구독 데이터베이스 초기화 완료: {database_url}")


@contextmanager
def get_session():
    """세션 컨텍스트 매니저"""
    if _SessionLocal is None:
        init_subscription_db()

    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class SubscriptionManager:
    """구독 관리 클래스"""

    def __init__(self):
        # DB 초기화 확인
        if _SessionLocal is None:
            init_subscription_db()

    @staticmethod
    def generate_subscription_key() -> str:
        """구독 키 생성 (16자 영숫자)"""
        return secrets.token_hex(8).upper()  # 16자 대문자

    def subscribe(
        self,
        email: str,
        keywords: list[str],
        name: str = None
    ) -> tuple[Subscriber, str]:
        """
        구독 신청

        Args:
            email: 이메일 주소
            keywords: 검색 키워드 목록
            name: 구독자 이름 (선택)

        Returns:
            (Subscriber 객체, 구독 키)
        """
        subscription_key = self.generate_subscription_key()

        with get_session() as session:
            # 이미 존재하는지 확인
            existing = session.query(Subscriber).filter(
                Subscriber.email == email
            ).first()

            if existing:
                # 기존 구독자 업데이트
                existing.subscription_key = subscription_key
                existing.keywords = json.dumps(keywords, ensure_ascii=False)
                existing.is_verified = False
                existing.is_active = True
                existing.updated_at = datetime.utcnow()
                if name:
                    existing.name = name
                subscriber = existing
                logger.info(f"구독 정보 업데이트: {email}")
            else:
                # 새 구독자 생성
                subscriber = Subscriber(
                    email=email,
                    name=name,
                    subscription_key=subscription_key,
                    keywords=json.dumps(keywords, ensure_ascii=False),
                    is_verified=False,
                    is_active=True,
                )
                session.add(subscriber)
                logger.info(f"새 구독자 등록: {email}")

            session.flush()

            return subscriber, subscription_key

    def verify(self, email: str, subscription_key: str) -> bool:
        """
        구독 인증

        Args:
            email: 이메일 주소
            subscription_key: 구독 키

        Returns:
            인증 성공 여부
        """
        with get_session() as session:
            subscriber = session.query(Subscriber).filter(
                Subscriber.email == email,
                Subscriber.subscription_key == subscription_key
            ).first()

            if subscriber:
                subscriber.is_verified = True
                subscriber.verified_at = datetime.utcnow()
                logger.info(f"구독 인증 완료: {email}")
                return True

            logger.warning(f"구독 인증 실패: {email}")
            return False

    def get_verified_subscribers(self) -> list[Subscriber]:
        """인증된 활성 구독자 목록 조회"""
        with get_session() as session:
            subscribers = session.query(Subscriber).filter(
                Subscriber.is_verified == True,
                Subscriber.is_active == True
            ).all()

            # 세션 분리를 위해 필요한 속성 접근
            for s in subscribers:
                _ = s.email, s.keywords, s.name

            return subscribers

    def get_subscriber_by_email(self, email: str) -> Optional[Subscriber]:
        """이메일로 구독자 조회"""
        with get_session() as session:
            subscriber = session.query(Subscriber).filter(
                Subscriber.email == email
            ).first()

            if subscriber:
                # 세션 분리를 위해 필요한 속성 접근
                _ = subscriber.email, subscriber.keywords, subscriber.name, subscriber.is_verified

            return subscriber

    def update_last_sent(self, email: str) -> None:
        """마지막 발송 시간 업데이트"""
        with get_session() as session:
            subscriber = session.query(Subscriber).filter(
                Subscriber.email == email
            ).first()

            if subscriber:
                subscriber.last_sent_at = datetime.utcnow()

    def unsubscribe(self, email: str) -> bool:
        """구독 해지"""
        with get_session() as session:
            subscriber = session.query(Subscriber).filter(
                Subscriber.email == email
            ).first()

            if subscriber:
                subscriber.is_active = False
                subscriber.unsubscribed_at = datetime.utcnow()
                logger.info(f"구독 해지: {email}")
                return True

            return False

    def get_keywords(self, email: str) -> list[str]:
        """구독자의 키워드 목록 조회"""
        with get_session() as session:
            subscriber = session.query(Subscriber).filter(
                Subscriber.email == email
            ).first()

            if subscriber and subscriber.keywords:
                return json.loads(subscriber.keywords)

            return []
