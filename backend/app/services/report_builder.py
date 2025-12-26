"""
SajuOS Premium Report Builder v5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 핵심 수정: 전역 Top-100 RuleCards 먼저 선별 → 섹션 분배
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1) 룰카드 선택 엔진: 전체 풀에서 Top-100 전역 선택 → 섹션별 분배
2) JSON Schema 강제: response_format + json_schema(strict=True)
3) 안정성: Semaphore(1), exponential backoff + jitter, 재시도 3회
"""
import asyncio
import logging
import time
import json
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError, APITimeoutError
import httpx

from app.config import get_settings
from app.services.openai_key import get_openai_api_key
from app.services.terminology_mapper import (
    sanitize_for_business,
    get_business_prompt_rules,
)

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 사업가형 핵심 태그 50개
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BUSINESS_OWNER_CORE_TAGS = [
    # 재물/현금흐름 (15개)
    "정재", "편재", "재성", "재물", "부", "현금", "매출", "수익", "투자", 
    "자산", "유동성", "손실", "파산", "횡재", "도둑",
    # 사업/커리어 (15개)
    "정관", "편관", "관성", "직장", "사업", "창업", "경영", "리더십", 
    "승진", "이직", "독립", "프리랜서", "계약", "거래", "파트너",
    # 실행력/생산성 (10개)
    "식신", "상관", "식상", "실행", "생산", "창작", "마케팅", "혁신", 
    "출력", "성과",
    # 인맥/관계 (5개)
    "비겁", "비견", "겁재", "동업", "경쟁",
    # 지식/브랜드 (5개)
    "인성", "정인", "편인", "학습", "브랜드"
]

# 섹션별 가중치 태그
SECTION_WEIGHT_TAGS: Dict[str, List[str]] = {
    "exec": ["전체운", "종합", "핵심", "요약", "일간", "성향"],
    "money": ["정재", "편재", "재성", "재물", "현금", "매출", "투자", "손실"],
    "business": ["정관", "편관", "사업", "창업", "경영", "리더십", "계약", "거래"],
    "team": ["비겁", "비견", "겁재", "동업", "파트너", "직원", "관계", "협력"],
    "health": ["건강", "에너지", "스트레스", "번아웃", "체력", "질병", "휴식"],
    "calendar": ["월운", "시기", "계절", "타이밍", "길일", "흉일", "절기"],
    "sprint": ["실행", "액션", "계획", "목표", "KPI", "마일스톤", "주간"]
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 섹션 정의
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionSpec:
    id: str
    title: str
    pages: int
    max_cards: int  # 이 섹션에 할당할 최대 카드 수 (from Top-100)
    min_chars: int
    validation_type: str = "standard"


PREMIUM_SECTIONS: Dict[str, SectionSpec] = {
    "exec": SectionSpec(id="exec", title="Executive Summary", pages=2, max_cards=15, min_chars=1500, validation_type="standard"),
    "money": SectionSpec(id="money", title="Money & Cashflow", pages=5, max_cards=18, min_chars=2500, validation_type="standard"),
    "business": SectionSpec(id="business", title="Business Strategy", pages=5, max_cards=18, min_chars=2500, validation_type="standard"),
    "team": SectionSpec(id="team", title="Team & Partner Risk", pages=4, max_cards=15, min_chars=2000, validation_type="standard"),
    "health": SectionSpec(id="health", title="Health & Performance", pages=3, max_cards=12, min_chars=1500, validation_type="standard"),
    "calendar": SectionSpec(id="calendar", title="12-Month Calendar", pages=6, max_cards=12, min_chars=2500, validation_type="calendar"),
    "sprint": SectionSpec(id="sprint", title="90-Day Sprint Plan", pages=5, max_cards=10, min_chars=2000, validation_type="sprint")
}

# 합계 = 15+18+18+15+12+12+10 = 100 (정확히 100장)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. JSON Schema (Structured Outputs)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STANDARD_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "standard_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "diagnosis": {
                    "type": "object",
                    "properties": {
                        "current_state": {"type": "string"},
                        "key_issues": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["current_state", "key_issues"],
                    "additionalProperties": False
                },
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "statement": {"type": "string"},
                            "confidence": {"type": "string"},
                            "evidence": {"type": "string"}
                        },
                        "required": ["id", "statement", "confidence", "evidence"],
                        "additionalProperties": False
                    }
                },
                "strategy_options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "pros": {"type": "array", "items": {"type": "string"}},
                            "cons": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["id", "name", "description", "pros", "cons"],
                        "additionalProperties": False
                    }
                },
                "recommended_strategy": {
                    "type": "object",
                    "properties": {
                        "selected_option": {"type": "string"},
                        "rationale": {"type": "string"},
                        "execution_plan": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "week": {"type": "integer"},
                                    "focus": {"type": "string"},
                                    "actions": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["week", "focus", "actions"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["selected_option", "rationale", "execution_plan"],
                    "additionalProperties": False
                },
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "target": {"type": "string"},
                            "measurement": {"type": "string"}
                        },
                        "required": ["metric", "target", "measurement"],
                        "additionalProperties": False
                    }
                },
                "risks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "risk": {"type": "string"},
                            "probability": {"type": "string"},
                            "impact": {"type": "string"},
                            "mitigation": {"type": "string"}
                        },
                        "required": ["risk", "probability", "impact", "mitigation"],
                        "additionalProperties": False
                    }
                },
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "diagnosis", "hypotheses", "strategy_options", 
                        "recommended_strategy", "kpis", "risks", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}

