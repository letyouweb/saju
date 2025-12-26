"""
SajuOS Premium Report Builder v2
- 99,000원 30페이지 비즈니스 컨설팅 리포트 엔진
- 7개 섹션 분할 생성 (Chaining) + 병렬 처리
- 용어 치환 레이어 (명리학 → 비즈니스)
- 분량 강제 + 자동 확장 루프
- 최종 Polish Pass
"""
import asyncio
import logging
import time
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from openai import AsyncOpenAI
import httpx

from app.config import get_settings
from app.services.openai_key import get_openai_api_key
from app.services.terminology_mapper import (
    sanitize_for_business,
    get_business_prompt_rules,
    validate_no_forbidden_terms
)

logger = logging.getLogger(__name__)


# ============ 섹션 정의 (프리미엄 스펙) ============

@dataclass
class SectionSpec:
    id: str
    title: str
    pages: int
    rulecard_quota: int
    topics: List[str]
    min_chars: int  # 최소 글자수
    required_elements: List[str]  # 필수 포함 요소
    

PREMIUM_SECTIONS: Dict[str, SectionSpec] = {
    "exec": SectionSpec(
        id="exec",
        title="Executive Summary",
        pages=2,
        rulecard_quota=50,
        topics=["general", "personality", "yearly_fortune"],
        min_chars=2000,
        required_elements=[
            "현상 진단",
            "핵심 가설 3개",
            "전략적 방향성",
            "즉시 실행 과제 5개",
            "핵심 KPI 3개"
        ]
    ),
    "money": SectionSpec(
        id="money",
        title="Money & Cashflow",
        pages=5,
        rulecard_quota=80,
        topics=["wealth", "finance", "investment"],
        min_chars=4000,
        required_elements=[
            "현금흐름 현상 진단",
            "수익 구조 가설 3개",
            "전략 옵션 3개(각각 장단점)",
            "추천 전략 + 주간 실행 계획",
            "재무 KPI 5개",
            "리스크 시나리오 3개 + 방어 전략"
        ]
    ),
    "business": SectionSpec(
        id="business",
        title="Business Strategy",
        pages=5,
        rulecard_quota=80,
        topics=["career", "business", "leadership"],
        min_chars=4000,
        required_elements=[
            "시장 포지션 진단",
            "성장 가설 3개",
            "전략 옵션 3개(장단점 포함)",
            "추천 전략 + 분기별 실행 로드맵",
            "성과 KPI 5개",
            "경쟁 리스크 분석 + 대응"
        ]
    ),
    "team": SectionSpec(
        id="team",
        title="Team & Partner Risk",
        pages=4,
        rulecard_quota=60,
        topics=["relationship", "partnership", "conflict"],
        min_chars=3000,
        required_elements=[
            "조직/파트너십 현상 진단",
            "관계 역학 가설 3개",
            "팀 구성 전략 옵션 3개",
            "추천 인재/파트너 프로파일",
            "갈등 조기 경보 지표",
            "위기 대응 프로토콜"
        ]
    ),
    "health": SectionSpec(
        id="health",
        title="Health & Performance",
        pages=3,
        rulecard_quota=50,
        topics=["health", "energy", "wellness"],
        min_chars=2500,
        required_elements=[
            "에너지/퍼포먼스 현상 진단",
            "번아웃 리스크 가설 3개",
            "워라밸 전략 옵션 3개",
            "주간 루틴 권장안",
            "건강 KPI (체크 주기 포함)",
            "위험 신호 + 대응"
        ]
    ),
    "calendar": SectionSpec(
        id="calendar",
        title="12-Month Tactical Calendar",
        pages=6,
        rulecard_quota=100,
        topics=["monthly", "timing", "seasonal"],
        min_chars=5000,
        required_elements=[
            "연간 전략 테마",
            "12개월 각각: 핵심 KPI, 권장 액션 5개, 금기 사항 3개",
            "분기별 마일스톤",
            "최고 성과 예상 월 Top 3",
            "고위험 월 + 대응 전략"
        ]
    ),
    "sprint": SectionSpec(
        id="sprint",
        title="90-Day Sprint Plan",
        pages=5,
        rulecard_quota=80,
        topics=["action", "planning", "execution"],
        min_chars=4000,
        required_elements=[
            "90일 미션 선언문",
            "12주 각각: 목표 2개, KPI 2개, 일일 액션",
            "30/60/90일 마일스톤 + 성공 기준",
            "주간 점검 체크리스트",
            "실패 시나리오 + 피벗 플랜"
        ]
    )
}


