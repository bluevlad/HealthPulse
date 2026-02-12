# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 상위 `C:/GIT/CLAUDE.md`의 Git-First Workflow를 상속합니다.

## Project Overview

HealthPulse - 디지털 헬스케어 뉴스 모니터링 시스템 (네이버 뉴스 수집 → AI 분석 → 이메일 뉴스레터)

## Environment

- **Database**: SQLite (SQLAlchemy ORM)
- **Target Server**: MacBook Docker (172.30.1.72) / Windows 로컬 개발
- **Docker Strategy**: Docker Compose (web + scheduler)
- **Python Version**: 3.10+
- **AI**: Ollama (로컬 LLM, qwen2.5:7b)

## Tech Stack

| 항목 | 기술 |
|------|------|
| Language | Python 3.10+ |
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0+ |
| Database | SQLite |
| Scheduler | APScheduler |
| AI/ML | Ollama (로컬), scikit-learn |
| HTTP Client | httpx, requests |
| Email | Gmail SMTP (aiosmtplib) |
| Template | Jinja2 |
| Config | Pydantic + python-dotenv |
| Web Scraping | BeautifulSoup4, lxml |

## Setup and Run Commands

```bash
# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt

# 실행 모드
python -m src.main              # 스케줄러 모드 (기본, 크롤링 7시/발송 8시)
python -m src.main --web        # 웹 서버 모드 (uvicorn src.web.app:app)
python -m src.main --run-once   # 1회 실행 (수집 → 분석 → 발송)
python -m src.main --collect-only  # 수집만
python -m src.main --process-only  # AI 분석만
python -m src.main --send-only     # 발송만

# Docker
docker compose up -d            # 개발
docker compose -f docker-compose.prod.yml up -d  # 운영

# 테스트
pytest tests/

# E2E 테스트 (e2e/)
cd e2e
npm install
npm run test        # Playwright 테스트
npm run test:ui     # UI 모드
npm run test:report # 리포트
```

Default server port: 4030

## Project Structure

```
HealthPulse/
├── src/
│   ├── main.py              # 엔트리포인트
│   ├── config.py            # Pydantic 설정
│   ├── collector/           # 뉴스 수집 (네이버 API)
│   ├── database/            # SQLAlchemy 모델/세션
│   ├── mailer/              # 이메일 발송
│   ├── notifier/            # 알림
│   ├── processor/           # AI 분석 (Ollama)
│   ├── reporter/            # 리포트 생성
│   ├── subscription/        # 구독 관리
│   └── web/                 # FastAPI 웹 앱
├── templates/               # 이메일 HTML 템플릿
├── config/                  # 설정 파일
├── tests/                   # 테스트
├── data/                    # SQLite DB (자동 생성)
└── logs/
```

## Do NOT

- .env 파일 커밋 금지
- requirements.txt에 없는 패키지를 설치 없이 import 금지
- pydantic v1 문법과 v2 문법 혼용 금지 (v2 사용)
- 서버 주소, 비밀번호 추측 금지 — 반드시 확인 후 사용
- 운영 Docker 컨테이너 직접 조작 금지 (healthpulse-web, healthpulse-scheduler)
- 자격증명(비밀번호, API 키)을 소스코드에 하드코딩하지 마라
- CORS에 allow_origins=["*"] 또는 origins="*" 사용하지 마라
- API 엔드포인트를 인증 없이 노출하지 마라
- console.log/print로 민감 정보를 출력하지 마라

## Required Environment Variables

```
NAVER_CLIENT_ID=         # 네이버 API
NAVER_CLIENT_SECRET=
OLLAMA_HOST=             # Ollama 서버 (기본: http://host.docker.internal:11434)
OLLAMA_MODEL=            # 모델명 (기본: qwen2.5:7b)
GMAIL_ADDRESS=           # Gmail 발송
GMAIL_APP_PASSWORD=
DATABASE_URL=            # SQLite (기본: sqlite:///./data/healthpulse.db)
CRAWL_HOUR=              # 크롤링 시간 (기본: 7)
CRAWL_MINUTE=            # 크롤링 분 (기본: 0)
SEND_HOUR=               # 발송 시간 (기본: 8)
SEND_MINUTE=             # 발송 분 (기본: 0)
LOG_LEVEL=               # 로그 레벨 (기본: INFO)
```

## Deployment

- **CI/CD**: GitHub Actions (prod 브랜치 push 시 자동 배포)
- **운영 포트**: 4030
- **헬스체크**: http://localhost:4030/api/health

> 로컬 환경 정보는 `CLAUDE.local.md` 참조 (git에 포함되지 않음)
