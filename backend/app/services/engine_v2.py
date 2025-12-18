"""
Scientific Saju Engine v2 - 천문학 기반 (Source of Truth)

NASA JPL 데이터 기반 ephem 라이브러리 사용
- 태양 황경(Ecliptic Longitude)으로 24절기 '분' 단위 정밀 판별
- KASI(한국천문연구원) 데이터와 동일한 천문학적 정답

⚠️ 필수 설치: pip install ephem

검증 완료:
- 1978-05-16 11:00 → 무오년 정사월 무인일 정사시 ✅
- 2000-01-01 일주 = 무오 ✅
- 입춘 경계 (314°/316°) 정확 판별 ✅
"""
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

try:
    import ephem
    EPHEM_AVAILABLE = True
except ImportError:
    EPHEM_AVAILABLE = False


# ============ 상수 정의 ============

GAN = list("갑을병정무기경신임계")
JI = list("자축인묘진사오미신유술해")

GAN_HANJA = list("甲乙丙丁戊己庚辛壬癸")
JI_HANJA = list("子丑寅卯辰巳午未申酉戌亥")

GAN_TO_ELEMENT = {
    "갑": "목", "을": "목", "병": "화", "정": "화", "무": "토",
    "기": "토", "경": "금", "신": "금", "임": "수", "계": "수"
}

JI_TO_ELEMENT = {
    "자": "수", "축": "토", "인": "목", "묘": "목", "진": "토", "사": "화",
    "오": "화", "미": "토", "신": "금", "유": "금", "술": "토", "해": "수"
}

DAY_MASTER_DESC = {
    "갑": "큰 나무(甲木) - 곧고 뻗어나가는 성장의 기운",
    "을": "작은 나무(乙木) - 유연하고 적응력 있는 기운",
    "병": "태양(丙火) - 밝고 뜨거운 열정의 기운",
    "정": "촛불(丁火) - 따뜻하고 은은한 빛의 기운",
    "무": "큰 산(戊土) - 안정적이고 묵직한 기운",
    "기": "논밭(己土) - 포용하고 키워내는 기운",
    "경": "바위/쇠(庚金) - 강하고 결단력 있는 기운",
    "신": "보석(辛金) - 섬세하고 빛나는 기운",
    "임": "큰 물(壬水) - 넓고 깊은 지혜의 기운",
    "계": "이슬/비(癸水) - 촉촉하고 스며드는 기운"
}

# 절기 이름 (월지 인덱스별)
SOLAR_TERM_NAMES = [
    "동지~소한 (자월)",   # 0
    "소한~입춘 (축월)",   # 1
    "입춘~경칩 (인월)",   # 2
    "경칩~청명 (묘월)",   # 3
    "청명~입하 (진월)",   # 4
    "입하~망종 (사월)",   # 5
    "망종~소서 (오월)",   # 6
    "소서~입추 (미월)",   # 7
    "입추~백로 (신월)",   # 8
    "백로~한로 (유월)",   # 9
    "한로~입동 (술월)",   # 10
    "입동~동지 (해월)",   # 11
]

# 시간대 옵션
HOUR_OPTIONS = [
    {"index": 0, "ji": "자", "ji_hanja": "子", "start": "23:00", "end": "00:59"},
    {"index": 1, "ji": "축", "ji_hanja": "丑", "start": "01:00", "end": "02:59"},
    {"index": 2, "ji": "인", "ji_hanja": "寅", "start": "03:00", "end": "04:59"},
    {"index": 3, "ji": "묘", "ji_hanja": "卯", "start": "05:00", "end": "06:59"},
    {"index": 4, "ji": "진", "ji_hanja": "辰", "start": "07:00", "end": "08:59"},
    {"index": 5, "ji": "사", "ji_hanja": "巳", "start": "09:00", "end": "10:59"},
    {"index": 6, "ji": "오", "ji_hanja": "午", "start": "11:00", "end": "12:59"},
    {"index": 7, "ji": "미", "ji_hanja": "未", "start": "13:00", "end": "14:59"},
    {"index": 8, "ji": "신", "ji_hanja": "申", "start": "15:00", "end": "16:59"},
    {"index": 9, "ji": "유", "ji_hanja": "酉", "start": "17:00", "end": "18:59"},
    {"index": 10, "ji": "술", "ji_hanja": "戌", "start": "19:00", "end": "20:59"},
    {"index": 11, "ji": "해", "ji_hanja": "亥", "start": "21:00", "end": "22:59"},
]


class CalculationError(Exception):
    """계산 오류 - fallback 금지, 에러 반환"""
    pass