# ============ 섹션별 프롬프트 (비즈니스 컨설팅 스타일) ============

def get_premium_system_prompt(section_id: str, target_year: int) -> str:
    """프리미엄 섹션별 시스템 프롬프트"""
    
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        spec = PREMIUM_SECTIONS["exec"]
    
    terminology_rules = get_business_prompt_rules()
    
    base = f"""당신은 99,000원 프리미엄 비즈니스 컨설팅 보고서를 작성하는 시니어 전략 컨설턴트입니다.
맥킨지, BCG, 베인 수준의 분석적 깊이와 실행 가능성을 갖춘 보고서를 작성합니다.

## 분석 기준년도: {target_year}년

## 핵심 원칙
1. **사주 풀이 금지**: 이 보고서는 '운세'가 아니라 '경영 전략 보고서'입니다
2. **데이터 기반**: 제공된 RuleCard 데이터를 근거로 가설을 세우고 전략을 도출합니다
3. **실행 가능성**: 모든 제안은 구체적 일정, 담당자, 예산 수준을 포함해야 합니다
4. **측정 가능성**: 모든 목표는 KPI로 측정 가능해야 합니다

{terminology_rules}

## 이 섹션의 요구사항: {spec.title}
- 최소 분량: {spec.min_chars}자 이상
- 필수 포함 요소:
{chr(10).join(f'  - {elem}' for elem in spec.required_elements)}

## 출력 형식
반드시 아래 JSON 구조로만 응답하세요 (마크다운 코드블록 없이):

{{
  "title": "{spec.title}",
  "diagnosis": {{
    "current_state": "현상 진단 (500자 이상)",
    "key_issues": ["이슈1", "이슈2", "이슈3"]
  }},
  "hypotheses": [
    {{"id": "H1", "statement": "가설 내용", "confidence": "HIGH/MEDIUM/LOW", "evidence": "근거 요약"}},
    {{"id": "H2", "statement": "...", "confidence": "...", "evidence": "..."}},
    {{"id": "H3", "statement": "...", "confidence": "...", "evidence": "..."}}
  ],
  "strategy_options": [
    {{
      "id": "S1",
      "name": "전략명",
      "description": "전략 설명 (200자 이상)",
      "pros": ["장점1", "장점2"],
      "cons": ["단점1", "단점2"],
      "required_resources": "필요 자원",
      "timeline": "예상 소요 기간"
    }},
    {{"id": "S2", ...}},
    {{"id": "S3", ...}}
  ],
  "recommended_strategy": {{
    "selected_option": "S1",
    "rationale": "선택 이유 (200자 이상)",
    "execution_plan": [
      {{"week": 1, "focus": "집중 영역", "actions": ["액션1", "액션2"], "deliverables": ["산출물1"]}},
      {{"week": 2, ...}},
      ...
    ]
  }},
  "kpis": [
    {{"metric": "지표명", "current": "현재값 또는 baseline", "target": "목표값", "measurement": "측정 방법", "frequency": "측정 주기"}},
    ...
  ],
  "risks": [
    {{"risk": "리스크 내용", "probability": "HIGH/MEDIUM/LOW", "impact": "HIGH/MEDIUM/LOW", "mitigation": "방어 전략", "early_warning": "조기 경보 신호"}},
    ...
  ],
  "evidence": {{
    "rulecard_ids": ["사용된 RuleCard ID 목록"],
    "evidence_summary": "근거 요약 (100자 이상)"
  }},
  "body_markdown": "## {spec.title}\\n\\n(위 내용을 통합한 마크다운 본문, {spec.min_chars}자 이상)",
  "confidence": "HIGH/MEDIUM/LOW"
}}
"""
    return base


