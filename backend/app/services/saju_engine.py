"""
사주 계산 엔진 (API 래퍼)
- engine_v2.py의 검증된 천문학 기반 엔진 사용
- API 응답 형식에 맞게 변환
"""
from typing import Optional
from dataclasses import dataclass

from app.models.schemas import Pillar, SajuWonGuk, DaeunInfo, QualityInfo
from app.services.engine_v2 import (
    ScientificSajuEngine, 
    scientific_engine, 
    CalculationError,
    EPHEM_AVAILABLE,
    GAN,
    JI,
    GAN_TO_ELEMENT,
    JI_TO_ELEMENT,
    DAY_MASTER_DESC
)


@dataclass
class CalculationResult:
    """계산 결과"""
    saju: SajuWonGuk
    day_master: str
    day_master_element: str
    day_master_description: str
    daeun: Optional[DaeunInfo]
    quality: QualityInfo


class SajuEngine:
    """
    사주 계산 엔진 (API 래퍼)
    - 내부적으로 engine_v2.py의 천문학 기반 엔진 사용
    """
    
    def __init__(self):
        if not EPHEM_AVAILABLE:
            raise ImportError(
                "ephem 라이브러리가 필요합니다.\n"
                "설치: pip install ephem"
            )
        self.engine = scientific_engine
    
    def calculate(
        self,
        year: int,
        month: int,
        day: int,
        hour: Optional[int] = None,
        minute: int = 0,
        gender: Optional[str] = None,
        timezone: str = "Asia/Seoul",
        use_solar_time: bool = True
    ) -> CalculationResult:
        """
        사주 계산 메인 함수
        
        Args:
            use_solar_time: 태양시 보정 (-30분) 적용 여부
        """
        
        # 천문학 엔진으로 계산
        result = self.engine.calculate(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            use_solar_time=use_solar_time
        )
        
        # Pillar 객체로 변환
        year_pillar = self._to_pillar(result["year_pillar"])
        month_pillar = self._to_pillar(result["month_pillar"])
        day_pillar = self._to_pillar(result["day_pillar"])
        hour_pillar = self._to_pillar(result["hour_pillar"]) if result["hour_pillar"] else None
        
        # SajuWonGuk 구성
        saju = SajuWonGuk(
            year_pillar=year_pillar,
            month_pillar=month_pillar,
            day_pillar=day_pillar,
            hour_pillar=hour_pillar
        )
        
        # 품질 정보
        meta = result["meta"]
        quality = QualityInfo(
            has_birth_time=hour is not None,
            solar_term_boundary=meta["is_boundary"],
            boundary_reason=meta["boundary_reason"],
            timezone=timezone,
            calculation_method=meta["calculation_method"]
        )
        
        # 대운 정보
        daeun = self._calc_daeun(
            year_gan_idx=result["year_pillar"]["gan_index"],
            gender=gender
        )
        
        return CalculationResult(
            saju=saju,
            day_master=result["day_master"],
            day_master_element=result["day_master_element"],
            day_master_description=result["day_master_description"],
            daeun=daeun,
            quality=quality
        )
    
    def _to_pillar(self, pillar_data: dict) -> Pillar:
        """딕셔너리 → Pillar 객체 변환"""
        return Pillar(
            gan=pillar_data["gan"],
            ji=pillar_data["ji"],
            ganji=pillar_data["ganji"],
            gan_element=pillar_data["gan_element"],
            ji_element=pillar_data["ji_element"],
            gan_index=pillar_data["gan_index"],
            ji_index=pillar_data["ji_index"]
        )
    
    def _calc_daeun(
        self,
        year_gan_idx: int,
        gender: Optional[str]
    ) -> Optional[DaeunInfo]:
        """대운 정보 계산"""
        if not gender:
            return None
        
        is_yang_year = year_gan_idx % 2 == 0
        is_male = gender.lower() in ["male", "남", "남성"]
        
        if (is_male and is_yang_year) or (not is_male and not is_yang_year):
            direction = "forward"
        else:
            direction = "backward"
        
        return DaeunInfo(
            start_age=3,
            direction=direction,
            current_daeun=None
        )
    
    def get_hour_options(self) -> list:
        """시간대 선택 옵션"""
        return self.engine.get_hour_options()


# 싱글톤 인스턴스
saju_engine = None
if EPHEM_AVAILABLE:
    saju_engine = SajuEngine()
