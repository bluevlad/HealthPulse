"""
네이버 뉴스 검색 API 클라이언트
"""

import logging
import re
import hashlib
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """뉴스 기사 데이터 클래스"""
    title: str
    description: str
    link: str
    original_link: str
    pub_date: Optional[datetime]
    source: Optional[str] = None
    keyword: str = ""
    content_hash: str = field(default="", init=False)

    def __post_init__(self):
        # HTML 태그 제거
        self.title = self._clean_html(self.title)
        self.description = self._clean_html(self.description)

        # 컨텐츠 해시 생성
        hash_content = f"{self.title}{self.description}"
        self.content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

    @staticmethod
    def _clean_html(text: str) -> str:
        """HTML 태그 및 특수문자 제거"""
        if not text:
            return ""
        # HTML 태그 제거
        clean = re.sub(r'<[^>]+>', '', text)
        # HTML 엔티티 변환
        clean = clean.replace("&quot;", '"')
        clean = clean.replace("&amp;", "&")
        clean = clean.replace("&lt;", "<")
        clean = clean.replace("&gt;", ">")
        clean = clean.replace("&apos;", "'")
        return clean.strip()

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            "title": self.title,
            "description": self.description,
            "link": self.link,
            "original_link": self.original_link,
            "pub_date": self.pub_date,
            "source": self.source,
            "keyword": self.keyword,
            "content_hash": self.content_hash,
        }


class NaverNewsCollector:
    """네이버 뉴스 검색 API 클라이언트"""

    BASE_URL = "https://openapi.naver.com/v1/search/news.json"

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None
    ):
        self.client_id = client_id or settings.naver_client_id
        self.client_secret = client_secret or settings.naver_client_secret

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "네이버 API 인증 정보가 필요합니다. "
                ".env 파일에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정하세요."
            )

        self._client = httpx.Client(
            headers={
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            },
            timeout=30.0
        )

    def search(
        self,
        query: str,
        display: int = 100,
        start: int = 1,
        sort: str = "date"
    ) -> list[NewsArticle]:
        """
        네이버 뉴스 검색

        Args:
            query: 검색어
            display: 검색 결과 수 (최대 100)
            start: 검색 시작 위치 (최대 1000)
            sort: 정렬 방식 (date: 날짜순, sim: 정확도순)

        Returns:
            NewsArticle 리스트
        """
        params = {
            "query": query,
            "display": min(display, 100),
            "start": start,
            "sort": sort,
        }

        try:
            response = self._client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get("items", []):
                article = self._parse_item(item, query)
                if article:
                    articles.append(article)

            logger.info(f"[{query}] {len(articles)}개 기사 수집 완료")
            return articles

        except httpx.HTTPStatusError as e:
            logger.error(f"API 요청 실패: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"뉴스 검색 중 오류 발생: {e}")
            return []

    def _parse_item(self, item: dict, keyword: str) -> Optional[NewsArticle]:
        """API 응답 아이템 파싱"""
        try:
            # 발행일 파싱
            pub_date = None
            if item.get("pubDate"):
                try:
                    # RFC 2822 형식: "Mon, 06 Jan 2025 09:00:00 +0900"
                    pub_date = datetime.strptime(
                        item["pubDate"],
                        "%a, %d %b %Y %H:%M:%S %z"
                    )
                except ValueError:
                    logger.debug(f"날짜 파싱 실패: {item.get('pubDate')}")

            # 언론사 추출 (링크에서)
            source = self._extract_source(item.get("originallink", ""))

            return NewsArticle(
                title=item.get("title", ""),
                description=item.get("description", ""),
                link=item.get("link", ""),
                original_link=item.get("originallink", ""),
                pub_date=pub_date,
                source=source,
                keyword=keyword,
            )
        except Exception as e:
            logger.error(f"아이템 파싱 실패: {e}")
            return None

    def _extract_source(self, url: str) -> str:
        """URL에서 언론사 추출"""
        if not url:
            return ""

        # 도메인 추출
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc

            # 주요 언론사 매핑
            source_map = {
                "chosun.com": "조선일보",
                "donga.com": "동아일보",
                "joongang.co.kr": "중앙일보",
                "hani.co.kr": "한겨레",
                "khan.co.kr": "경향신문",
                "mk.co.kr": "매일경제",
                "hankyung.com": "한국경제",
                "sedaily.com": "서울경제",
                "etnews.com": "전자신문",
                "newsis.com": "뉴시스",
                "yna.co.kr": "연합뉴스",
                "yonhapnews.co.kr": "연합뉴스",
                "news1.kr": "뉴스1",
                "mt.co.kr": "머니투데이",
                "edaily.co.kr": "이데일리",
                "biz.chosun.com": "조선비즈",
                "zdnet.co.kr": "지디넷코리아",
                "biospectator.com": "바이오스펙테이터",
                "bosa.co.kr": "약사공론",
                "dailypharm.com": "데일리팜",
                "yakup.com": "약업신문",
                "medipana.com": "메디파나뉴스",
                "medifonews.com": "메디포뉴스",
            }

            for key, value in source_map.items():
                if key in domain:
                    return value

            return domain
        except Exception:
            return ""

    def collect_by_keywords(
        self,
        keywords: list[str],
        display_per_keyword: int = 50
    ) -> list[NewsArticle]:
        """
        여러 키워드로 뉴스 수집

        Args:
            keywords: 검색 키워드 리스트
            display_per_keyword: 키워드당 수집 건수

        Returns:
            중복 제거된 NewsArticle 리스트
        """
        all_articles = []
        seen_hashes = set()

        for keyword in keywords:
            articles = self.search(keyword, display=display_per_keyword)

            for article in articles:
                # 중복 체크
                if article.content_hash not in seen_hashes:
                    seen_hashes.add(article.content_hash)
                    all_articles.append(article)

        logger.info(f"총 {len(all_articles)}개 고유 기사 수집 (키워드 {len(keywords)}개)")
        return all_articles

    def close(self):
        """HTTP 클라이언트 종료"""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 기본 검색 키워드 (헬스케어/진단키트 관련)
DEFAULT_KEYWORDS = [
    # 핵심 키워드
    "디지털헬스케어",
    "진단키트",
    "체외진단",
    "IVD",

    # 규제/정책
    "식약처 의료기기",
    "FDA 승인 진단",

    # 기술/R&D
    "AI 진단",
    "바이오마커",
    "액체생검",
    "분자진단",

    # 시장/산업
    "헬스케어 투자",
    "의료기기 시장",
]


if __name__ == "__main__":
    # 테스트 실행
    import os
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    try:
        with NaverNewsCollector() as collector:
            # 단일 키워드 검색 테스트
            articles = collector.search("디지털헬스케어", display=5)

            print(f"\n=== 검색 결과: {len(articles)}건 ===\n")
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article.title}")
                print(f"   - 출처: {article.source}")
                print(f"   - 날짜: {article.pub_date}")
                print(f"   - 링크: {article.link}")
                print()

    except ValueError as e:
        print(f"오류: {e}")