SPRINT_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sprint_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "mission_statement": {"type": "string"},
                "weekly_plans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "week": {"type": "integer"},
                            "theme": {"type": "string"},
                            "goals": {"type": "array", "items": {"type": "string"}},
                            "daily_actions": {"type": "array", "items": {"type": "string"}},
                            "kpis": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["week", "theme", "goals", "daily_actions", "kpis"],
                        "additionalProperties": False
                    }
                },
                "milestones": {
                    "type": "object",
                    "properties": {
                        "day_30": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "success_criteria": {"type": "string"},
                                "deliverables": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["goal", "success_criteria", "deliverables"],
                            "additionalProperties": False
                        },
                        "day_60": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "success_criteria": {"type": "string"},
                                "deliverables": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["goal", "success_criteria", "deliverables"],
                            "additionalProperties": False
                        },
                        "day_90": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "success_criteria": {"type": "string"},
                                "deliverables": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["goal", "success_criteria", "deliverables"],
                            "additionalProperties": False
                        }
                    },
                    "required": ["day_30", "day_60", "day_90"],
                    "additionalProperties": False
                },
                "risk_scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scenario": {"type": "string"},
                            "trigger": {"type": "string"},
                            "pivot_plan": {"type": "string"}
                        },
                        "required": ["scenario", "trigger", "pivot_plan"],
                        "additionalProperties": False
                    }
                },
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "mission_statement", "weekly_plans", "milestones", 
                        "risk_scenarios", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}

CALENDAR_SECTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "calendar_section",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "annual_theme": {"type": "string"},
                "monthly_plans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "month": {"type": "integer"},
                            "month_name": {"type": "string"},
                            "theme": {"type": "string"},
                            "energy_level": {"type": "string"},
                            "key_focus": {"type": "string"},
                            "recommended_actions": {"type": "array", "items": {"type": "string"}},
                            "cautions": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["month", "month_name", "theme", "energy_level", 
                                    "key_focus", "recommended_actions", "cautions"],
                        "additionalProperties": False
                    }
                },
                "quarterly_milestones": {
                    "type": "object",
                    "properties": {
                        "Q1": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "key_metric": {"type": "string"}}, "required": ["theme", "milestone", "key_metric"], "additionalProperties": False},
                        "Q2": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "key_metric": {"type": "string"}}, "required": ["theme", "milestone", "key_metric"], "additionalProperties": False},
                        "Q3": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "key_metric": {"type": "string"}}, "required": ["theme", "milestone", "key_metric"], "additionalProperties": False},
                        "Q4": {"type": "object", "properties": {"theme": {"type": "string"}, "milestone": {"type": "string"}, "key_metric": {"type": "string"}}, "required": ["theme", "milestone", "key_metric"], "additionalProperties": False}
                    },
                    "required": ["Q1", "Q2", "Q3", "Q4"],
                    "additionalProperties": False
                },
                "peak_months": {"type": "array", "items": {"type": "string"}},
                "risk_months": {"type": "array", "items": {"type": "string"}},
                "body_markdown": {"type": "string"},
                "confidence": {"type": "string"}
            },
            "required": ["title", "annual_theme", "monthly_plans", "quarterly_milestones",
                        "peak_months", "risk_months", "body_markdown", "confidence"],
            "additionalProperties": False
        }
    }
}


