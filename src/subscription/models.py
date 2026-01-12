"""
구독자 데이터베이스 모델
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Subscriber(Base):
    """구독자 (이메일 인증 기반)"""
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, autoincrement=True)

    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(100))

    # 구독 키 및 인증
    subscription_key = Column(String(64), unique=True, nullable=False)  # 구독 인증 키
    is_verified = Column(Boolean, default=False)  # 이메일 인증 완료 여부
    verified_at = Column(DateTime)  # 인증 완료 시간

    # 검색 키워드 (JSON 문자열)
    keywords = Column(Text)  # ["수젠텍", "디지털헬스케어", ...]

    # 구독 상태
    is_active = Column(Boolean, default=True)
    unsubscribed_at = Column(DateTime)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sent_at = Column(DateTime)  # 마지막 발송 시간

    # 인덱스
    __table_args__ = (
        Index("idx_subscriber_email", "email"),
        Index("idx_subscriber_key", "subscription_key"),
        Index("idx_subscriber_verified", "is_verified"),
    )

    def __repr__(self):
        return f"<Subscriber(email='{self.email}', verified={self.is_verified})>"
