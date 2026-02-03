"""
Ollama 기반 기사 요약 모듈
"""

import logging
from typing import Optional

import ollama
from ollama import ResponseError

from ..config import settings

logger = logging.getLogger(__name__)


class OllamaSummarizer:
    """Ollama 로컬 LLM 기반 요약기"""

    SUMMARIZE_PROMPT = """다음 뉴스 기사를 3-4문장으로 간결하게 요약해주세요.
핵심 내용과 중요한 수치/데이터를 포함해주세요.

제목: {title}

내용: {content}

요약:"""

    IMPORTANCE_PROMPT = """다음 뉴스 기사가 디지털 헬스케어/진단키트 회사에 얼마나 중요한지 0.0~1.0 사이 점수로 평가해주세요.

평가 기준:
- 규제/정책 변화 관련: 높은 점수
- 시장 동향/경쟁사 관련: 중간~높은 점수
- 기술/R&D 관련: 중간 점수
- 일반 뉴스: 낮은 점수

제목: {title}
내용: {content}

숫자만 응답해주세요 (예: 0.75):"""

    def __init__(
        self,
        model: str = None,
        host: str = None
    ):
        self.model = model or settings.ollama_model
        self.host = host or settings.ollama_host

        # Ollama 클라이언트 설정
        self._client = ollama.Client(host=self.host)
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Ollama 서버 및 모델 사용 가능 여부 확인"""
        try:
            models = self._client.list()
            model_names = [m['name'] for m in models.get('models', [])]

            # 모델명에서 태그 제거 (qwen2.5:7b -> qwen2.5)
            base_model = self.model.split(':')[0]

            for name in model_names:
                if base_model in name:
                    logger.info(f"Ollama 모델 '{self.model}' 사용 가능")
                    return True

            logger.warning(
                f"Ollama 모델 '{self.model}'을 찾을 수 없습니다. "
                f"사용 가능한 모델: {model_names}"
            )
            return False

        except Exception as e:
            logger.warning(f"Ollama 서버 연결 실패: {e}")
            return False

    @property
    def is_available(self) -> bool:
        """Ollama 사용 가능 여부"""
        return self._available

    def summarize(self, title: str, content: str) -> str:
        """
        기사 요약 생성

        Args:
            title: 기사 제목
            content: 기사 본문 또는 설명

        Returns:
            요약된 텍스트 (실패 시 빈 문자열)
        """
        if not self._available:
            return self._fallback_summary(title, content)

        prompt = self.SUMMARIZE_PROMPT.format(title=title, content=content)

        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.3,
                    "num_predict": 200,
                }
            )
            summary = response.get("response", "").strip()
            return summary if summary else self._fallback_summary(title, content)

        except ResponseError as e:
            logger.error(f"Ollama 요약 생성 실패: {e}")
            return self._fallback_summary(title, content)
        except Exception as e:
            logger.error(f"요약 생성 중 오류: {e}")
            return self._fallback_summary(title, content)

    def score_importance(self, title: str, content: str) -> float:
        """
        기사 중요도 점수 산정

        Args:
            title: 기사 제목
            content: 기사 본문 또는 설명

        Returns:
            0.0 ~ 1.0 사이 점수
        """
        if not self._available:
            return self._fallback_importance(title, content)

        prompt = self.IMPORTANCE_PROMPT.format(title=title, content=content)

        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.1,
                    "num_predict": 10,
                }
            )
            score_text = response.get("response", "").strip()

            # 숫자 추출
            import re
            match = re.search(r'(\d+\.?\d*)', score_text)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0)

            return self._fallback_importance(title, content)

        except Exception as e:
            logger.error(f"중요도 점수 산정 중 오류: {e}")
            return self._fallback_importance(title, content)

    def _fallback_summary(self, title: str, content: str) -> str:
        """
        Ollama 사용 불가 시 폴백 요약

        - 기사 설명의 앞부분을 그대로 사용
        """
        if content:
            # 첫 200자 사용
            summary = content[:200]
            if len(content) > 200:
                summary += "..."
            return summary
        return title

    def _fallback_importance(self, title: str, content: str) -> float:
        """
        Ollama 사용 불가 시 키워드 기반 중요도 산정
        """
        text = f"{title} {content}".lower()

        # 중요 키워드 및 가중치
        high_keywords = ["fda", "식약처", "승인", "인허가", "규제", "허가"]
        medium_keywords = ["투자", "m&a", "인수", "시장", "임상", "연구", "특허"]
        low_keywords = ["행사", "이벤트", "인터뷰", "기고"]

        score = 0.5  # 기본 점수

        for kw in high_keywords:
            if kw in text:
                score += 0.1

        for kw in medium_keywords:
            if kw in text:
                score += 0.05

        for kw in low_keywords:
            if kw in text:
                score -= 0.1

        return min(max(score, 0.0), 1.0)


# 편의 함수
_summarizer: Optional[OllamaSummarizer] = None


def get_summarizer() -> OllamaSummarizer:
    """싱글톤 요약기 반환"""
    global _summarizer
    if _summarizer is None:
        _summarizer = OllamaSummarizer()
    return _summarizer


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)

    summarizer = OllamaSummarizer()

    print(f"Ollama 사용 가능: {summarizer.is_available}")

    # 테스트 기사
    test_title = "식약처, 코로나19 자가진단키트 긴급사용 승인"
    test_content = """
    식품의약품안전처가 새로운 코로나19 자가진단키트에 대한 긴급사용을 승인했다.
    이번에 승인된 제품은 기존 제품 대비 정확도가 15% 향상되었으며,
    결과 확인 시간도 15분에서 10분으로 단축되었다.
    해당 제품은 다음 주부터 전국 약국에서 판매될 예정이다.
    """

    summary = summarizer.summarize(test_title, test_content)
    print(f"\n요약:\n{summary}")

    score = summarizer.score_importance(test_title, test_content)
    print(f"\n중요도 점수: {score:.2f}")
