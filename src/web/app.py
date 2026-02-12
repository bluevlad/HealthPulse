"""
HealthPulse Web Application
Subscription management and newsletter preview

라우트 구성:
- routes/public.py: 구독자 대면 페이지 (구독, 인증, 해지, 관리)
- routes/admin.py: 관리자 페이지 (대시보드, 구독자, 발송이력, 기사)
- routes/api.py: REST API 엔드포인트 (통계, 헬스체크)
"""

import logging
import logging.config
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.database import init_db

# 구조화 로깅 설정
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
        "security": {
            "format": '{"timestamp":"%(asctime)s","level":"%(levelname)s","type":"SECURITY","message":"%(message)s"}',
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "stream": "ext://sys.stdout",
        },
        "security_console": {
            "class": "logging.StreamHandler",
            "formatter": "security",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "": {"level": "INFO", "handlers": ["console"]},
        "security": {"level": "INFO", "handlers": ["security_console"], "propagate": False},
        "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "sqlalchemy.engine": {"level": "WARNING", "handlers": ["console"], "propagate": False},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

# FastAPI 앱 생성
app = FastAPI(
    title="HealthPulse",
    description="디지털 헬스케어 뉴스 구독 서비스",
    version="1.0.0"
)


# CSRF Origin Check Middleware
class CSRFOriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin:
                parsed = urlparse(origin)
                allowed_hosts = {
                    urlparse(settings.web_base_url).hostname,
                    "localhost",
                    "127.0.0.1",
                }
                if parsed.hostname not in allowed_hosts:
                    security_logger.warning("CSRF check failed: origin=%s", origin)
                    raise HTTPException(status_code=403, detail="Forbidden: invalid origin")
        return await call_next(request)

app.add_middleware(CSRFOriginCheckMiddleware)

# Static files
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Initialize database
init_db(settings.database_url)

# Include routers
from src.web.routes import public_router, admin_router, api_router

app.include_router(public_router)
app.include_router(admin_router)
app.include_router(api_router)


# Run Server
def run_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