def get_premium_user_prompt(
    section_id: str,
    saju_data: Dict[str, Any],
    rulecards_context: str,
    target_year: int,
    user_question: str = ""
) -> str:
    """섹션별 유저 프롬프트 생성"""
    
    spec = PREMIUM_SECTIONS.get(section_id)
    
    # 사주 정보 (비즈니스 프로파일로 표현)
    saju = saju_data.get("saju", saju_data)
    day_master = saju_data.get("day_master", "")
    day_master_element = saju_data.get("day_master_element", "")
    
    return f"""## 클라이언트 비즈니스 프로파일

### 의사결정자 특성 분석 데이터
- 핵심 역량 코드: {day_master} ({day_master_element})
- 분석 기준년도: {target_year}년

### 클라이언트 질문/관심사
{user_question or "종합적인 비즈니스 전략 수립"}

## 분석 근거 데이터 (RuleCard)
{rulecards_context}

---

위 데이터를 기반으로 **{spec.title if spec else section_id}** 섹션을 작성해주세요.

중요 체크리스트:
✅ 명리학/사주 용어 사용 금지 (비즈니스 용어만 사용)
✅ 최소 {spec.min_chars if spec else 3000}자 이상 작성
✅ 필수 요소 모두 포함: {', '.join(spec.required_elements) if spec else ''}
✅ 구체적 숫자, 날짜, 담당 포함
✅ 실행 가능한 액션 아이템
✅ 측정 가능한 KPI

반드시 JSON 형식으로만 응답하세요.
"""


# ============ 룰카드 분배 ============

def distribute_rulecards_premium(
    all_cards: List[Dict[str, Any]],
    section_id: str,
    max_cards: int = 60
) -> Tuple[str, List[str]]:
    """
    섹션 주제에 맞게 RuleCards 정교하게 분배
    비즈니스 의사결정 근거 형태로 변환
    """
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return "", []
    
    target_topics = spec.topics
    quota = min(spec.rulecard_quota, max_cards)
    
    # 1. 토픽 매칭 점수 계산
    scored_cards = []
    for card in all_cards:
        card_topic = card.get("topic", "").lower()
        card_tags = [t.lower() for t in card.get("tags", [])]
        
        score = 0
        for topic in target_topics:
            if topic.lower() in card_topic:
                score += 3
            if any(topic.lower() in tag for tag in card_tags):
                score += 2
        
        if score > 0:
            scored_cards.append((score, card))
    
    # 점수순 정렬 후 상위 선택
    scored_cards.sort(key=lambda x: x[0], reverse=True)
    selected = [card for _, card in scored_cards[:quota]]
    
    # 부족하면 나머지에서 채우기
    if len(selected) < quota:
        used_ids = {c.get("id", "") for c in selected}
        for card in all_cards:
            if card.get("id", "") not in used_ids:
                selected.append(card)
                if len(selected) >= quota:
                    break
    
    # 2. 비즈니스 근거 형태로 변환
    context_lines = []
    card_ids = []
    
    for card in selected:
        card_id = card.get("id", card.get("_id", f"card_{len(card_ids)}"))
        card_ids.append(card_id)
        
        # 비즈니스 프레임으로 재해석
        topic = card.get("topic", "")
        mechanism = sanitize_for_business(card.get("mechanism", "")[:150])
        action = sanitize_for_business(card.get("action", "")[:150])
        
        line = f"[{card_id}] 분석 영역: {topic}"
        if mechanism:
            line += f"\n  → 비즈니스 시사점: {mechanism}"
        if action:
            line += f"\n  → 권장 액션: {action}"
        
        context_lines.append(line)
    
    context_str = "\n".join(context_lines) if context_lines else "분석 데이터 없음"
    
    return context_str, card_ids


# ============ 분량 검증 + 확장 ============

@dataclass
class ValidationResult:
    is_valid: bool
    char_count: int
    missing_elements: List[str]
    forbidden_terms_found: List[str]
    needs_expansion: bool


def validate_section_output(
    content: Dict[str, Any],
    section_id: str
) -> ValidationResult:
    """섹션 출력 검증: 분량, 필수 요소, 금칙어"""
    
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return ValidationResult(True, 0, [], [], False)
    
    # 1. 분량 체크
    body_md = content.get("body_markdown", "")
    char_count = len(body_md)
    
    # 2. 필수 요소 체크
    missing_elements = []
    
    # diagnosis 체크
    if not content.get("diagnosis", {}).get("current_state"):
        missing_elements.append("현상 진단")
    
    # hypotheses 체크
    hypotheses = content.get("hypotheses", [])
    if len(hypotheses) < 3:
        missing_elements.append(f"핵심 가설 ({len(hypotheses)}/3개)")
    
    # strategy_options 체크
    options = content.get("strategy_options", [])
    if len(options) < 3:
        missing_elements.append(f"전략 옵션 ({len(options)}/3개)")
    
    # recommended_strategy 체크
    if not content.get("recommended_strategy", {}).get("execution_plan"):
        missing_elements.append("추천 전략 + 실행 계획")
    
    # kpis 체크
    kpis = content.get("kpis", [])
    if len(kpis) < 3:
        missing_elements.append(f"KPI ({len(kpis)}/3개)")
    
    # risks 체크
    risks = content.get("risks", [])
    if len(risks) < 2:
        missing_elements.append(f"리스크 분석 ({len(risks)}/2개)")
    
    # 3. 금칙어 체크
    is_clean, forbidden = validate_no_forbidden_terms(body_md)
    
    # 4. 종합 판정
    is_valid = (
        char_count >= spec.min_chars and
        len(missing_elements) == 0 and
        is_clean
    )
    
    needs_expansion = char_count < spec.min_chars or len(missing_elements) > 0
    
    return ValidationResult(
        is_valid=is_valid,
        char_count=char_count,
        missing_elements=missing_elements,
        forbidden_terms_found=forbidden,
        needs_expansion=needs_expansion
    )


