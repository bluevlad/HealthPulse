"""
기사 중복 탐지 모듈

Sentence-BERT를 사용한 의미적 유사도 기반 중복 탐지
"""

import json
import logging
import hashlib
from typing import Optional
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# Sentence-BERT 모델 (lazy loading)
_model = None
_model_loaded = False


def _get_model():
    """Sentence-BERT 모델 로드 (lazy loading)"""
    global _model, _model_loaded

    if _model_loaded:
        return _model

    try:
        from sentence_transformers import SentenceTransformer

        # 한국어 최적화 모델
        _model = SentenceTransformer('jhgan/ko-sroberta-multitask')
        logger.info("Sentence-BERT 모델 로드 완료: jhgan/ko-sroberta-multitask")
        _model_loaded = True
        return _model

    except ImportError:
        logger.warning(
            "sentence-transformers가 설치되지 않았습니다. "
            "pip install sentence-transformers 로 설치하세요."
        )
        _model_loaded = True
        return None

    except Exception as e:
        logger.error(f"Sentence-BERT 모델 로드 실패: {e}")
        _model_loaded = True
        return None


@dataclass
class DuplicateResult:
    """중복 탐지 결과"""
    is_duplicate: bool
    similarity_score: float
    matched_hash: Optional[str] = None
    matched_title: Optional[str] = None


