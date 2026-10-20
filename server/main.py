import os
import shutil
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from urllib.parse import quote
from pydantic import BaseModel
from .database import init_db, get_laws, get_law_by_id, delete_law, get_stats, insert_law, update_law, replace_law_sections
from .parser import parse_law_text, extract_text_from_pdf
from .search import search_laws_and_sections
from .api_sync import sync_laws, sync_admin_rules, run_all_sync, SYNC_STATUS
from .seed_data import seed_sample_data
from . import security
from fastapi.responses import RedirectResponse

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
STORAGE_LAWS_DIR = os.path.join(BASE_DIR, "data", "storage", "laws")
STORAGE_RULES_DIR = os.path.join(BASE_DIR, "data", "storage", "rules")
STORAGE_COMMENTARY_DIR = os.path.join(BASE_DIR, "data", "storage", "commentary")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 기동 시 DB 초기화 및 기본 샘플 데이터(첨부2 복제 규칙 등) 시딩 (안전 처리)
    try:
        init_db()
        seed_sample_data()
    except Exception as e:
        print(f"[Lifespan Init Warning] {e}")
    yield

app = FastAPI(title="해양경찰 법령정보센터 API", lifespan=lifespan)

# CORS: 허용 도메인만 명시 (기본값: 없음 = 동일 출처만 허용)
_cors_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

# ----------------- 관리자 접근 제어 미들웨어 -----------------

@app.middleware("http")
async def admin_guard(request, call_next):
    path = request.url.path
    method = request.method
    need_login = security.requires_admin(path, method)
    need_ip = need_login or security.requires_admin_ip_only(path)

    if need_ip:
        ip = security.get_client_ip(request)
        if not security.is_ip_allowed(ip):
            security.audit(ip, "DENY_IP", f"{method} {path}")
            if path.startswith("/api/"):
                return JSONResponse(status_code=403, content={"detail": "허용되지 않은 IP에서의 관리자 접근입니다."})
            return JSONResponse(status_code=403, content={"detail": "접근 권한이 없습니다."})

        if need_login:
            token = request.cookies.get(security.SESSION_COOKIE)
            if not security.validate_session(token, ip):
                if path.startswith("/api/"):
                    return JSONResponse(status_code=401, content={"detail": "관리자 로그인이 필요합니다."})
                return RedirectResponse(url="/admin/login", status_code=303)
            if method not in ("GET", "HEAD", "OPTIONS"):
                security.audit(ip, "ADMIN_ACTION", f"{method} {path}")

    return await call_next(request)

class LoginModel(BaseModel):
    password: str

@app.post("/api/admin/login")
def api_admin_login(payload: LoginModel, request: Request):
    ip = security.get_client_ip(request)
    remain = security.lockout_remaining(ip)
    if remain:
        raise HTTPException(status_code=429, detail=f"로그인 실패가 반복되어 잠겨 있습니다. {remain // 60 + 1}분 후 다시 시도하세요.")
    if not security.is_password_configured():
        raise HTTPException(status_code=503, detail="관리자 비밀번호가 설정되지 않았습니다. 서버 환경변수 ADMIN_PASSWORD_HASH를 설정하세요.")
    if not security.verify_password(payload.password):
        security.record_failure(ip)
        security.audit(ip, "LOGIN_FAIL")
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

    security.clear_failures(ip)
    token = security.create_session(ip)
    security.audit(ip, "LOGIN_OK")
    resp = JSONResponse({"status": "success"})
    resp.set_cookie(
        security.SESSION_COOKIE, token,
        httponly=True, samesite="strict", secure=security.is_https(request),
        max_age=security.SESSION_MINUTES * 60, path="/"
    )
    return resp

@app.post("/api/admin/logout")
def api_admin_logout(request: Request):
    token = request.cookies.get(security.SESSION_COOKIE)
    security.destroy_session(token)
    security.audit(security.get_client_ip(request), "LOGOUT")
    resp = JSONResponse({"status": "success"})
    resp.delete_cookie(security.SESSION_COOKIE, path="/")
    return resp

