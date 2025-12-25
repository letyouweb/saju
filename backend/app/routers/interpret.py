"""
/interpret endpoint - Production Ready
- 2026 신년운세: target_year 강제 컨텍스트
- RuleCards 8,500장 데이터 자동 활용
"""
from fastapi import APIRouter, HTTPException, Request, Query
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

# RuleCard pipeline
from app.services.feature_tags_no_time import build_feature_tags_no_time_from_pillars
from app.services.preset_type2 import BUSINESS_OWNER_PRESET_V2
from app.services.focus_boost import boost_preset_focus
from app.services.rulecard_selector import select_cards_for_preset

logger = logging.getLogger(__name__)
router = APIRouter()


# ============ 2026 컨텍스트 강제 ============

def inject_year_context(question: str, target_year: int) -> str:
    """
    2026 신년운세용: 연도 강제 컨텍스트 주입
    """
    return f"""[분석 기준 고정]
- 이 분석은 반드시 {target_year}년 1월~12월 기준으로만 작성합니다.
- 월별 운세/좋은 시기/조심할 시기는 {target_year}년 달력 흐름으로 제시합니다.
- 다른 연도(예: 올해/작년/오늘 날짜)를 근거로 섞어 말하지 않습니다.

[사용자 질문]
{question}""".strip()


# ============ RuleCards 컨텍스트 생성 ============

def _compress_rulecards_for_prompt(selection: dict, max_cards_per_section: int = 8) -> str:
    """RuleCards를 GPT 프롬프트용으로 압축"""
    lines = ["[사주OS RuleCard 컨텍스트 - 8,500장 전문 데이터 기반]"]
    
    total_cards = 0
    for sec in selection.get("sections", []):
        title = sec.get("title", sec.get("key", ""))
        meta = sec.get("meta", {})
        avg_overlap = meta.get("avgOverlap", 0)
        
        cards = sec.get("cards", [])[:max_cards_per_section]
        if not cards:
            continue
            
        lines.append(f"\n## {title} (매칭도={avg_overlap:.1f})")

        for c in cards:
            total_cards += 1
            cid = c.get("id", "")
            topic = c.get("topic", "")
            tags = ", ".join((c.get("tags") or [])[:6])
            trig = c.get("trigger", "")
            if isinstance(trig, dict):
                trig = trig.get("note", "")
            trig = str(trig)[:100]
            mech = (c.get("mechanism") or "")[:150]
            interp = (c.get("interpretation") or "")[:150]
            act = (c.get("action") or "")[:150]
            
            lines.append(f"- [{cid}] {topic}")
            lines.append(f"  tags: {tags}")
            if trig: lines.append(f"  trigger: {trig}")
            if mech: lines.append(f"  mechanism: {mech}")
            if interp: lines.append(f"  interpretation: {interp}")
            if act: lines.append(f"  action: {act}")

    lines.append(f"\n[총 {total_cards}개 RuleCard 참조]")
    lines.append("[지침] 위 RuleCard를 근거로 구체적이고 실행 가능한 조언을 제공하세요.")
    return "\n".join(lines)


def _get_pillar_ganji(pillar_data) -> str:
    """
    사주 기둥에서 간지 문자열 추출
    - Pillar dict: {"gan": "무", "ji": "인", "ganji": "무인", ...} → '무인'
    - str: '무인' → '무인'
    """
    if isinstance(pillar_data, dict):
        # ganji 필드 우선
        if pillar_data.get("ganji"):
            return pillar_data["ganji"]
        # gan + ji 조합
        gan = pillar_data.get("gan", "")
        ji = pillar_data.get("ji", "")
        if gan and ji:
            return gan + ji
        return ""
    elif isinstance(pillar_data, str):
        return pillar_data
    return ""