class ArticleDeduplicator:
    """기사 중복 탐지기"""

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        hash_threshold: float = 1.0
    ):
        """
        Args:
            similarity_threshold: 의미적 유사도 임계값 (0.0 ~ 1.0)
            hash_threshold: 해시 일치 임계값 (1.0이면 정확히 일치)
        """
        self.similarity_threshold = similarity_threshold
        self.hash_threshold = hash_threshold
        self._model = _get_model()

        # 메모리 캐시 (세션 내 중복 체크용)
        self._hash_cache: set[str] = set()
        self._embedding_cache: dict[str, np.ndarray] = {}

    @property
    def is_available(self) -> bool:
        """Sentence-BERT 모델 사용 가능 여부"""
        return self._model is not None

    def compute_hash(self, title: str, content: str = "") -> str:
        """
        컨텐츠 해시 계산

        Args:
            title: 기사 제목
            content: 기사 본문 또는 설명

        Returns:
            SHA-256 해시 문자열
        """
        text = f"{title}{content}".strip().lower()
        return hashlib.sha256(text.encode()).hexdigest()

    def compute_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        텍스트 임베딩 벡터 계산

        Args:
            text: 입력 텍스트

        Returns:
            임베딩 벡터 (실패 시 None)
        """
        if not self._model:
            return None

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"임베딩 계산 실패: {e}")
            return None

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """코사인 유사도 계산"""
        if vec1 is None or vec2 is None:
            return 0.0

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def check_duplicate(
        self,
        title: str,
        content: str,
        existing_hashes: list[str] = None,
        existing_embeddings: dict[str, np.ndarray] = None
    ) -> DuplicateResult:
        """
        중복 여부 확인

        Args:
            title: 새 기사 제목
            content: 새 기사 본문 또는 설명
            existing_hashes: 기존 기사 해시 목록
            existing_embeddings: 기존 기사 임베딩 딕셔너리 {hash: embedding}

        Returns:
            DuplicateResult 객체
        """
        # 1. 해시 기반 중복 체크 (정확한 중복)
        new_hash = self.compute_hash(title, content)

        # 캐시에서 해시 체크
        if new_hash in self._hash_cache:
            return DuplicateResult(
                is_duplicate=True,
                similarity_score=1.0,
                matched_hash=new_hash
            )

        # 기존 해시 목록에서 체크
        if existing_hashes and new_hash in existing_hashes:
            return DuplicateResult(
                is_duplicate=True,
                similarity_score=1.0,
                matched_hash=new_hash
            )

        # 2. 의미적 유사도 기반 중복 체크 (유사한 중복)
        if self._model and existing_embeddings:
            new_text = f"{title} {content}"
            new_embedding = self.compute_embedding(new_text)

            if new_embedding is not None:
                max_similarity = 0.0
                matched_hash = None

                for existing_hash, existing_embedding in existing_embeddings.items():
                    similarity = self.cosine_similarity(new_embedding, existing_embedding)

                    if similarity > max_similarity:
                        max_similarity = similarity
                        matched_hash = existing_hash

                if max_similarity >= self.similarity_threshold:
                    return DuplicateResult(
                        is_duplicate=True,
                        similarity_score=max_similarity,
                        matched_hash=matched_hash
                    )

                # 캐시에 추가
                self._hash_cache.add(new_hash)
                self._embedding_cache[new_hash] = new_embedding

                return DuplicateResult(
                    is_duplicate=False,
                    similarity_score=max_similarity
                )

        # Sentence-BERT 사용 불가 시 해시만으로 판단
        self._hash_cache.add(new_hash)
        return DuplicateResult(is_duplicate=False, similarity_score=0.0)

    def check_duplicate_simple(
        self,
        title: str,
        content: str,
        existing_hashes: set[str]
    ) -> bool:
        """
        간단한 해시 기반 중복 체크

        Args:
            title: 기사 제목
            content: 기사 본문 또는 설명
            existing_hashes: 기존 기사 해시 집합

        Returns:
            중복 여부 (True/False)
        """
        new_hash = self.compute_hash(title, content)
        return new_hash in existing_hashes

    def embedding_to_json(self, embedding: np.ndarray) -> str:
        """임베딩 벡터를 JSON 문자열로 변환"""
        if embedding is None:
            return ""
        return json.dumps(embedding.tolist())

    def json_to_embedding(self, json_str: str) -> Optional[np.ndarray]:
        """JSON 문자열을 임베딩 벡터로 변환"""
        if not json_str:
            return None
        try:
            return np.array(json.loads(json_str))
        except Exception:
            return None

    def clear_cache(self):
        """캐시 초기화"""
        self._hash_cache.clear()
        self._embedding_cache.clear()


# 편의 함수
_deduplicator: Optional[ArticleDeduplicator] = None


def get_deduplicator() -> ArticleDeduplicator:
    """싱글톤 중복 탐지기 반환"""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = ArticleDeduplicator()
    return _deduplicator


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)

    dedup = ArticleDeduplicator()

    print(f"Sentence-BERT 사용 가능: {dedup.is_available}")

    # 테스트 기사들
    articles = [
        {
            "title": "식약처, 코로나19 자가진단키트 긴급사용 승인",
            "content": "식품의약품안전처가 새로운 코로나19 자가진단키트에 대한 긴급사용을 승인했다."
        },
        {
            "title": "식약처, 코로나19 자가진단키트 긴급사용 승인",  # 완전 중복
            "content": "식품의약품안전처가 새로운 코로나19 자가진단키트에 대한 긴급사용을 승인했다."
        },
        {
            "title": "코로나19 자가진단키트, 식약처 긴급승인 획득",  # 유사 중복
            "content": "식약처가 코로나19 자가진단키트의 긴급사용을 승인했다."
        },
        {
            "title": "헬스케어 스타트업, 100억 원 투자 유치",  # 다른 기사
            "content": "AI 기반 헬스케어 스타트업이 대규모 투자를 유치했다."
        },
    ]

    print("\n=== 중복 탐지 테스트 ===\n")

    existing_hashes = set()
    existing_embeddings = {}

    for i, article in enumerate(articles, 1):
        result = dedup.check_duplicate(
            article["title"],
            article["content"],
            list(existing_hashes),
            existing_embeddings
        )

        print(f"{i}. {article['title'][:40]}...")
        print(f"   중복: {result.is_duplicate} | 유사도: {result.similarity_score:.3f}")

        if not result.is_duplicate:
            # 기존 기사로 추가
            hash_val = dedup.compute_hash(article["title"], article["content"])
            existing_hashes.add(hash_val)

            if dedup.is_available:
                embedding = dedup.compute_embedding(f"{article['title']} {article['content']}")
                if embedding is not None:
                    existing_embeddings[hash_val] = embedding

        print()
