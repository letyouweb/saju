import os, re, hashlib

def get_openai_api_key() -> str:
    k = os.getenv("OPENAI_API_KEY", "")

    # 복붙 실수 방지: 따옴표/개행 제거 + 트림
    k = k.replace('"', "").replace("'", "")
    k = k.replace("\r", "").replace("\n", "").strip()

    # Bearer까지 넣었으면 제거
    if k.lower().startswith("bearer "):
        k = k[7:].strip()

    # 중간 공백/탭이 남아있으면 잘못 저장된 것
    if not k or re.search(r"\s", k):
        raise RuntimeError("OPENAI_API_KEY has whitespace/newline. Fix Railway Variables.")

    return k

def key_fingerprint(k: str) -> str:
    # 키 노출 없이 동일성만 검증
    return hashlib.sha256(k.encode("utf-8")).hexdigest()[:12]