@app.get("/api/admin/session")
def api_admin_session(request: Request):
    """메뉴의 '관리자 모드' 링크 표시 여부 판단용 (관리자 IP에서만 true 가능)"""
    ip = security.get_client_ip(request)
    allowed = security.is_ip_allowed(ip)
    logged_in = allowed and security.validate_session(request.cookies.get(security.SESSION_COOKIE), ip)
    return {"admin_ip": allowed, "logged_in": logged_in}

# ----------------- REST API -----------------

@app.get("/api/stats")
def api_get_stats():
    return get_stats()

@app.get("/api/laws")
def api_get_laws(
    category: Optional[str] = Query(None, description="'law' 또는 'rule'"),
    sub_category: Optional[str] = Query(None, description="법률, 부령, 훈령, 예규, 고시 등"),
    q: Optional[str] = Query(None, description="필터 검색어")
):
    cat_val = category if isinstance(category, str) else None
    sub_val = sub_category if isinstance(sub_category, str) else None
    q_val = q if isinstance(q, str) else None
    return get_laws(category=cat_val, sub_category=sub_val, keyword=q_val)

@app.get("/api/laws/{law_id}")
def api_get_law(law_id: int):
    law = get_law_by_id(law_id)
    if not law:
        raise HTTPException(status_code=404, detail="해당 법령을 찾을 수 없습니다.")
    return law

@app.get("/api/search")
def api_search(
    q: str = Query(..., description="검색 키워드"),
    category: Optional[str] = Query(None, description="'law' 또는 'rule'")
):
    results = search_laws_and_sections(q, category=category)
    return {"query": q, "count": len(results), "results": results}

@app.post("/api/laws/upload")
async def api_upload_law(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("law"),
    sub_category: str = Form("법률"),
    promulgation_no: str = Form(""),
    promulgation_date: str = Form(""),
    enforcement_date: str = Form(""),
    department: str = Form("해양경찰청"),
    department_phone: str = Form("")
):
    if category == "law":
        target_dir = STORAGE_LAWS_DIR
    elif category == "commentary":
        target_dir = STORAGE_COMMENTARY_DIR
    else:
        target_dir = STORAGE_RULES_DIR
    os.makedirs(target_dir, exist_ok=True)
    
    file_name = file.filename
    save_path = os.path.join(target_dir, file_name)
    
    # 중복 파일명 처리
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(save_path):
        save_path = os.path.join(target_dir, f"{base_name}_{counter}{ext}")
        counter += 1
        
    actual_file_name = os.path.basename(save_path)

    # 로컬 디렉터리에 물리적 파일 저장
    content_bytes = await file.read()
    with open(save_path, "wb") as f:
        f.write(content_bytes)

    # 텍스트 디코딩 또는 PDF 텍스트 자동 추출
    raw_text = ""
    if actual_file_name.lower().endswith(".pdf") or content_bytes.startswith(b"%PDF"):
        raw_text = extract_text_from_pdf(content_bytes)
        if not raw_text:
            raw_text = f"[{actual_file_name} 파일이 로컬에 저장되었습니다. (텍스트 없는 스캔본 PDF)]"
    else:
        try:
            raw_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = content_bytes.decode("cp949")
            except UnicodeDecodeError:
                raw_text = f"[{actual_file_name} 파일이 로컬에 저장되었습니다. 바이너리 문서이므로 첨부 다운로드로 열람 가능합니다.]"

    # 조문 구조 자동 파싱
    parsed_meta, sections = parse_law_text(raw_text, default_title=title or base_name)

    rel_file_path = os.path.relpath(save_path, BASE_DIR)
    final_title = title.strip() or parsed_meta.get("title") or base_name

    law_data = {
        "title": final_title,
        "category": category,
        "sub_category": sub_category,
        "promulgation_no": promulgation_no.strip() or parsed_meta.get("promulgation_no", ""),
        "promulgation_date": promulgation_date.strip(),
        "enforcement_date": enforcement_date.strip() or parsed_meta.get("enforcement_date", ""),
        "department": department.strip() or parsed_meta.get("department", "해양경찰청"),
        "department_phone": department_phone.strip() or parsed_meta.get("department_phone", ""),
        "file_path": rel_file_path,
        "file_name": actual_file_name,
        "raw_content": raw_text
    }

    new_id = insert_law(law_data, sections)
    return {
        "status": "success",
        "message": f"'{final_title}' 법령 파일이 로컬에 정상 저장 및 등록되었습니다.",
        "law_id": new_id,
        "sections_count": len(sections),
        "file_path": rel_file_path
    }

