"""
중복 탐지 모듈 테스트
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processor.deduplicator import ArticleDeduplicator


class TestArticleDeduplicator:
    """ArticleDeduplicator 테스트"""

    @pytest.fixture
    def deduplicator(self):
        """중복 탐지기 인스턴스"""
        return ArticleDeduplicator(similarity_threshold=0.85)

    def test_compute_hash(self, deduplicator):
        """해시 계산 테스트"""
        hash1 = deduplicator.compute_hash("테스트 제목", "테스트 내용")
        hash2 = deduplicator.compute_hash("테스트 제목", "테스트 내용")
        hash3 = deduplicator.compute_hash("다른 제목", "다른 내용")

        assert hash1 == hash2  # 동일 입력 → 동일 해시
        assert hash1 != hash3  # 다른 입력 → 다른 해시

    def test_exact_duplicate(self, deduplicator):
        """정확한 중복 탐지 테스트"""
        title = "식약처, 코로나19 자가진단키트 긴급사용 승인"
        content = "식품의약품안전처가 새로운 자가진단키트를 승인했다."

        # 첫 번째 기사 등록
        hash1 = deduplicator.compute_hash(title, content)
        existing_hashes = {hash1}

        # 동일한 기사 중복 체크
        result = deduplicator.check_duplicate(title, content, list(existing_hashes), {})

        assert result.is_duplicate == True
        assert result.similarity_score == 1.0

    def test_not_duplicate(self, deduplicator):
        """비중복 테스트"""
        title1 = "식약처, 코로나19 자가진단키트 긴급사용 승인"
        content1 = "식품의약품안전처가 새로운 자가진단키트를 승인했다."

        title2 = "헬스케어 스타트업 100억 투자 유치"
        content2 = "AI 헬스케어 기업이 대규모 투자를 유치했다."

        hash1 = deduplicator.compute_hash(title1, content1)
        existing_hashes = {hash1}

        result = deduplicator.check_duplicate(title2, content2, list(existing_hashes), {})

        assert result.is_duplicate == False

    def test_check_duplicate_simple(self, deduplicator):
        """간단한 해시 기반 중복 체크 테스트"""
        title = "테스트 기사"
        content = "테스트 내용"

        hash_val = deduplicator.compute_hash(title, content)
        existing_hashes = {hash_val}

        # 중복
        assert deduplicator.check_duplicate_simple(title, content, existing_hashes) == True

        # 비중복
        assert deduplicator.check_duplicate_simple("다른 기사", "다른 내용", existing_hashes) == False

    def test_clear_cache(self, deduplicator):
        """캐시 초기화 테스트"""
        # 캐시에 데이터 추가
        deduplicator._hash_cache.add("test_hash")

        assert len(deduplicator._hash_cache) > 0

        # 캐시 초기화
        deduplicator.clear_cache()

        assert len(deduplicator._hash_cache) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
