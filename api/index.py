import os
import sys

# 프로젝트 루트 디렉터리를 sys.path 최상단에 등록
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Vercel 환경 플래그가 없을 경우에도 람다 환경 감지
if not os.environ.get("VERCEL") and os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    os.environ["VERCEL"] = "1"

# 데이터베이스 Vercel 초기화 트리거
try:
    from server import database
    database._init_vercel_db()
except Exception as e:
    print(f"[Vercel DB Init Warning in index.py] {e}")

from server.main import app