class LawUpdateModel(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    department: Optional[str] = None
    department_phone: Optional[str] = None
    promulgation_no: Optional[str] = None
    promulgation_date: Optional[str] = None
    enforcement_date: Optional[str] = None
    file_name: Optional[str] = None

@app.put("/api/laws/{law_id}")
def api_update_law(law_id: int, payload: LawUpdateModel):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="수정할 필드가 지정되지 않았습니다.")
    success = update_law(law_id, data)
    if not success:
        raise HTTPException(status_code=404, detail="수정할 법령을 찾을 수 없습니다.")
    return {"status": "success", "message": "법령 정보가 성공적으로 수정되었습니다.", "law_id": law_id}

@app.post("/api/laws/{law_id}/replace-file")
async def api_replace_law_file(law_id: int, file: UploadFile = File(...)):
    law = get_law_by_id(law_id)
    if not law:
        raise HTTPException(status_code=404, detail="법령을 찾을 수 없습니다.")

    if law["category"] == "law":
        target_dir = STORAGE_LAWS_DIR
    elif law["category"] == "commentary":
        target_dir = STORAGE_COMMENTARY_DIR
    else:
        target_dir = STORAGE_RULES_DIR
    os.makedirs(target_dir, exist_ok=True)
    
    file_name = file.filename
    save_path = os.path.join(target_dir, file_name)
    
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(save_path) and os.path.basename(save_path) != law.get("file_name"):
        save_path = os.path.join(target_dir, f"{base_name}_{counter}{ext}")
        counter += 1
        
    actual_file_name = os.path.basename(save_path)
    content_bytes = await file.read()
    with open(save_path, "wb") as f:
        f.write(content_bytes)

    if law.get("file_path"):
        old_full = os.path.join(BASE_DIR, law["file_path"])
        if os.path.exists(old_full) and os.path.abspath(old_full) != os.path.abspath(save_path):
            try:
                os.remove(old_full)
            except Exception:
                pass

    rel_path = os.path.relpath(save_path, BASE_DIR)
    
    # 새 파일 텍스트 추출 및 조문 재파싱
    new_raw_text = ""
    if actual_file_name.lower().endswith(".pdf") or content_bytes.startswith(b"%PDF"):
        new_raw_text = extract_text_from_pdf(content_bytes)
    else:
        try:
            new_raw_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                new_raw_text = content_bytes.decode("cp949")
            except UnicodeDecodeError:
                pass

    if new_raw_text:
        _, new_sections = parse_law_text(new_raw_text, default_title=law["title"])
        if new_sections:
            replace_law_sections(law_id, new_sections, raw_content=new_raw_text)

    update_law(law_id, {"file_name": actual_file_name, "file_path": rel_path})
    return {"status": "success", "message": f"파일이 '{actual_file_name}'(으)로 교체 및 조문 파싱 완료되었습니다.", "file_name": actual_file_name}

@app.get("/api/pdf/{law_id}")
def api_view_pdf(law_id: int):
    law = get_law_by_id(law_id)
    if not law or not law.get("file_path"):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    full_path = os.path.join(BASE_DIR, law["file_path"])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="로컬에 파일이 존재하지 않습니다.")
    
    media_type = "application/pdf" if law["file_path"].lower().endswith(".pdf") else "text/plain"
    return FileResponse(
        path=full_path,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(law.get('file_name', 'document'))}"}
    )

