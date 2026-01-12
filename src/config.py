"""
HealthPulse 설정 관리 모듈
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # 프로젝트 경로
    BASE_DIR: Path = Path(__file__).parent.parent

    # 네이버 API
    naver_client_id: str = Field(default="", env="NAVER_CLIENT_ID")
    naver_client_secret: str = Field(default="", env="NAVER_CLIENT_SECRET")

    # Ollama
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    ollama_model: str = Field(default="qwen2.5:7b", env="OLLAMA_MODEL")

    # Gmail SMTP
    gmail_address: str = Field(default="", env="GMAIL_ADDRESS")
    gmail_app_password: str = Field(default="", env="GMAIL_APP_PASSWORD")

    # 데이터베이스
    database_url: str = Field(
        default="sqlite:///./data/healthpulse.db",
        env="DATABASE_URL"
    )

    # 스케줄러
    schedule_hour: int = Field(default=8, env="SCHEDULE_HOUR")
    schedule_minute: int = Field(default=0, env="SCHEDULE_MINUTE")

    # 로깅
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()


settings = get_settings()
