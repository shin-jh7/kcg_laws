import os
import sys
import shutil

# 프로젝트 루트 디렉터리를 sys.path 최상단에 등록
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Vercel 서버리스 환경 대응:
# Vercel 람다는 루트 파일시스템이 읽기 전용이므로, 번들된 SQLite DB를 /tmp로 복제하여 연결
if os.environ.get("VERCEL"):
    bundle_db = os.path.join(BASE_DIR, "data", "kcg_laws.db")
    tmp_db = "/tmp/kcg_laws.db"
    if not os.path.exists(tmp_db) and os.path.exists(bundle_db):
        try:
            shutil.copy2(bundle_db, tmp_db)
        except Exception as e:
            print(f"[Vercel DB Copy Warning] {e}")
    
    if os.path.exists(tmp_db):
        from server import database
        database.DB_PATH = tmp_db

from server.main import app