@app.delete("/api/laws/{law_id}")
def api_delete_law(law_id: int):
    success = delete_law(law_id)
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 법령을 찾을 수 없습니다.")
    return {"status": "success", "message": f"법령 ID {law_id} 및 로컬 파일이 삭제되었습니다."}

@app.get("/api/download/{law_id}")
def api_download_law(law_id: int):
    law = get_law_by_id(law_id)
    if not law or not law.get("file_path"):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    full_path = os.path.join(BASE_DIR, law["file_path"])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="로컬 저장소에 파일이 존재하지 않습니다.")
        
    return FileResponse(
        path=full_path,
        filename=law.get("file_name") or os.path.basename(full_path),
        media_type="application/octet-stream"
    )

class SyncRequest(BaseModel):
    law_queries: Optional[List[str]] = None
    rule_queries: Optional[List[str]] = None
    expc_queries: Optional[List[str]] = None
    law_limit: int = 0
    rule_limit: int = 0
    expc_limit: int = 0
    download_annex: bool = True

@app.post("/api/sync/kcg-laws")
def api_sync_kcg_laws(req: SyncRequest = SyncRequest()):
    """국가법령정보센터 Open API를 호출하여 최신 해양경찰 법령, 행정규칙(별표/서식 포함), 법령해설을 로컬에 자동 수집합니다."""
    try:
        # 이전 캐시된 프론트엔드에서 5건 요청이 들어오더라도 전체 수집(0)으로 자동 전환
        law_limit = 0 if req.law_limit == 5 else req.law_limit
        rule_limit = 0 if req.rule_limit == 5 else req.rule_limit
        expc_limit = 0 if req.expc_limit == 5 else req.expc_limit

        res = run_all_sync(
            queries_law=req.law_queries,
            queries_rule=req.rule_queries,
            queries_expc=req.expc_queries,
            law_limit=law_limit,
            rule_limit=rule_limit,
            expc_limit=expc_limit,
            download_annex=req.download_annex
        )

        stats = get_stats()
        return {
            "status": "success",
            "laws_synced": res["laws_count"],
            "rules_synced": res["rules_count"],
            "commentaries_synced": res.get("comms_count", 0),
            "total_synced": res["total_count"],
            "db_law_count": stats["law_count"],
            "db_rule_count": stats["rule_count"],
            "db_commentary_count": stats.get("commentary_count", 0),
            "db_total_count": stats["total_count"],
            "db_section_count": stats["section_count"],
            "message": f"국가법령정보센터 전체 동기화 완료: 법령 {stats['law_count']}건, 행정규칙 {stats['rule_count']}건, 법령해설 {stats.get('commentary_count', 0)}건 (총 {stats['total_count']}건)이 로컬에 적재되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Open API 동기화 중 오류 발생: {str(e)}")

@app.get("/api/sync/status")
def api_get_sync_status():
    """진행 중인 Open API 동기화 실시간 진행률 및 상태를 조회합니다."""
    return SYNC_STATUS

# ----------------- HTML 라우팅 -----------------

@app.get("/")
def route_home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/laws")
def route_laws():
    return FileResponse(os.path.join(STATIC_DIR, "list.html"))

@app.get("/rules")
def route_rules():
    return FileResponse(os.path.join(STATIC_DIR, "list.html"))

@app.get("/commentary")
def route_commentary():
    return FileResponse(os.path.join(STATIC_DIR, "list.html"))

@app.get("/search")
def route_search():
    return FileResponse(os.path.join(STATIC_DIR, "search.html"))

@app.get("/viewer")
def route_viewer():
    return FileResponse(os.path.join(STATIC_DIR, "viewer.html"))

@app.get("/admin")
def route_admin():
    return FileResponse(
        os.path.join(STATIC_DIR, "admin.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/admin/login")
def route_admin_login():
    return FileResponse(
        os.path.join(STATIC_DIR, "admin_login.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

# 정적 리소스 마운트 (CSS, JS, 이미지 등)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