def get_expansion_prompt(
    section_id: str,
    current_content: Dict[str, Any],
    validation: ValidationResult,
    target_year: int
) -> str:
    """분량/요소 부족 시 확장 프롬프트"""
    
    spec = PREMIUM_SECTIONS.get(section_id)
    
    return f"""이전 응답이 분량/요소 기준을 충족하지 않습니다.

## 부족 사항
- 현재 분량: {validation.char_count}자 (최소 {spec.min_chars if spec else 3000}자 필요)
- 누락된 필수 요소: {', '.join(validation.missing_elements) if validation.missing_elements else '없음'}
- 발견된 금칙어: {', '.join(validation.forbidden_terms_found) if validation.forbidden_terms_found else '없음'}

## 기존 내용
{json.dumps(current_content, ensure_ascii=False, indent=2)[:3000]}

## 확장 요청
위 내용을 보완하여 다시 작성해주세요:
1. 분량을 {spec.min_chars if spec else 3000}자 이상으로 확장
2. 누락된 요소 추가: {', '.join(validation.missing_elements)}
3. 금칙어를 비즈니스 용어로 치환
4. 더 구체적인 숫자, 날짜, 액션 포함

동일한 JSON 구조로 응답하세요.
"""


# ============ Polish Pass ============

def polish_section(content: Dict[str, Any]) -> Dict[str, Any]:
    """섹션 후처리: 문체 통일, 금칙어 제거"""
    
    # body_markdown 치환
    if "body_markdown" in content:
        content["body_markdown"] = sanitize_for_business(content["body_markdown"])
    
    # diagnosis 치환
    if "diagnosis" in content and isinstance(content["diagnosis"], dict):
        if "current_state" in content["diagnosis"]:
            content["diagnosis"]["current_state"] = sanitize_for_business(
                content["diagnosis"]["current_state"]
            )
    
    # hypotheses 치환
    if "hypotheses" in content:
        for h in content["hypotheses"]:
            if isinstance(h, dict):
                h["statement"] = sanitize_for_business(h.get("statement", ""))
                h["evidence"] = sanitize_for_business(h.get("evidence", ""))
    
    # strategy_options 치환
    if "strategy_options" in content:
        for s in content["strategy_options"]:
            if isinstance(s, dict):
                s["description"] = sanitize_for_business(s.get("description", ""))
    
    # recommended_strategy 치환
    if "recommended_strategy" in content and isinstance(content["recommended_strategy"], dict):
        content["recommended_strategy"]["rationale"] = sanitize_for_business(
            content["recommended_strategy"].get("rationale", "")
        )
    
    # risks 치환
    if "risks" in content:
        for r in content["risks"]:
            if isinstance(r, dict):
                r["risk"] = sanitize_for_business(r.get("risk", ""))
                r["mitigation"] = sanitize_for_business(r.get("mitigation", ""))
    
    return content


# ============ 메인 빌더 ============