def _extract_pillars_from_saju_data(saju_data: dict) -> tuple:
    """
    사주 데이터에서 연/월/일 간지 추출
    
    지원 구조:
    1. saju_result.saju.year_pillar.ganji (프론트엔드 전체 구조)
    2. saju_data.year_pillar.ganji (saju 서브필드)
    3. saju_data.year_pillar (문자열)
    """
    # Case 1: saju 서브필드가 있는 경우 (saju_result.saju)
    if "saju" in saju_data and isinstance(saju_data["saju"], dict):
        saju = saju_data["saju"]
        year_p = _get_pillar_ganji(saju.get("year_pillar", {}))
        month_p = _get_pillar_ganji(saju.get("month_pillar", {}))
        day_p = _get_pillar_ganji(saju.get("day_pillar", {}))
        return year_p, month_p, day_p
    
    # Case 2: 직접 year_pillar 필드 (문자열 또는 dict)
    year_p = _get_pillar_ganji(saju_data.get("year_pillar", saju_data.get("year", "")))
    month_p = _get_pillar_ganji(saju_data.get("month_pillar", saju_data.get("month", "")))
    day_p = _get_pillar_ganji(saju_data.get("day_pillar", saju_data.get("day", "")))
    
    return year_p, month_p, day_p


def build_rulecards_context(saju_data: dict, store, target_year: int = 2026) -> tuple:
    """
    사주 데이터에서 RuleCards 컨텍스트 생성
    Returns: (context_string, feature_tags_list, cards_count)
    """
    # 사주 기둥 추출 (다양한 구조 지원)
    year_p, month_p, day_p = _extract_pillars_from_saju_data(saju_data)
    
    logger.info(f"[RuleCards] 추출된 기둥: 년={year_p}, 월={month_p}, 일={day_p}")
    
    if not (year_p and month_p and day_p):
        logger.warning("[RuleCards] 사주 기둥 데이터 부족")
        return "", [], 0
    
    # Feature Tags 생성
    ft = build_feature_tags_no_time_from_pillars(year_p, month_p, day_p, overlay_year=target_year)
    feature_tags = ft.get("tags", [])
    
    # Preset 부스트 및 카드 선택
    boosted = boost_preset_focus(BUSINESS_OWNER_PRESET_V2, feature_tags)
    selection = select_cards_for_preset(store, boosted, feature_tags)
    
    # 컨텍스트 압축
    context = _compress_rulecards_for_prompt(selection)
    
    # 총 카드 수 계산
    total_cards = sum(len(sec.get("cards", [])) for sec in selection.get("sections", []))
    
    return context, feature_tags, total_cards


@router.post(
    "/interpret",
    response_model=InterpretResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Saju Interpretation (RuleCards 자동 적용)"
)
async def interpret_saju(
    payload: InterpretRequest,
    raw: Request,
    mode: str = Query("auto", description="auto | direct (auto=RuleCards 자동 적용)")
):
    """
    사주 해석 API
    - 8,500장 RuleCards 데이터 자동 활용
    - 2026년 신년운세 기준
    """
    saju_data = {}

    if payload.saju_result:
        saju_data = payload.saju_result.model_dump()
    else:
        if not all([payload.year_pillar, payload.month_pillar, payload.day_pillar]):
            raise HTTPException(status_code=400, detail={"error_code": "MISSING_SAJU_DATA", "message": "Saju data required"})

        saju_data = {
            "year_pillar": payload.year_pillar,
            "month_pillar": payload.month_pillar,
            "day_pillar": payload.day_pillar,
            "hour_pillar": payload.hour_pillar,
            "day_master": payload.day_pillar[0] if payload.day_pillar else "",
            "day_master_element": ""
        }

    question = payload.question
    
    # 2026 신년운세: target_year 항상 우선 (기본 2026)
    final_year = payload.target_year if payload.target_year else 2026
    
    # RuleCards 컨텍스트 생성 (자동)
    store = getattr(raw.app.state, "rulestore", None)
    rulecards_context = ""
    feature_tags = []
    cards_count = 0
    
    if store and mode != "direct":
        try:
            rulecards_context, feature_tags, cards_count = build_rulecards_context(
                saju_data, store, final_year
            )
            if rulecards_context:
                question = f"{question}\n\n[featureTags] {', '.join(feature_tags[:20])}\n\n{rulecards_context}"
                logger.info(f"[RuleCards] ✅ 적용: {cards_count}장, featureTags={len(feature_tags)}")
        except Exception as e:
            logger.warning(f"[RuleCards] 컨텍스트 생성 실패: {e}")
    else:
        if not store:
            logger.warning("[RuleCards] ⚠️ RuleStore 미로드 - direct 모드로 진행")
        else:
            logger.info("[RuleCards] direct 모드 - RuleCards 미적용")
    
    # 연도 컨텍스트 주입
    question_with_context = inject_year_context(question, final_year)
    
    logger.info(f"[INTERPRET] TargetYear={final_year} | Mode={mode} | RuleCards={cards_count}장")

    try:
        result = await gpt_interpreter.interpret(
            saju_data=saju_data,
            name=payload.name,
            gender=payload.gender.value if payload.gender else None,
            concern_type=payload.concern_type,
            question=question_with_context
        )
        return result
    except Exception as e:
        logger.error(f"[INTERPRET] Error: {type(e).__name__}")
        raise HTTPException(status_code=500, detail={"error_code": "INTERPRETATION_ERROR", "message": str(e)[:200]})


