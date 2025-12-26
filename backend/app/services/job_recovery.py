"""
Job Recovery - 컨테이너 재시작 시 미완료 Job 복구
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
99,000원 유료 서비스에서 Job 손실은 치명적
→ 서버 시작 시 DB에서 미완료 상태 Job을 찾아 자동 재시작
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def recover_interrupted_jobs(rulestore: Any = None) -> int:
    """
    서버 시작 시 미완료 Job 복구
    
    복구 대상:
    1. status = 'generating' (진행 중이었던 것)
    2. status = 'pending' 이면서 생성된 지 1시간 이내
    
    Returns:
        복구 시작한 Job 수
    """
    try:
        from app.services.supabase_store import supabase_store
        from app.services.report_worker import report_worker
    except ImportError as e:
        logger.warning(f"[Recovery] Import 실패: {e}")
        return 0
    
    recovered_count = 0
    
    try:
        # 🔥 1. 진행 중이었던 리포트 (generating)
        generating_reports = await supabase_store.get_reports_by_status("generating")
        
        for report in generating_reports:
            report_id = report["id"]
            created_at = report.get("created_at", "")
            
            logger.info(f"[Recovery] 🔄 미완료 리포트 발견: {report_id} (status=generating)")
            
            # 백그라운드로 재시작
            asyncio.create_task(
                report_worker.start_report_generation(report_id, rulestore)
            )
            recovered_count += 1
        
        # 🔥 2. 대기 중이었던 리포트 (pending, 1시간 이내 생성)
        pending_reports = await supabase_store.get_reports_by_status("pending")
        
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        for report in pending_reports:
            report_id = report["id"]
            created_at_str = report.get("created_at", "")
            
            # 생성 시간 파싱
            try:
                # ISO 형식 파싱
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                created_at = created_at.replace(tzinfo=None)  # naive로 변환
                
                # 1시간 이내에 생성된 것만 복구
                if created_at > cutoff_time:
                    logger.info(f"[Recovery] 🔄 대기 중 리포트 발견: {report_id} (status=pending)")
                    
                    asyncio.create_task(
                        report_worker.start_report_generation(report_id, rulestore)
                    )
                    recovered_count += 1
                else:
                    # 오래된 pending은 failed로 마킹
                    logger.warning(f"[Recovery] ⚠️ 오래된 pending 리포트: {report_id} → failed로 마킹")
                    await supabase_store.fail_report(
                        report_id, 
                        "서버 재시작 시 타임아웃으로 복구 불가. 재신청 필요."
                    )
            except Exception as parse_err:
                logger.warning(f"[Recovery] 날짜 파싱 실패: {report_id} | {parse_err}")
                continue
        
        if recovered_count > 0:
            logger.info(f"[Recovery] ✅ 총 {recovered_count}개 리포트 복구 시작")
        else:
            logger.info("[Recovery] ✅ 복구할 미완료 리포트 없음")
        
        return recovered_count
        
    except Exception as e:
        logger.error(f"[Recovery] ❌ 복구 실패: {e}")
        return 0
