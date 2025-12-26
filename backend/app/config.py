"""
Saju AI Service Settings v4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
99,000원 프리미엄 리포트 설정:
- RuleCard Top-100 제한
- JSON Schema 강제
- Semaphore(2), Retry 3회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    
    @property
    def clean_openai_api_key(self) -> str:
        return self.openai_api_key.strip().replace('\n', '').replace('\r', '')
    
    # KASI API
    kasi_api_key: str = ""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 99,000원 프리미엄 리포트 설정
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    # 섹션별 설정
    report_section_max_output_tokens: int = 4000  # 섹션당 최대 출력 토큰
    report_section_timeout: int = 90  # 섹션당 타임아웃 (초)
    
    # 동시성 (안정성 우선)
    report_max_concurrency: int = 2  # Semaphore 제한 (1~2)
    
    # Retry 설정
    report_max_retries: int = 3  # 최대 재시도 횟수
    report_retry_base_delay: float = 2.0  # 기본 대기 시간 (초)
    
    # RuleCard 설정
    report_rulecard_top_limit: int = 100  # Top-100 RuleCards만 사용
    
    # 전체 타임아웃
    report_total_timeout: int = 600  # 10분
    
    # 레거시 호환
    max_output_tokens: int = 12000
    max_input_tokens: int = 8000
    
    # Retry Settings (레거시)
    sajuos_max_retries: int = 3
    sajuos_timeout: int = 180
    sajuos_retry_base_delay: float = 1.0
    sajuos_retry_max_delay: float = 30.0
    
    # Cache
    cache_ttl_seconds: int = 86400
    cache_max_size: int = 10000
    
    # CORS
    allowed_origins: str = "http://localhost:3000,https://sajuos.com,https://www.sajuos.com"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    # Debug
    debug_show_refs: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()