class ScientificSajuEngine:
    """
    천문학 기반 사주 엔진 (Source of Truth)
    
    - ephem 라이브러리: NASA JPL 데이터 기반
    - 태양 황경 계산으로 24절기 정밀 판별
    - 태양시 보정 ON/OFF 토글 지원
    """
    
    def __init__(self):
        if not EPHEM_AVAILABLE:
            raise ImportError(
                "ephem 라이브러리가 필요합니다.\n"
                "설치: pip install ephem"
            )
        
        # Anchor: 2000년 1월 1일 = 무오일 (60갑자 중 54번째)
        self.ANCHOR_DATE = datetime(2000, 1, 1)
        self.ANCHOR_IDX = 54
    
    def _get_solar_longitude(self, year: int, month: int, day: int, hour: int, minute: int = 0) -> float:
        """
        태양의 황경(Ecliptic Longitude) 계산
        
        핵심: ephem.Ecliptic(sun).lon 사용
        - 지구에서 본 태양의 황도 경도
        """
        dt_kst = datetime(year, month, day, hour, minute)
        dt_utc = dt_kst - timedelta(hours=9)
        
        sun = ephem.Sun()
        observer = ephem.Observer()
        observer.date = dt_utc
        sun.compute(observer)
        
        # 진짜 황경: Ecliptic coordinate
        ecliptic = ephem.Ecliptic(sun)
        lon_deg = math.degrees(ecliptic.lon)
        
        return lon_deg
    
    def _get_solar_term_index(self, solar_longitude: float) -> Tuple[int, str]:
        """
        황경 → 월지 인덱스 매핑
        
        24절기 기준:
        - 입춘(315°) → 인월(2) 시작
        - 경칩(345°) → 묘월(3) 시작
        - ...
        - 동지(270°) → 자월(0) 시작
        
        공식: (황경 + 45) / 30 → 0~11 → +2 → 월지
        """
        deg = solar_longitude
        
        # 정규화: +45도 해서 입춘(315°)이 0이 되도록
        normalized = (deg + 45) % 360
        term_idx = int(normalized / 30)  # 0~11
        
        # 월지 인덱스: term_idx 0 = 인월(2)
        month_ji_idx = (term_idx + 2) % 12
        
        term_name = SOLAR_TERM_NAMES[month_ji_idx]
        
        return month_ji_idx, term_name
    
    def _is_near_boundary(self, solar_longitude: float) -> Tuple[bool, Optional[str]]:
        """절기 경계 근처인지 확인 (±1.5도 ≈ 36시간)"""
        deg = solar_longitude
        
        # 절기 경계 각도들: 0, 15, 30, 45, ... 345
        for boundary in range(0, 360, 15):
            diff = abs((deg - boundary + 180) % 360 - 180)
            if diff <= 1.5:
                if boundary == 315:
                    return True, "near_ipchun"
                return True, "near_term_change"
        
        return False, None
    
    def calculate(
        self,
        year: int,
        month: int,
        day: int,
        hour: Optional[int] = None,
        minute: int = 0,
        use_solar_time: bool = True
    ) -> Dict[str, Any]:
        """
        사주 계산 메인 함수
        
        Args:
            year, month, day: 양력 생년월일
            hour: 출생 시 (0-23), None이면 시주 생략
            minute: 출생 분
            use_solar_time: 태양시 보정 (-30분) 적용 여부
        
        Returns:
            사주 결과 딕셔너리
        
        Raises:
            CalculationError: 계산 실패시 (fallback 금지)
        """
        
        try:
            # ========== 1. 태양 황경 계산 ==========
            calc_hour = hour if hour is not None else 12
            solar_lon = self._get_solar_longitude(year, month, day, calc_hour, minute)
            solar_idx, solar_term = self._get_solar_term_index(solar_lon)
            is_boundary, boundary_reason = self._is_near_boundary(solar_lon)
            
            # ========== 2. 년주 계산 ==========
            cal_year = year
            
            # 1~2월이고 아직 인월(2)이 안 됐으면 전년도
            if month <= 2:
                if solar_idx <= 1:  # 자(0) 또는 축(1)
                    cal_year = year - 1
            
            year_gan_idx = (cal_year - 4) % 10
            year_ji_idx = (cal_year - 4) % 12
            
            # ========== 3. 월주 계산 ==========
            month_ji_idx = solar_idx
            
            # 월간 공식 (연두법)
            start_gan_idx = (year_gan_idx % 5) * 2 + 2
            gap = month_ji_idx - 2
            if gap < 0:
                gap += 12
            month_gan_idx = (start_gan_idx + gap) % 10
            
            # ========== 4. 일주 계산 ==========
            target_dt = datetime(year, month, day)
            days_diff = (target_dt - self.ANCHOR_DATE).days
            curr_day_idx = (self.ANCHOR_IDX + days_diff) % 60
            
            day_gan_idx = curr_day_idx % 10
            day_ji_idx = curr_day_idx % 12
            
            # ========== 5. 시주 계산 ==========
            hour_gan_idx = None
            hour_ji_idx = None
            hour_range = None
            
            if hour is not None:
                # 태양시 보정 (Toggle)
                adjusted_minute = hour * 60 + minute
                if use_solar_time:
                    adjusted_minute -= 30
                    if adjusted_minute < 0:
                        adjusted_minute += 1440
                
                eff_hour = adjusted_minute // 60
                
                # 시지: (시간+1)//2
                hour_ji_idx = ((eff_hour + 1) // 2) % 12
                
                # 시간: (일간%5)*2 + 시지
                start_time_gan = (day_gan_idx % 5) * 2
                hour_gan_idx = (start_time_gan + hour_ji_idx) % 10
                
                # 시간대 범위
                h_opt = HOUR_OPTIONS[hour_ji_idx]
                hour_range = f"{h_opt['start']}~{h_opt['end']}"
            
            # ========== 결과 반환 ==========
            return {
                "year_pillar": self._make_pillar(year_gan_idx, year_ji_idx),
                "month_pillar": self._make_pillar(month_gan_idx, month_ji_idx),
                "day_pillar": self._make_pillar(day_gan_idx, day_ji_idx),
                "hour_pillar": self._make_pillar(hour_gan_idx, hour_ji_idx) if hour is not None else None,
                "hour_range": hour_range,
                "day_master": GAN[day_gan_idx],
                "day_master_element": GAN_TO_ELEMENT[GAN[day_gan_idx]],
                "day_master_description": DAY_MASTER_DESC[GAN[day_gan_idx]],
                "meta": {
                    "solar_time_applied": use_solar_time,
                    "solar_longitude_deg": round(solar_lon, 2),
                    "solar_term_idx": solar_idx,
                    "solar_term_name": solar_term,
                    "is_boundary": is_boundary,
                    "boundary_reason": boundary_reason,
                    "calculation_method": "ephem_astronomical",
                    "timezone": "Asia/Seoul"
                }
            }
            
        except Exception as e:
            raise CalculationError(f"사주 계산 실패: {str(e)}")
    
    def _make_pillar(self, gan_idx: int, ji_idx: int) -> Dict[str, Any]:
        """Pillar 딕셔너리 생성"""
        return {
            "ganji": GAN[gan_idx] + JI[ji_idx],
            "gan": GAN[gan_idx],
            "ji": JI[ji_idx],
            "gan_hanja": GAN_HANJA[gan_idx],
            "ji_hanja": JI_HANJA[ji_idx],
            "gan_element": GAN_TO_ELEMENT[GAN[gan_idx]],
            "ji_element": JI_TO_ELEMENT[JI[ji_idx]],
            "gan_index": gan_idx,
            "ji_index": ji_idx
        }
    
    @staticmethod
    def get_hour_options():
        """시간대 선택 옵션"""
        return [
            {
                "index": h["index"],
                "ji": h["ji"],
                "ji_hanja": h["ji_hanja"],
                "range_start": h["start"],
                "range_end": h["end"],
                "label": f"{h['ji_hanja']}시 ({h['ji']}시) - {h['start']}~{h['end']}"
            }
            for h in HOUR_OPTIONS
        ]


# 싱글톤 인스턴스
scientific_engine = None
if EPHEM_AVAILABLE:
    scientific_engine = ScientificSajuEngine()


# ============ Regression Tests ============

def run_tests():
    """회귀 테스트 - 정답 기준과 100% 일치 확인"""
    if not EPHEM_AVAILABLE:
        print("❌ ephem 미설치")
        return False
    
    engine = ScientificSajuEngine()
    passed = True
    
    print("=" * 60)
    print("🧪 Scientific Saju Engine v2 - Regression Tests")
    print("=" * 60)
    
    # Test 1: 핵심 케이스
    res = engine.calculate(1978, 5, 16, 11, 0, use_solar_time=True)
    
    print(f"\n[1978-05-16 11:00] Solar Time ON")
    print(f"  년: {res['year_pillar']['ganji']} | 월: {res['month_pillar']['ganji']} | 일: {res['day_pillar']['ganji']} | 시: {res['hour_pillar']['ganji']}")
    print(f"  황경: {res['meta']['solar_longitude_deg']}° | 절기: {res['meta']['solar_term_name']}")
    
    if (res['year_pillar']['ganji'] == '무오' and
        res['month_pillar']['ganji'] == '정사' and
        res['day_pillar']['ganji'] == '무인' and
        res['hour_pillar']['ganji'] == '정사'):
        print("  ✅ PASS")
    else:
        print("  ❌ FAIL")
        passed = False
    
    # Test 2: Anchor
    res2 = engine.calculate(2000, 1, 1, 12, 0)
    print(f"\n[2000-01-01 Anchor]")
    print(f"  일주: {res2['day_pillar']['ganji']} (기대: 무오)")
    
    if res2['day_pillar']['ganji'] == '무오':
        print("  ✅ PASS")
    else:
        print("  ❌ FAIL")
        passed = False
    
    # Test 3: 입춘 경계
    res3a = engine.calculate(2025, 2, 3, 12, 0)
    res3b = engine.calculate(2025, 2, 5, 12, 0)
    
    print(f"\n[입춘 경계]")
    print(f"  2025-02-03: {res3a['year_pillar']['ganji']} (황경 {res3a['meta']['solar_longitude_deg']}°)")
    print(f"  2025-02-05: {res3b['year_pillar']['ganji']} (황경 {res3b['meta']['solar_longitude_deg']}°)")
    
    if res3a['year_pillar']['ganji'] == '갑진' and res3b['year_pillar']['ganji'] == '을사':
        print("  ✅ PASS")
    else:
        print("  ❌ FAIL")
        passed = False
    
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED" if passed else "❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return passed


if __name__ == "__main__":
    run_tests()
