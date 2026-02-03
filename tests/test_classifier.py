"""
카테고리 분류기 테스트
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.classifier import ArticleClassifier, CATEGORY_KEYWORDS
from src.database.models import CategoryType


class TestArticleClassifier:
    """ArticleClassifier 테스트"""

    @pytest.fixture
    def classifier(self):
        """분류기 인스턴스 (Ollama 없이)"""
        return ArticleClassifier(use_ollama=False)

    def test_classify_regulatory(self, classifier):
        """규제/정책 분류 테스트"""
        title = "식약처, 코로나19 자가진단키트 긴급사용 승인"
        content = "식품의약품안전처가 새로운 코로나19 자가진단키트에 대한 긴급사용을 승인했다."

        result = classifier.classify(title, content)
        assert result == CategoryType.REGULATORY

    def test_classify_market(self, classifier):
        """시장/산업 분류 테스트"""
        title = "헬스케어 스타트업, 100억 원 시리즈A 투자 유치"
        content = "AI 기반 헬스케어 스타트업이 100억 원 규모의 시리즈A 투자를 유치했다."

        result = classifier.classify(title, content)
        assert result == CategoryType.MARKET

    def test_classify_technology(self, classifier):
        """기술/R&D 분류 테스트"""
        title = "새로운 바이오마커 발견... 조기진단 정확도 90% 달성"
        content = "연구팀이 암 조기진단을 위한 새로운 바이오마커를 발견했다."

        result = classifier.classify(title, content)
        assert result == CategoryType.TECHNOLOGY

    def test_classify_competitor(self, classifier):
        """경쟁사 분류 테스트"""
        title = "씨젠, 분자진단 신제품 출시... 글로벌 시장 공략"
        content = "씨젠이 새로운 분자진단 제품을 출시하며 글로벌 시장 확대에 나선다."

        result = classifier.classify(title, content)
        assert result == CategoryType.COMPETITOR

    def test_classify_product(self, classifier):
        """제품/서비스 분류 테스트"""
        title = "헬스케어 플랫폼 신제품 런칭, 웨어러블 연동 기능 추가"
        content = "새로운 헬스케어 플랫폼이 출시되며 웨어러블 기기와의 연동 기능이 추가되었다."

        result = classifier.classify(title, content)
        assert result == CategoryType.PRODUCT

    def test_classify_general(self, classifier):
        """일반 분류 테스트 (매칭 키워드 없음)"""
        title = "오늘의 날씨"
        content = "맑음"

        result = classifier.classify(title, content)
        assert result == CategoryType.GENERAL

    def test_classify_batch(self, classifier):
        """일괄 분류 테스트"""
        articles = [
            {"title": "FDA 승인 획득", "content": "의료기기 FDA 승인"},
            {"title": "100억 투자 유치", "content": "시리즈A 펀딩 완료"},
        ]

        results = classifier.classify_batch(articles)

        assert len(results) == 2
        assert results[0] == CategoryType.REGULATORY
        assert results[1] == CategoryType.MARKET


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