@router.post(
    "/generate-report",
    response_model=InterpretResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Generate Saju Report (RuleCards 자동 적용)"
)
async def generate_report(
    payload: InterpretRequest,
    raw: Request,
    mode: str = Query("auto", description="auto | direct")
):
    """Generate Saju Report - Alias endpoint for /interpret"""
    return await interpret_saju(payload, raw, mode)


@router.get("/interpret/today", summary="Today Date")
async def get_today_context():
    today = SajuManager.get_today_kst()
    return {
        "today_kst": SajuManager.get_today_string(),
        "year": today.year,
        "month": today.month,
        "day": today.day
    }


@router.get("/interpret/cost-estimate", summary="Cost Estimate")
async def get_cost_estimate(input_tokens: int = 1500, output_tokens: int = 1000):
    return gpt_interpreter.estimate_cost(input_tokens, output_tokens)


@router.get("/interpret/concern-types", summary="Concern Types")
async def get_concern_types():
    return {
        "concern_types": [
            {"value": "love", "label": "Love/Marriage", "emoji": "💕"},
            {"value": "wealth", "label": "Wealth/Finance", "emoji": "💰"},
            {"value": "career", "label": "Career/Business", "emoji": "💼"},
            {"value": "health", "label": "Health", "emoji": "🏥"},
            {"value": "study", "label": "Study/Exam", "emoji": "📚"},
            {"value": "general", "label": "General Fortune", "emoji": "🔮"}
        ]
    }


@router.get("/interpret/rulecards-status", summary="RuleCards Status")
async def get_rulecards_status(raw: Request):
    """RuleCards 로드 상태 확인"""
    store = getattr(raw.app.state, "rulestore", None)
    if store:
        return {
            "loaded": True,
            "total_cards": len(store.cards),
            "topics": list(store.by_topic.keys()),
            "topics_count": len(store.by_topic)
        }
    return {
        "loaded": False,
        "total_cards": 0,
        "topics": [],
        "topics_count": 0
    }


@router.get("/interpret/gpt-test", summary="GPT API Test")
async def test_gpt_connection():
    """Direct GPT call test"""
    from app.config import get_settings
    from app.services.openai_key import get_openai_api_key, key_fingerprint, key_tail
    from openai import AsyncOpenAI
    import httpx
    
    settings = get_settings()
    
    try:
        api_key = get_openai_api_key()
        key_set = True
        key_preview = f"fp={key_fingerprint(api_key)} tail={key_tail(api_key)}"
    except RuntimeError as e:
        api_key = None
        key_set = False
        key_preview = str(e)
    
    result = {
        "api_key_set": key_set,
        "api_key_preview": key_preview,
        "model": settings.openai_model,
        "max_retries": settings.sajuos_max_retries,
        "timeout": settings.sajuos_timeout,
    }
    
    if not api_key:
        result["success"] = False
        result["error"] = "OPENAI_API_KEY not set or invalid"
        return result
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=10.0)
        )
        
        chat_resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=20
        )
        
        result["success"] = True
        result["response"] = chat_resp.choices[0].message.content
        result["model_used"] = chat_resp.model
        result["status"] = "READY_FOR_PRODUCTION"
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:300]
        
        result["success"] = False
        result["error_type"] = error_type
        result["error"] = error_msg
        
        if "401" in error_msg or "auth" in error_msg.lower():
            result["guidance"] = "Check API key validity and permissions"
        elif "429" in error_msg or "rate" in error_msg.lower():
            result["guidance"] = "Rate limited - wait and retry"
        elif "quota" in error_msg.lower():
            result["guidance"] = "Add billing credits at platform.openai.com"
        elif "404" in error_msg:
            result["guidance"] = f"Model '{settings.openai_model}' not found"
        else:
            result["guidance"] = "Check Railway logs for details"
    
    return result
