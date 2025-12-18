"""
사주 AI 서비스 - FastAPI 메인 앱

아키텍처:
- Railway 호스팅
- Vercel(sajuqueen.com)에서 직접 호출
- CORS 필수 설정
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.routers import calculate, interpret

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리"""
    logger.info("🚀 사주 AI 서비스 시작")
    settings = get_settings()
    
    # 환경변수 확인
    if not settings.openai_api_key:
        logger.error("❌ OPENAI_API_KEY가 설정되지 않았습니다!")
    else:
        key_preview = settings.openai_api_key[:10] + "..." if len(settings.openai_api_key) > 10 else "???"
        logger.info(f"✅ OPENAI_API_KEY 로드됨: {key_preview}")
    
    if not settings.kasi_api_key:
        logger.warning("⚠️ KASI_API_KEY 미설정 - ephem Fallback 모드")
    
    # CORS 설정 로깅
    logger.info(f"✅ CORS 허용 도메인: {settings.allowed_origins_list}")
    
    yield
    
    logger.info("👋 사주 AI 서비스 종료")


# FastAPI 앱 생성
app = FastAPI(
    title="사주 AI 서비스",
    description="""
## 🔮 AI 기반 사주 해석 서비스

### 주요 기능
- `/api/v1/calculate`: 생년월일 → 사주 원국 계산
- `/api/v1/interpret`: 사주 원국 → AI 해석

### 아키텍처
- Backend: Railway (FastAPI)
- Frontend: Vercel (Next.js)
- 직접 통신 (CORS 설정)

### ⚠️ 면책 조항
본 서비스는 오락/참고 목적으로 제공되며, 의학/법률/투자 등 전문적 조언을 대체하지 않습니다.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============ CORS 설정 ============
# 중요: sajuqueen.com에서 직접 호출 허용
settings = get_settings()

# CORS 허용 도메인 검증
REQUIRED_ORIGINS = ["https://sajuqueen.com", "https://www.sajuqueen.com"]
for origin in REQUIRED_ORIGINS:
    if origin not in settings.allowed_origins_list:
        logger.warning(f"⚠️ CORS 경고: {origin}이 allowed_origins에 없습니다!")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 라우터 등록
app.include_router(calculate.router, prefix="/api/v1", tags=["사주 계산"])
app.include_router(interpret.router, prefix="/api/v1", tags=["사주 해석"])


# ============ 시스템 엔드포인트 ============

@app.get("/", tags=["시스템"])
async def root():
    """서비스 상태 확인"""
    return {
        "service": "사주 AI 서비스",
        "status": "running",
        "version": "1.0.0",
        "cors_origins": settings.allowed_origins_list,
        "endpoints": {
            "calculate": "/api/v1/calculate",
            "interpret": "/api/v1/interpret",
            "docs": "/docs"
        }
    }


@app.get("/health", tags=["시스템"])
async def health_check():
    """헬스체크"""
    return {"status": "healthy"}


@app.get("/cors-test", tags=["시스템"])
async def cors_test(request: Request):
    """
    CORS 디버깅용 엔드포인트
    - Origin 헤더 확인
    - 허용 여부 확인
    """
    origin = request.headers.get("origin", "없음")
    is_allowed = origin in settings.allowed_origins_list or origin == "없음"
    
    return {
        "request_origin": origin,
        "allowed_origins": settings.allowed_origins_list,
        "is_allowed": is_allowed,
        "note": "CORS preflight는 브라우저가 자동으로 처리합니다."
    }


@app.get("/env-check", tags=["시스템"])
async def env_check():
    """환경변수 상태 확인 (민감 정보 마스킹)"""
    return {
        "openai_api_key": "✅ 설정됨" if settings.openai_api_key else "❌ 미설정",
        "kasi_api_key": "✅ 설정됨" if settings.kasi_api_key else "⚠️ 미설정 (Fallback)",
        "allowed_origins": settings.allowed_origins_list,
        "debug_mode": settings.debug,
    }


# ============ 에러 핸들러 ============

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "서버 내부 오류가 발생했습니다.",
            "detail": str(exc) if settings.debug else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
