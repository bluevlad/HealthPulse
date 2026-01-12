"""
HTML 이메일 리포트 생성기
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import settings
from ..database.models import Article, CategoryType

logger = logging.getLogger(__name__)


class ReportGenerator:
    """HTML 이메일 리포트 생성기"""

    def __init__(self, template_dir: str = None):
        """
        Args:
            template_dir: 템플릿 디렉토리 경로
        """
        if template_dir is None:
            template_dir = settings.BASE_DIR / "templates"

        self.template_dir = Path(template_dir)

        # Jinja2 환경 설정
        self._env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 커스텀 필터 등록
        self._env.filters['format_date'] = self._format_date
        self._env.filters['truncate_text'] = self._truncate_text

    @staticmethod
    def _format_date(dt: datetime, fmt: str = "%Y-%m-%d %H:%M") -> str:
        """날짜 포맷팅"""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.strftime(fmt)

    @staticmethod
    def _truncate_text(text: str, length: int = 100) -> str:
        """텍스트 자르기"""
        if not text:
            return ""
        if len(text) <= length:
            return text
        return text[:length] + "..."

    def generate_daily_report(
        self,
        articles: list[Article],
        report_date: datetime = None,
        recipient_name: str = None,
        top_n: int = 5
    ) -> str:
        """
        일일 리포트 HTML 생성

        Args:
            articles: 기사 목록
            report_date: 리포트 날짜
            recipient_name: 수신자 이름
            top_n: TOP N 기사 수

        Returns:
            HTML 문자열
        """
        if report_date is None:
            report_date = datetime.now()

        # 카테고리별 그룹화
        articles_by_category = defaultdict(list)
        for article in articles:
            category = article.category or CategoryType.GENERAL
            articles_by_category[category].append(article)

        # 중요도 순 정렬
        for category in articles_by_category:
            articles_by_category[category].sort(
                key=lambda a: a.importance_score or 0,
                reverse=True
            )

        # TOP N 기사 추출
        top_articles = sorted(
            articles,
            key=lambda a: a.importance_score or 0,
            reverse=True
        )[:top_n]

        # 카테고리 순서 정의
        category_order = [
            CategoryType.REGULATORY,
            CategoryType.MARKET,
            CategoryType.TECHNOLOGY,
            CategoryType.COMPETITOR,
            CategoryType.PRODUCT,
            CategoryType.GENERAL,
        ]

        # 정렬된 카테고리별 기사
        sorted_categories = []
        for category in category_order:
            if category in articles_by_category:
                sorted_categories.append({
                    "name": category.value,
                    "articles": articles_by_category[category]
                })

        # 통계 정보
        stats = {
            "total_count": len(articles),
            "category_counts": {
                cat.value: len(articles_by_category.get(cat, []))
                for cat in category_order
            },
            "avg_importance": (
                sum(a.importance_score or 0 for a in articles) / len(articles)
                if articles else 0
            )
        }

        # 템플릿 렌더링
        try:
            template = self._env.get_template("email_report.html")
            html = template.render(
                report_date=report_date,
                recipient_name=recipient_name,
                top_articles=top_articles,
                categories=sorted_categories,
                stats=stats,
                generated_at=datetime.now(),
            )
            return html

        except Exception as e:
            logger.error(f"템플릿 렌더링 실패: {e}")
            # 폴백: 간단한 HTML 생성
            return self._generate_fallback_html(articles, report_date, recipient_name)

    def _generate_fallback_html(
        self,
        articles: list[Article],
        report_date: datetime,
        recipient_name: str = None
    ) -> str:
        """템플릿 실패 시 폴백 HTML 생성"""
        date_str = report_date.strftime("%Y년 %m월 %d일")

        html_parts = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'></head>",
            "<body style='font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;'>",
            f"<h1>HealthPulse 일일 브리핑</h1>",
            f"<p>{date_str}</p>",
        ]

        if recipient_name:
            html_parts.append(f"<p>{recipient_name}님께,</p>")

        html_parts.append(f"<p>오늘 수집된 뉴스 {len(articles)}건을 안내드립니다.</p>")
        html_parts.append("<hr>")

        for i, article in enumerate(articles[:20], 1):
            score = article.importance_score or 0
            category = article.category.value if article.category else "일반"

            html_parts.append(f"""
            <div style='margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;'>
                <h3 style='margin: 0 0 10px 0;'>
                    {i}. <a href='{article.link}' style='color: #1a73e8;'>{article.title}</a>
                </h3>
                <p style='color: #666; font-size: 14px; margin: 5px 0;'>
                    [{category}] 중요도: {score:.1%} | {article.source or '출처 미상'}
                </p>
                <p style='margin: 10px 0;'>{article.summary or article.description or ''}</p>
            </div>
            """)

        html_parts.append("<hr>")
        html_parts.append("<p style='color: #999; font-size: 12px;'>")
        html_parts.append("이 메일은 HealthPulse 시스템에서 자동 생성되었습니다.")
        html_parts.append("</p>")
        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def generate_summary_report(
        self,
        articles: list[Article],
        report_date: datetime = None
    ) -> str:
        """
        경영진용 요약 리포트 생성

        - TOP 5 뉴스만 포함
        - 간결한 형태
        """
        if report_date is None:
            report_date = datetime.now()

        # 중요도 상위 5개만
        top_articles = sorted(
            articles,
            key=lambda a: a.importance_score or 0,
            reverse=True
        )[:5]

        return self.generate_daily_report(
            articles=top_articles,
            report_date=report_date,
            top_n=5
        )


# 편의 함수
_generator: Optional[ReportGenerator] = None


def get_generator() -> ReportGenerator:
    """싱글톤 리포트 생성기 반환"""
    global _generator
    if _generator is None:
        _generator = ReportGenerator()
    return _generator
