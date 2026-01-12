"""
SQLAlchemy 데이터베이스 모델 정의
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CategoryType(PyEnum):
    """기사 카테고리 유형"""
    REGULATORY = "규제/정책"       # 식약처, FDA, 인허가
    MARKET = "시장/산업"           # 시장규모, 투자, M&A
    TECHNOLOGY = "기술/R&D"        # 임상시험, 신기술, 특허
    COMPETITOR = "경쟁사"          # 경쟁사 동향
    PRODUCT = "제품/서비스"        # 신제품, 출시 소식
    GENERAL = "일반"               # 기타


class RecipientGroup(PyEnum):
    """수신자 그룹"""
    EXECUTIVE = "경영진"
    RND = "연구개발"
    MARKETING = "마케팅"
    SALES = "영업"
    ALL = "전체"


class Article(Base):
    """수집된 뉴스 기사"""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 기본 정보
    title = Column(String(500), nullable=False)
    description = Column(Text)  # 원문 설명
    content = Column(Text)      # 추출된 본문 (선택적)
    link = Column(String(1000), unique=True, nullable=False)
    original_link = Column(String(1000))  # 네이버 외부 원본 링크

    # 메타데이터
    pub_date = Column(DateTime)  # 기사 발행일
    source = Column(String(100))  # 언론사
    keyword = Column(String(100))  # 검색에 사용된 키워드

    # AI 분석 결과
    category = Column(Enum(CategoryType), default=CategoryType.GENERAL)
    summary = Column(Text)  # AI 생성 요약
    importance_score = Column(Float, default=0.0)  # 중요도 점수 (0.0 ~ 1.0)

    # 중복 탐지용
    content_hash = Column(String(64))  # 제목+설명 해시
    embedding_vector = Column(Text)    # 임베딩 벡터 (JSON 문자열)
    is_duplicate = Column(Boolean, default=False)

    # 처리 상태
    is_processed = Column(Boolean, default=False)  # AI 분석 완료 여부
    is_sent = Column(Boolean, default=False)       # 이메일 발송 여부

    # 타임스탬프
    collected_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    # 인덱스
    __table_args__ = (
        Index("idx_article_pub_date", "pub_date"),
        Index("idx_article_category", "category"),
        Index("idx_article_keyword", "keyword"),
        Index("idx_article_collected", "collected_at"),
        Index("idx_article_content_hash", "content_hash"),
    )

    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:30]}...')>"


class Recipient(Base):
    """이메일 수신자"""
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, autoincrement=True)

    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(100))
    group = Column(Enum(RecipientGroup), default=RecipientGroup.ALL)

    # 선호 카테고리 (JSON 문자열)
    preferred_categories = Column(Text)  # ["규제/정책", "기술/R&D"]

    # 관심 키워드 (JSON 문자열)
    keywords = Column(Text)  # ["디지털헬스케어", "의료AI"]

    # 구독 해지 토큰
    unsubscribe_token = Column(String(64), unique=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    send_histories = relationship("SendHistory", back_populates="recipient")

    def __repr__(self):
        return f"<Recipient(email='{self.email}', group='{self.group.value}')>"


class SendHistory(Base):
    """이메일 발송 이력"""
    __tablename__ = "send_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=False)

    # 발송 정보
    subject = Column(String(500))
    article_count = Column(Integer, default=0)
    report_date = Column(DateTime)  # 리포트 대상 날짜

    # 상태
    is_success = Column(Boolean, default=False)
    error_message = Column(Text)

    sent_at = Column(DateTime, default=datetime.utcnow)

    # 관계
    recipient = relationship("Recipient", back_populates="send_histories")

    # 인덱스
    __table_args__ = (
        Index("idx_send_history_date", "report_date"),
        Index("idx_send_history_recipient", "recipient_id"),
    )

    def __repr__(self):
        return f"<SendHistory(recipient_id={self.recipient_id}, sent_at='{self.sent_at}')>"


class EmailVerification(Base):
    """이메일 인증 코드"""
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)

    email = Column(String(255), nullable=False)
    name = Column(String(100))
    code = Column(String(6), nullable=False)  # 6자리 인증 코드

    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)  # 시도 횟수

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # 만료 시간

    # 인덱스
    __table_args__ = (
        Index("idx_verification_email", "email"),
        Index("idx_verification_code", "code"),
    )

    def __repr__(self):
        return f"<EmailVerification(email='{self.email}', verified={self.is_verified})>"


class Category(Base):
    """카테고리 분류 규칙"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(50), unique=True, nullable=False)  # CategoryType 값
    keywords = Column(Text)  # 분류 키워드 목록 (JSON)
    description = Column(String(200))
    priority = Column(Integer, default=0)  # 분류 우선순위

    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Category(name='{self.name}')>"