def get_section_schema(section_id: str) -> dict:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        return STANDARD_SECTION_SCHEMA
    if spec.validation_type == "sprint":
        return SPRINT_SECTION_SCHEMA
    elif spec.validation_type == "calendar":
        return CALENDAR_SECTION_SCHEMA
    return STANDARD_SECTION_SCHEMA


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 🔥 전역 Top-100 RuleCard 선별 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class GlobalRuleCardSelection:
    """전역 Top-100 선별 결과"""
    original_pool_count: int  # 원본 풀 크기 (예: 480)
    top100_count: int  # Top-100 선별 크기 (정확히 100 또는 미만)
    top100_cards: List[Dict[str, Any]]  # Top-100 카드 리스트
    top100_card_ids: List[str]  # Top-100 카드 ID 리스트


def score_rulecard_global(
    card: Dict[str, Any],
    feature_tags: List[str]
) -> float:
    """전역 RuleCard 점수화 (섹션 무관)"""
    score = 0.0
    
    card_topic = (card.get("topic", "") or "").lower()
    card_tags = [t.lower() for t in card.get("tags", [])]
    card_text = f"{card_topic} {' '.join(card_tags)} {card.get('mechanism', '')} {card.get('action', '')}"
    card_text_lower = card_text.lower()
    
    # 1. featureTags 매칭 (최대 30점)
    for ft in feature_tags:
        if ft.lower() in card_text_lower:
            score += 3.0
    
    # 2. 사업가형 핵심 태그 50개 매칭 (최대 50점)
    for core_tag in BUSINESS_OWNER_CORE_TAGS:
        if core_tag.lower() in card_text_lower:
            score += 1.0
    
    return score