class PremiumReportBuilder:
    """99,000원 프리미엄 리포트 빌더"""
    
    def __init__(self):
        self._client = None
        self._semaphore = None
    
    def _get_client(self) -> AsyncOpenAI:
        settings = get_settings()
        api_key = get_openai_api_key()
        return AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(float(settings.report_section_timeout), connect=15.0),
            max_retries=0
        )
    
    async def build_premium_report(
        self,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        target_year: int = 2026,
        user_question: str = "",
        name: str = "고객",
        mode: str = "premium"
    ) -> Dict[str, Any]:
        """
        7개 섹션 병렬 생성 + 합성 + Polish
        """
        settings = get_settings()
        start_time = time.time()
        
        # 동시성 제한 (2~3개)
        self._semaphore = asyncio.Semaphore(settings.report_max_concurrency)
        self._client = self._get_client()
        
        logger.info(f"[PremiumReport] 시작 | Year={target_year} | Cards={len(rulecards)} | Mode={mode}")
        
        # 섹션 생성 태스크
        section_ids = list(PREMIUM_SECTIONS.keys())
        tasks = [
            self._generate_section_with_expansion(
                section_id=sid,
                saju_data=saju_data,
                rulecards=rulecards,
                target_year=target_year,
                user_question=user_question
            )
            for sid in section_ids
        ]
        
        # 병렬 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 수집
        sections = []
        total_rulecards = 0
        errors = []
        
        for sid, result in zip(section_ids, results):
            if isinstance(result, Exception):
                logger.error(f"[PremiumReport] 섹션 실패: {sid} | {str(result)[:100]}")
                errors.append({"section": sid, "error": str(result)[:200]})
                sections.append(self._create_error_section(sid, target_year))
            else:
                # Polish Pass 적용
                polished = polish_section(result["content"])
                
                sections.append({
                    "id": sid,
                    "title": PREMIUM_SECTIONS[sid].title,
                    "confidence": polished.get("confidence", "MEDIUM"),
                    "rulecard_ids": result.get("rulecard_ids", []),
                    "body_markdown": polished.get("body_markdown", ""),
                    "diagnosis": polished.get("diagnosis", {}),
                    "hypotheses": polished.get("hypotheses", []),
                    "strategy_options": polished.get("strategy_options", []),
                    "recommended_strategy": polished.get("recommended_strategy", {}),
                    "kpis": polished.get("kpis", []),
                    "risks": polished.get("risks", []),
                    "evidence": polished.get("evidence", {}),
                    "char_count": result.get("char_count", 0),
                    "latency_ms": result.get("latency_ms", 0)
                })
                total_rulecards += len(result.get("rulecard_ids", []))
        
        total_latency = int((time.time() - start_time) * 1000)
        
        # 전체 토큰 추정
        total_chars = sum(s.get("char_count", 0) for s in sections)
        total_tokens_estimate = int(total_chars / 2)  # 한글 기준 대략
        
        # 최종 보고서
        report = {
            "target_year": target_year,
            "sections": sections,
            "meta": {
                "total_tokens_estimate": total_tokens_estimate,
                "total_chars": total_chars,
                "mode": "premium_business_30p",
                "generated_at": datetime.now().isoformat(),
                "llm_model": settings.openai_model,
                "section_count": len(sections),
                "rulecards_used_total": total_rulecards,
                "latency_ms": total_latency,
                "errors": errors if errors else None
            },
            # 레거시 호환
            "legacy": self._create_legacy_compat(sections, target_year, name)
        }
        
        logger.info(
            f"[PremiumReport] 완료 | Sections={len(sections)} | "
            f"Chars={total_chars} | Latency={total_latency}ms | Errors={len(errors)}"
        )
        
        return report
    
    async def _generate_section_with_expansion(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        target_year: int,
        user_question: str,
        max_expansions: int = 2
    ) -> Dict[str, Any]:
        """섹션 생성 + 자동 확장 루프"""
        
        async with self._semaphore:
            start_time = time.time()
            settings = get_settings()
            
            # 룰카드 분배
            rulecards_context, rulecard_ids = distribute_rulecards_premium(
                rulecards,
                section_id,
                settings.report_section_max_rulecards
            )
            
            # 프롬프트 생성
            system_prompt = get_premium_system_prompt(section_id, target_year)
            user_prompt = get_premium_user_prompt(
                section_id, saju_data, rulecards_context, target_year, user_question
            )
            
            logger.info(f"[Section:{section_id}] 시작 | Cards={len(rulecard_ids)}")
            
            content = None
            expansion_count = 0
            
            while expansion_count <= max_expansions:
                try:
                    # GPT 호출
                    if expansion_count == 0:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    else:
                        # 확장 요청
                        validation = validate_section_output(content, section_id)
                        expansion_prompt = get_expansion_prompt(
                            section_id, content, validation, target_year
                        )
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": expansion_prompt}
                        ]
                    
                    response = await self._client.chat.completions.create(
                        model=settings.openai_model,
                        messages=messages,
                        max_tokens=settings.report_section_max_output_tokens,
                        temperature=0.3,
                        response_format={"type": "json_object"}
                    )
                    
                    content_str = response.choices[0].message.content
                    content = self._parse_json(content_str)
                    
                    if not content:
                        raise ValueError("JSON 파싱 실패")
                    
                    # 검증
                    validation = validate_section_output(content, section_id)
                    
                    if validation.is_valid:
                        logger.info(
                            f"[Section:{section_id}] 검증 통과 | "
                            f"Chars={validation.char_count} | Expansions={expansion_count}"
                        )
                        break
                    
                    if not validation.needs_expansion or expansion_count >= max_expansions:
                        logger.warning(
                            f"[Section:{section_id}] 최대 확장 도달 | "
                            f"Chars={validation.char_count} | Missing={validation.missing_elements}"
                        )
                        break
                    
                    logger.info(
                        f"[Section:{section_id}] 확장 필요 | "
                        f"Chars={validation.char_count} | Missing={validation.missing_elements}"
                    )
                    expansion_count += 1
                    
                except Exception as e:
                    logger.error(f"[Section:{section_id}] 에러: {str(e)[:100]}")
                    if expansion_count >= max_expansions:
                        raise
                    expansion_count += 1
            
            latency_ms = int((time.time() - start_time) * 1000)
            char_count = len(content.get("body_markdown", "")) if content else 0
            
            logger.info(f"[Section:{section_id}] 완료 | Chars={char_count} | Latency={latency_ms}ms")
            
            return {
                "content": content,
                "rulecard_ids": rulecard_ids,
                "char_count": char_count,
                "latency_ms": latency_ms
            }
    
    def _create_error_section(self, section_id: str, target_year: int) -> Dict[str, Any]:
        """에러 발생 시 폴백 섹션"""
        spec = PREMIUM_SECTIONS.get(section_id)
        return {
            "id": section_id,
            "title": spec.title if spec else section_id,
            "confidence": "LOW",
            "rulecard_ids": [],
            "body_markdown": f"## {spec.title if spec else section_id}\n\n"
                           f"{target_year}년 분석 데이터 처리 중 일시적 오류가 발생했습니다.\n"
                           f"잠시 후 다시 시도해주세요.",
            "diagnosis": {"current_state": "데이터 처리 오류", "key_issues": []},
            "hypotheses": [],
            "strategy_options": [],
            "recommended_strategy": {},
            "kpis": [],
            "risks": [],
            "evidence": {"rulecard_ids": [], "evidence_summary": ""},
            "char_count": 0,
            "latency_ms": 0,
            "error": True
        }
    
    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        """JSON 파싱"""
        if not content:
            return None
        
        text = content.strip()
        
        # 코드블록 제거
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
            lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
            text = "\n".join(lines)
        
        try:
            return json.loads(text)
        except:
            pass
        
        # JSON 부분 추출
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        
        return None
    
    def _create_legacy_compat(
        self,
        sections: List[Dict[str, Any]],
        target_year: int,
        name: str
    ) -> Dict[str, Any]:
        """레거시 프론트엔드 호환용 필드"""
        
        exec_section = next((s for s in sections if s["id"] == "exec"), {})
        money_section = next((s for s in sections if s["id"] == "money"), {})
        
        # 강점 추출
        strengths = []
        for h in exec_section.get("hypotheses", []):
            if h.get("confidence") == "HIGH":
                strengths.append(h.get("statement", ""))
        
        # 리스크 추출
        risks = []
        for r in exec_section.get("risks", [])[:3]:
            risks.append(r.get("risk", ""))
        
        # 액션 플랜
        action_plan = []
        rec = exec_section.get("recommended_strategy", {})
        for step in rec.get("execution_plan", [])[:5]:
            if step.get("actions"):
                action_plan.extend(step["actions"][:2])
        
        return {
            "success": True,
            "summary": f"{target_year}년 프리미엄 비즈니스 컨설팅 보고서",
            "day_master_analysis": exec_section.get("diagnosis", {}).get("current_state", ""),
            "strengths": strengths[:5],
            "risks": risks,
            "answer": exec_section.get("body_markdown", "")[:1000],
            "action_plan": action_plan[:5],
            "lucky_periods": [],
            "caution_periods": [],
            "lucky_elements": {},
            "blessing": f"{name}님의 {target_year}년 성공을 응원합니다!",
            "disclaimer": "본 보고서는 데이터 기반 분석 참고 자료이며, 전문적 조언을 대체하지 않습니다."
        }


# 싱글톤 인스턴스
premium_report_builder = PremiumReportBuilder()


# 기존 호환용 alias
report_builder = premium_report_builder
