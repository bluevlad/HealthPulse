"""
기사 카테고리 분류 모듈
"""

import json
import logging
from typing import Optional

import ollama
from ollama import ResponseError

from ..config import settings
from ..database.models import CategoryType

logger = logging.getLogger(__name__)


# 카테고리별 키워드 매핑
CATEGORY_KEYWORDS = {
    CategoryType.REGULATORY: [
        "식약처", "FDA", "인허가", "규제", "승인", "허가", "의료기기법",
        "임상시험 승인", "품목허가", "GMP", "인증", "CE마크", "MFDS",
        "규제 샌드박스", "의료기기 심사", "허가 심사"
    ],
    CategoryType.MARKET: [
        "시장", "투자", "M&A", "IPO", "인수", "합병", "펀딩", "상장",
        "시장규모", "매출", "성장률", "투자유치", "기업가치", "시가총액",
        "분기실적", "매각", "스타트업"
    ],
    CategoryType.TECHNOLOGY: [
        "임상시험", "연구", "개발", "특허", "기술", "AI", "신기술",
        "바이오마커", "유전자", "진단기술", "알고리즘", "정확도",
        "민감도", "특이도", "R&D", "연구개발", "논문", "학회"
    ],
    CategoryType.COMPETITOR: [
        # 주요 진단키트/헬스케어 기업
        "씨젠", "SD바이오센서", "수젠텍", "래피젠", "휴마시스",
        "녹십자MS", "바디텍메드", "피씨엘", "젠큐릭스", "마크로젠",
        "로슈", "애보트", "지멘스", "다나허", "써모피셔"
    ],
    CategoryType.PRODUCT: [
        "신제품", "출시", "런칭", "제품", "서비스", "솔루션",
        "키트", "플랫폼", "시스템", "장비", "기기", "웨어러블",
        "앱", "어플리케이션", "소프트웨어"
    ],
}


class ArticleClassifier:
    """기사 카테고리 분류기"""

    CLASSIFY_PROMPT = """다음 뉴스 기사를 아래 카테고리 중 하나로 분류해주세요.

카테고리:
1. 규제/정책 - 식약처, FDA, 인허가, 승인, 규제 관련
2. 시장/산업 - 투자, M&A, IPO, 시장규모, 매출 관련
3. 기술/R&D - 연구, 임상시험, 특허, 신기술 관련
4. 경쟁사 - 경쟁 기업 동향 관련
5. 제품/서비스 - 신제품 출시, 서비스 런칭 관련
6. 일반 - 위 카테고리에 해당하지 않는 경우

제목: {title}
내용: {content}

카테고리 번호만 응답해주세요 (1-6):"""

    CATEGORY_MAP = {
        "1": CategoryType.REGULATORY,
        "2": CategoryType.MARKET,
        "3": CategoryType.TECHNOLOGY,
        "4": CategoryType.COMPETITOR,
        "5": CategoryType.PRODUCT,
        "6": CategoryType.GENERAL,
    }

    def __init__(
        self,
        model: str = None,
        host: str = None,
        use_ollama: bool = True
    ):
        self.model = model or settings.ollama_model
        self.host = host or settings.ollama_host
        self.use_ollama = use_ollama

        self._client = None
        self._available = False

        if use_ollama:
            try:
                self._client = ollama.Client(host=self.host)
                self._available = self._check_availability()
            except Exception as e:
                logger.warning(f"Ollama 클라이언트 초기화 실패: {e}")

    def _check_availability(self) -> bool:
        """Ollama 서버 사용 가능 여부 확인"""
        try:
            models = self._client.list()
            return len(models.get('models', [])) > 0
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """Ollama 사용 가능 여부"""
        return self._available

    def classify(self, title: str, content: str) -> CategoryType:
        """
        기사 카테고리 분류

        Args:
            title: 기사 제목
            content: 기사 본문 또는 설명

        Returns:
            CategoryType 열거형 값
        """
        # Ollama 사용 가능하면 AI 분류 시도
        if self._available and self.use_ollama:
            category = self._classify_with_ollama(title, content)
            if category:
                return category

        # 키워드 기반 폴백
        return self._classify_by_keywords(title, content)

    def _classify_with_ollama(self, title: str, content: str) -> Optional[CategoryType]:
        """Ollama를 사용한 AI 분류"""
        prompt = self.CLASSIFY_PROMPT.format(title=title, content=content)

        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.1,
                    "num_predict": 5,
                }
            )
            result = response.get("response", "").strip()

            # 숫자 추출
            import re
            match = re.search(r'[1-6]', result)
            if match:
                return self.CATEGORY_MAP.get(match.group(), CategoryType.GENERAL)

        except Exception as e:
            logger.error(f"Ollama 분류 실패: {e}")

        return None

    def _classify_by_keywords(self, title: str, content: str) -> CategoryType:
        """키워드 기반 분류"""
        text = f"{title} {content}".lower()

        # 카테고리별 키워드 매칭 점수
        scores = {category: 0 for category in CategoryType}

        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    scores[category] += 1

        # 최고 점수 카테고리 반환
        max_category = max(scores, key=scores.get)

        # 매칭된 키워드가 없으면 일반 카테고리
        if scores[max_category] == 0:
            return CategoryType.GENERAL

        return max_category

    def classify_batch(self, articles: list[dict]) -> list[CategoryType]:
        """
        여러 기사 일괄 분류

        Args:
            articles: [{"title": "...", "content": "..."}, ...] 형태

        Returns:
            CategoryType 리스트
        """
        results = []
        for article in articles:
            category = self.classify(
                article.get("title", ""),
                article.get("content", article.get("description", ""))
            )
            results.append(category)
        return results


# 편의 함수
_classifier: Optional[ArticleClassifier] = None


def get_classifier() -> ArticleClassifier:
    """싱글톤 분류기 반환"""
    global _classifier
    if _classifier is None:
        _classifier = ArticleClassifier()
    return _classifier


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)

    classifier = ArticleClassifier()

    print(f"Ollama 사용 가능: {classifier.is_available}")

    # 테스트 기사들
    test_cases = [
        {
            "title": "식약처, 코로나19 자가진단키트 긴급사용 승인",
            "content": "식품의약품안전처가 새로운 코로나19 자가진단키트에 대한 긴급사용을 승인했다.",
            "expected": "규제/정책"
        },
        {
            "title": "씨젠, 분자진단 신제품 출시... 글로벌 시장 공략",
            "content": "씨젠이 새로운 분자진단 제품을 출시하며 글로벌 시장 확대에 나선다.",
            "expected": "경쟁사"
        },
        {
            "title": "헬스케어 스타트업, 100억 원 시리즈A 투자 유치",
            "content": "AI 기반 헬스케어 스타트업이 100억 원 규모의 시리즈A 투자를 유치했다.",
            "expected": "시장/산업"
        },
        {
            "title": "새로운 바이오마커 발견... 조기진단 정확도 90% 달성",
            "content": "연구팀이 암 조기진단을 위한 새로운 바이오마커를 발견했다.",
            "expected": "기술/R&D"
        },
    ]

    print("\n=== 분류 테스트 ===\n")
    for test in test_cases:
        result = classifier.classify(test["title"], test["content"])
        status = "✓" if result.value == test["expected"] else "✗"
        print(f"{status} {test['title'][:30]}...")
        print(f"   예상: {test['expected']} | 결과: {result.value}")
        print()