def select_global_top100(
    all_cards: List[Dict[str, Any]],
    feature_tags: List[str],
    top_limit: int = 100
) -> GlobalRuleCardSelection:
    """
    🔥 전체 RuleCard 풀에서 Top-100만 전역 선별
    """
    original_pool = len(all_cards)
    
    if original_pool == 0:
        return GlobalRuleCardSelection(
            original_pool_count=0,
            top100_count=0,
            top100_cards=[],
            top100_card_ids=[]
        )
    
    # 1. 전체 카드 점수화
    scored = []
    for card in all_cards:
        score = score_rulecard_global(card, feature_tags)
        scored.append((score, card))
    
    # 2. 점수순 정렬 → Top-100
    scored.sort(key=lambda x: x[0], reverse=True)
    top100 = [card for _, card in scored[:top_limit]]
    
    # 3. ID 추출
    top100_ids = []
    for card in top100:
        cid = card.get("id", card.get("_id", f"card_{len(top100_ids)}"))
        top100_ids.append(cid)
    
    logger.info(
        f"[GlobalTop100] 전역 선별 완료 | "
        f"Original Pool={original_pool} | Top100={len(top100)} | "
        f"FeatureTags={len(feature_tags)}"
    )
    
    return GlobalRuleCardSelection(
        original_pool_count=original_pool,
        top100_count=len(top100),
        top100_cards=top100,
        top100_card_ids=top100_ids
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 섹션별 RuleCard 분배 (Top-100에서)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class SectionRuleCardAllocation:
    """섹션별 룰카드 할당 결과"""
    section_id: str
    allocated_count: int
    allocated_card_ids: List[str]
    context_text: str


def allocate_rulecards_to_section(
    top100_cards: List[Dict[str, Any]],
    section_id: str,
    max_cards: int,
    already_used_ids: set
) -> SectionRuleCardAllocation:
    """
    Top-100에서 섹션에 할당 (중복 방지)
    """
    spec = PREMIUM_SECTIONS.get(section_id)
    section_tags = SECTION_WEIGHT_TAGS.get(section_id, [])
    
    # 섹션 관련도 점수 계산
    scored = []
    for card in top100_cards:
        cid = card.get("id", card.get("_id", ""))
        if cid in already_used_ids:
            continue  # 이미 사용된 카드 제외
        
        card_text = f"{card.get('topic', '')} {card.get('mechanism', '')} {card.get('action', '')}"
        card_text_lower = card_text.lower()
        
        section_score = 0
        for st in section_tags:
            if st.lower() in card_text_lower:
                section_score += 2.0
        
        scored.append((section_score, card))
    
    # 섹션 관련도 순 정렬
    scored.sort(key=lambda x: x[0], reverse=True)
    allocated = [card for _, card in scored[:max_cards]]
    
    # 컨텍스트 텍스트 생성
    lines = []
    ids = []
    for card in allocated:
        cid = card.get("id", card.get("_id", f"card_{len(ids)}"))
        ids.append(cid)
        
        topic = card.get("topic", "")
        mechanism = sanitize_for_business((card.get("mechanism") or "")[:100])
        action = sanitize_for_business((card.get("action") or "")[:100])
        
        line = f"[{cid}] {topic}"
        if mechanism:
            line += f" → {mechanism}"
        if action:
            line += f" | 액션: {action}"
        lines.append(line)
    
    context = "\n".join(lines) if lines else "분석 데이터 없음"
    
    return SectionRuleCardAllocation(
        section_id=section_id,
        allocated_count=len(ids),
        allocated_card_ids=ids,
        context_text=context
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. 프롬프트 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_section_system_prompt(section_id: str, target_year: int) -> str:
    spec = PREMIUM_SECTIONS.get(section_id)
    if not spec:
        spec = PREMIUM_SECTIONS["exec"]
    
    terminology_rules = get_business_prompt_rules()
    
    return f"""당신은 99,000원 프리미엄 비즈니스 컨설팅 보고서를 작성하는 시니어 전략 컨설턴트입니다.

## 분석 기준년도: {target_year}년

## 핵심 원칙
1. 사주 풀이가 아닌 '경영 전략 보고서' 스타일로 작성
2. 제공된 RuleCard 데이터를 근거로 가설과 전략 도출
3. 구체적 일정, 숫자, KPI 포함
4. 최소 {spec.min_chars}자 이상 작성

{terminology_rules}

## 이 섹션: {spec.title}
JSON 스키마에 맞춰 정확히 응답하세요."""


def get_section_user_prompt(
    section_id: str,
    saju_data: Dict[str, Any],
    allocation: SectionRuleCardAllocation,
    target_year: int,
    user_question: str = ""
) -> str:
    spec = PREMIUM_SECTIONS.get(section_id)
    day_master = saju_data.get("day_master", "")
    day_master_element = saju_data.get("day_master_element", "")
    
    return f"""## 클라이언트 프로파일
- 핵심 역량 코드: {day_master} ({day_master_element})
- 분석 기준년도: {target_year}년
- 질문: {user_question or "종합적인 비즈니스 전략 수립"}

## 분석 근거 RuleCards ({allocation.allocated_count}장)
{allocation.context_text}

---
위 데이터를 기반으로 **{spec.title if spec else section_id}** 섹션을 작성하세요.
- 최소 {spec.min_chars if spec else 2000}자 이상
- 명리학 용어 금지, 비즈니스 용어만 사용
- JSON 스키마에 정확히 맞춰 응답"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. 메인 빌더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PremiumReportBuilder:
    """99,000원 프리미엄 리포트 빌더 v5"""
    
    def __init__(self):
        self._client = None
        self._semaphore = None
    
    def _get_client(self) -> AsyncOpenAI:
        settings = get_settings()
        api_key = get_openai_api_key()
        return AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(90.0, connect=15.0),
            max_retries=0
        )
    
    async def _call_with_retry(
        self,
        messages: List[Dict[str, str]],
        section_id: str,
        response_format: dict,
        max_retries: int = 3,
        base_delay: float = 2.0
    ) -> Dict[str, Any]:
        """JSON Schema 강제 + Retry + Exponential Backoff + Jitter"""
        settings = get_settings()
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[Section:{section_id}] OpenAI 호출 {attempt + 1}/{max_retries}")
                
                response = await self._client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.3,
                    response_format=response_format
                )
                
                content_str = response.choices[0].message.content
                if not content_str:
                    raise ValueError("빈 응답")
                
                content = json.loads(content_str)
                logger.info(f"[Section:{section_id}] 성공 | 응답: {len(content_str)}자")
                return content
                
            except RateLimitError as e:
                last_error = e
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"[Section:{section_id}] 429 Rate Limit | Wait {delay:.1f}s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    
            except (APIError, APIConnectionError, APITimeoutError) as e:
                last_error = e
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"[Section:{section_id}] API Error | Wait {delay:.1f}s | {str(e)[:100]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    
            except json.JSONDecodeError as e:
                last_error = e
                delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"[Section:{section_id}] JSON Parse Error | Wait {delay:.1f}s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = e
                logger.error(f"[Section:{section_id}] 예상치 못한 에러: {type(e).__name__}: {str(e)[:200]}")
                raise
        
        raise last_error or Exception("Unknown error after retries")
    
    async def build_premium_report(
        self,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        feature_tags: List[str] = None,
        target_year: int = 2026,
        user_question: str = "",
        name: str = "고객",
        mode: str = "premium"
    ) -> Dict[str, Any]:
        """7개 섹션 순차 생성 (Semaphore=1, 안정성 최우선)"""
        settings = get_settings()
        start_time = time.time()
        
        # Semaphore: 1 (완전 순차 처리로 안정성 확보)
        self._semaphore = asyncio.Semaphore(1)
        self._client = self._get_client()
        
        if not feature_tags:
            feature_tags = []
        
        # ═══════════════════════════════════════════════════
        # 🔥 핵심: 전역 Top-100 RuleCards 먼저 선별
        # ═══════════════════════════════════════════════════
        global_selection = select_global_top100(rulecards, feature_tags, top_limit=100)
        
        logger.info(
            f"[PremiumReport] ========== 시작 ==========\n"
            f"  Year={target_year} | Original Pool={global_selection.original_pool_count}\n"
            f"  🔥 Top-100 선별={global_selection.top100_count} | FeatureTags={len(feature_tags)}"
        )
        
        # 섹션별 RuleCard 분배 (Top-100에서만)
        section_ids = list(PREMIUM_SECTIONS.keys())
        allocations: Dict[str, SectionRuleCardAllocation] = {}
        used_card_ids = set()
        
        for sid in section_ids:
            spec = PREMIUM_SECTIONS[sid]
            alloc = allocate_rulecards_to_section(
                top100_cards=global_selection.top100_cards,
                section_id=sid,
                max_cards=spec.max_cards,
                already_used_ids=used_card_ids
            )
            allocations[sid] = alloc
            used_card_ids.update(alloc.allocated_card_ids)
            
            logger.info(f"[Allocation] {sid}: {alloc.allocated_count}장 할당")
        
        # 섹션 생성 태스크
        tasks = [
            self._generate_section(
                section_id=sid,
                saju_data=saju_data,
                allocation=allocations[sid],
                target_year=target_year,
                user_question=user_question
            )
            for sid in section_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 수집
        sections = []
        errors = []
        rulecard_meta = {}
        total_allocated = 0
        
        for sid, result in zip(section_ids, results):
            alloc = allocations[sid]
            
            if isinstance(result, Exception):
                error_detail = {
                    "section": sid,
                    "error_type": type(result).__name__,
                    "error_message": str(result)[:500]
                }
                errors.append(error_detail)
                logger.error(f"[PremiumReport] ❌ 섹션 실패: {sid} | {type(result).__name__}: {str(result)[:200]}")
                sections.append(self._create_error_section(sid, target_year, str(result)[:200]))
            else:
                content = result["content"]
                polished = self._polish_section(content, sid)
                spec = PREMIUM_SECTIONS.get(sid)
                
                section_data = {
                    "id": sid,
                    "title": spec.title if spec else sid,
                    "confidence": polished.get("confidence", "MEDIUM"),
                    "rulecard_ids": alloc.allocated_card_ids,
                    "rulecard_selected": alloc.allocated_count,
                    "body_markdown": polished.get("body_markdown", ""),
                    "char_count": len(polished.get("body_markdown", "")),
                    "latency_ms": result.get("latency_ms", 0)
                }
                
                # 타입별 필드 추가
                if spec.validation_type == "sprint":
                    section_data.update({
                        "mission_statement": polished.get("mission_statement", ""),
                        "weekly_plans": polished.get("weekly_plans", []),
                        "milestones": polished.get("milestones", {}),
                        "risk_scenarios": polished.get("risk_scenarios", []),
                    })
                elif spec.validation_type == "calendar":
                    section_data.update({
                        "annual_theme": polished.get("annual_theme", ""),
                        "monthly_plans": polished.get("monthly_plans", []),
                        "quarterly_milestones": polished.get("quarterly_milestones", {}),
                        "peak_months": polished.get("peak_months", []),
                        "risk_months": polished.get("risk_months", []),
                    })
                else:
                    section_data.update({
                        "diagnosis": polished.get("diagnosis", {}),
                        "hypotheses": polished.get("hypotheses", []),
                        "strategy_options": polished.get("strategy_options", []),
                        "recommended_strategy": polished.get("recommended_strategy", {}),
                        "kpis": polished.get("kpis", []),
                        "risks": polished.get("risks", []),
                    })
                
                sections.append(section_data)
                logger.info(f"[PremiumReport] ✅ 섹션 성공: {sid} | Chars={section_data['char_count']}")
            
            # 섹션별 룰카드 메타
            rulecard_meta[sid] = {
                "selected_count": alloc.allocated_count,
                "selected_card_ids": alloc.allocated_card_ids
            }
            total_allocated += alloc.allocated_count
        
        total_latency = int((time.time() - start_time) * 1000)
        total_chars = sum(s.get("char_count", 0) for s in sections)
        
        report = {
            "target_year": target_year,
            "sections": sections,
            "meta": {
                "total_chars": total_chars,
                "mode": "premium_business_30p",
                "generated_at": datetime.now().isoformat(),
                "llm_model": settings.openai_model,
                "section_count": len(sections),
                "success_count": len(sections) - len(errors),
                "error_count": len(errors),
                "latency_ms": total_latency,
                # 🔥 핵심: 룰카드 메타 (100/480 형식)
                "rulecards_pool_total": global_selection.original_pool_count,
                "rulecards_top100_selected": global_selection.top100_count,
                "rulecards_used_total": total_allocated,
                "rulecards_by_section": rulecard_meta,
                "feature_tags_count": len(feature_tags),
                "errors": errors if errors else None
            },
            "legacy": self._create_legacy_compat(sections, target_year, name)
        }
        
        logger.info(
            f"[PremiumReport] ========== 완료 ==========\n"
            f"  Sections={len(sections)} | Success={len(sections) - len(errors)} | Errors={len(errors)}\n"
            f"  🔥 RuleCards={global_selection.top100_count}/{global_selection.original_pool_count} (Top-100)\n"
            f"  Chars={total_chars} | Latency={total_latency}ms"
        )
        
        return report
    
    async def _generate_section(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        allocation: SectionRuleCardAllocation,
        target_year: int,
        user_question: str
    ) -> Dict[str, Any]:
        """단일 섹션 생성"""
        async with self._semaphore:
            start_time = time.time()
            
            system_prompt = get_section_system_prompt(section_id, target_year)
            user_prompt = get_section_user_prompt(
                section_id, saju_data, allocation, target_year, user_question
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response_format = get_section_schema(section_id)
            
            logger.info(f"[Section:{section_id}] 시작 | RuleCards={allocation.allocated_count}장")
            
            content = await self._call_with_retry(
                messages=messages,
                section_id=section_id,
                response_format=response_format,
                max_retries=3,
                base_delay=2.0
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return {"content": content, "latency_ms": latency_ms}
    
    async def regenerate_single_section(
        self,
        section_id: str,
        saju_data: Dict[str, Any],
        rulecards: List[Dict[str, Any]],
        feature_tags: List[str] = None,
        target_year: int = 2026,
        user_question: str = ""
    ) -> Dict[str, Any]:
        """단일 섹션만 재생성 (오류 복구용)"""
        if section_id not in PREMIUM_SECTIONS:
            raise ValueError(f"Invalid section_id: {section_id}")
        
        self._semaphore = asyncio.Semaphore(1)
        self._client = self._get_client()
        
        if not feature_tags:
            feature_tags = []
        
        # Top-100 선별
        global_selection = select_global_top100(rulecards, feature_tags, top_limit=100)
        
        # 해당 섹션에 할당
        spec = PREMIUM_SECTIONS[section_id]
        allocation = allocate_rulecards_to_section(
            top100_cards=global_selection.top100_cards,
            section_id=section_id,
            max_cards=spec.max_cards,
            already_used_ids=set()
        )
        
        logger.info(f"[SingleSection] 재생성 시작: {section_id} | RuleCards={allocation.allocated_count}")
        
        try:
            result = await self._generate_section(
                section_id=section_id,
                saju_data=saju_data,
                allocation=allocation,
                target_year=target_year,
                user_question=user_question
            )
            
            content = result["content"]
            polished = self._polish_section(content, section_id)
            
            section_data = {
                "id": section_id,
                "title": spec.title,
                "confidence": polished.get("confidence", "MEDIUM"),
                "rulecard_ids": allocation.allocated_card_ids,
                "rulecard_selected": allocation.allocated_count,
                "body_markdown": polished.get("body_markdown", ""),
                "char_count": len(polished.get("body_markdown", "")),
                "latency_ms": result.get("latency_ms", 0),
                "regenerated": True
            }
            
            # 타입별 필드
            if spec.validation_type == "sprint":
                section_data.update({
                    "mission_statement": polished.get("mission_statement", ""),
                    "weekly_plans": polished.get("weekly_plans", []),
                    "milestones": polished.get("milestones", {}),
                    "risk_scenarios": polished.get("risk_scenarios", []),
                })
            elif spec.validation_type == "calendar":
                section_data.update({
                    "annual_theme": polished.get("annual_theme", ""),
                    "monthly_plans": polished.get("monthly_plans", []),
                    "quarterly_milestones": polished.get("quarterly_milestones", {}),
                })
            else:
                section_data.update({
                    "diagnosis": polished.get("diagnosis", {}),
                    "hypotheses": polished.get("hypotheses", []),
                    "strategy_options": polished.get("strategy_options", []),
                    "recommended_strategy": polished.get("recommended_strategy", {}),
                    "kpis": polished.get("kpis", []),
                    "risks": polished.get("risks", []),
                })
            
            logger.info(f"[SingleSection] 완료: {section_id} | Chars={section_data['char_count']}")
            
            return {"success": True, "section": section_data}
            
        except Exception as e:
            logger.error(f"[SingleSection] 실패: {section_id} | {str(e)[:200]}")
            return {
                "success": False,
                "section_id": section_id,
                "error": str(e)[:500],
                "error_type": type(e).__name__
            }
    
    def _polish_section(self, content: Dict[str, Any], section_id: str) -> Dict[str, Any]:
        """용어 치환"""
        if "body_markdown" in content:
            content["body_markdown"] = sanitize_for_business(content["body_markdown"])
        if "diagnosis" in content and isinstance(content["diagnosis"], dict):
            if "current_state" in content["diagnosis"]:
                content["diagnosis"]["current_state"] = sanitize_for_business(content["diagnosis"]["current_state"])
        if "mission_statement" in content:
            content["mission_statement"] = sanitize_for_business(content["mission_statement"])
        if "annual_theme" in content:
            content["annual_theme"] = sanitize_for_business(content["annual_theme"])
        return content
    
    def _create_error_section(self, section_id: str, target_year: int, error_msg: str = "") -> Dict[str, Any]:
        spec = PREMIUM_SECTIONS.get(section_id)
        return {
            "id": section_id,
            "title": spec.title if spec else section_id,
            "confidence": "LOW",
            "rulecard_ids": [],
            "rulecard_selected": 0,
            "body_markdown": f"## {spec.title if spec else section_id}\n\n"
                           f"{target_year}년 분석 중 오류가 발생했습니다.\n"
                           f"_Error: {error_msg[:100]}_",
            "char_count": 0,
            "latency_ms": 0,
            "error": True,
            "error_message": error_msg[:200]
        }
    
    def _create_legacy_compat(self, sections: List[Dict[str, Any]], target_year: int, name: str) -> Dict[str, Any]:
        exec_section = next((s for s in sections if s["id"] == "exec"), {})
        strengths = [h.get("statement", "") for h in exec_section.get("hypotheses", []) if h.get("confidence") == "HIGH"][:5]
        risks = [r.get("risk", "") for r in exec_section.get("risks", [])[:3]]
        return {
            "success": True,
            "summary": f"{target_year}년 프리미엄 비즈니스 컨설팅 보고서",
            "strengths": strengths,
            "risks": risks,
            "blessing": f"{name}님의 {target_year}년 성공을 응원합니다!",
            "disclaimer": "본 보고서는 데이터 기반 분석 참고 자료이며, 전문적 조언을 대체하지 않습니다."
        }


# 싱글톤
premium_report_builder = PremiumReportBuilder()
report_builder = premium_report_builder
