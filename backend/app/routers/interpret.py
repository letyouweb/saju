"""
/interpret 엔드포인트
- GPT 기반 사주 해석
- 구조화된 JSON 응답
- 오늘 날짜 컨텍스트 자동 주입 (연도 착각 방지)
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from app.models.schemas import (
    InterpretRequest,
    InterpretResponse,
    ErrorResponse,
    ConcernType
)
from app.services.gpt_interpreter import gpt_interpreter
from app.services.engine_v2 import SajuManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/interpret",
    response_model=InterpretResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="사주 해석",
    description="""
사주 원국과 고민을 입력받아 AI가 해석합니다.

**오늘 날짜 컨텍스트 자동 주입:**
- GPT에게 "오늘 날짜"를 명시적으로 전달하여 연도 착각 방지
- 예: "2024년 운세" 대신 정확한 "2025년 운세" 응답

**주의사항:**
- 의학/법률/투자 등 전문 분야 단정적 조언은 필터링됨
"""
)
async def interpret_saju(request: InterpretRequest):
    """
    사주 해석 API
    """
    
    # 사주 데이터 구성
    saju_data = {}
    
    if request.saju_result:
        saju_data = request.saju_result.model_dump()
    else:
        if not all([request.year_pillar, request.month_pillar, request.day_pillar]):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "MISSING_SAJU_DATA",
                    "message": "사주 정보가 필요합니다. saju_result 또는 각 기둥(년주/월주/일주)을 입력하세요."
                }
            )
        
        saju_data = {
            "year_pillar": request.year_pillar,
            "month_pillar": request.month_pillar,
            "day_pillar": request.day_pillar,
            "hour_pillar": request.hour_pillar,
            "day_master": request.day_pillar[0] if request.day_pillar else "",
            "day_master_element": ""
        }
    
    # ⚠️ 핵심: 오늘 날짜 컨텍스트 주입 (연도 착각 방지)
    question_with_context = SajuManager.inject_today_context(request.question)
    
    logger.info(f"Interpreting saju - Today: {SajuManager.get_today_string()}")
    
    # 해석 실행
    try:
        result = await gpt_interpreter.interpret(
            saju_data=saju_data,
            name=request.name,
            gender=request.gender.value if request.gender else None,
            concern_type=request.concern_type,
            question=question_with_context  # 날짜 컨텍스트 포함
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Interpretation error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERPRETATION_ERROR",
                "message": "사주 해석 중 오류가 발생했습니다.",
                "detail": str(e)
            }
        )


@router.get(
    "/interpret/today",
    summary="오늘 날짜 확인",
    description="서버가 인식하는 오늘 날짜를 확인합니다. (연도 착각 디버깅용)"
)
async def get_today_context():
    """오늘 날짜 컨텍스트 확인"""
    today = SajuManager.get_today_kst()
    sample_question = "올해 운세가 궁금합니다."
    
    return {
        "today_kst": SajuManager.get_today_string(),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "sample_input": sample_question,
        "sample_output": SajuManager.inject_today_context(sample_question)
    }


@router.get(
    "/interpret/cost-estimate",
    summary="비용 추정",
    description="사주 해석 1건당 예상 비용을 조회합니다."
)
async def get_cost_estimate(
    input_tokens: int = 1500,
    output_tokens: int = 1000
):
    """비용 추정 조회"""
    return gpt_interpreter.estimate_cost(input_tokens, output_tokens)


@router.get(
    "/interpret/concern-types",
    summary="고민 유형 목록",
    description="지원하는 고민 유형 목록을 조회합니다."
)
async def get_concern_types():
    """고민 유형 목록"""
    return {
        "concern_types": [
            {"value": "love", "label": "연애/결혼", "emoji": "💕"},
            {"value": "wealth", "label": "재물/금전", "emoji": "💰"},
            {"value": "career", "label": "직장/사업", "emoji": "💼"},
            {"value": "health", "label": "건강", "emoji": "🏥"},
            {"value": "study", "label": "학업/시험", "emoji": "📚"},
            {"value": "general", "label": "종합운세", "emoji": "🔮"}
        ]
    }
