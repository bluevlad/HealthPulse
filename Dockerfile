# HealthPulse Docker Image
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY src/ ./src/
COPY config/ ./config/
COPY templates/ ./templates/

# 데이터 디렉토리 생성
RUN mkdir -p /app/data /app/logs

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 포트 노출
EXPOSE 4030

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:4030/api/health')" || exit 1

# 실행
CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "4030"]
