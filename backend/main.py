@app.get("/")
def read_root():
    return {"message": "SajuOS API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

import os
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.services.engine_v2 import SajuEngine # 형의 기존 엔진
from app.services.gpt_interpreter import GPTInterpreter # 클로드용 GPT 서비스

app = FastAPI(title="SajuOS Premium API")

# 1. CORS 설정 (Vercel 도메인 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 상용화 시 sajuos.com으로 제한 권장
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 서버 시작 시 데이터 로드 (상대 경로 ./data/1717/ 적용)
RULE_CARDS = []
@app.on_event("startup")
async def startup_event():
    db_path = "./data/sajuos_master_db.jsonl"
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                # 클로드가 수정한 경로 확인 로직 포함 가능
                RULE_CARDS.append(card)
        print(f"✅ [RuleCards] {len(RULE_CARDS)}개 로드 완료 (Path: 1717)")
    else:
        print(f"❌ [Error] 데이터를 찾을 수 없습니다: {db_path}")

# 3. 핵심 엔드포인트: 리포트 생성
@app.post("/api/v1/generate-report")
async def generate_report(request: Request):
    data = await request.json()
    try:
        # GPT 호출 및 리포트 생성 로직 (클로드 코드 삽입부)
        # Supabase 저장 로직이 여기에 들어감
        return {
            "status": "success",
            "model_used": "gpt-4o",
            "report": "생성된 리포트 내용..."
        }
    except Exception as e:
        # 에러 시 fallback 응답 전송
        return {"model_used": "fallback", "error": str(e)}

@app.get("/health")
def health():
    return {"status": "ok", "db_connected": os.getenv("DATABASE_URL") is not None}