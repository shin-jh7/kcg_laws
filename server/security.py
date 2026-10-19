"""
관리자 접근 제어 모듈 (IP 허용 목록 + 관리자 로그인 세션)

환경변수
- ADMIN_ALLOWED_NETWORKS : 관리자 허용 IP 대역 (쉼표 구분, CIDR)
                           기본값 "59.13.166.128/25,127.0.0.1/32,::1/128"
- ADMIN_PASSWORD_HASH    : 관리자 비밀번호 해시 (python -m server.security 로 생성)
                           미설정 시 로그인 불가(안전하게 차단)
- ADMIN_SESSION_MINUTES  : 미사용 시 세션 만료 시간(분), 기본 30
- TRUST_PROXY            : "1" 이면 리버스 프록시의 X-Forwarded-For 헤더로 실제 IP 판별
"""
import os
import time
import hmac
import base64
import hashlib
import secrets
import logging
import ipaddress
import threading
from typing import Optional, Dict, Tuple

from fastapi import Request

# ----------------- 설정 -----------------

DEFAULT_NETWORKS = "59.13.166.128/25,127.0.0.1/32,::1/128"
ALLOWED_NETWORKS = [
    ipaddress.ip_network(n.strip(), strict=False)
    for n in os.environ.get("ADMIN_ALLOWED_NETWORKS", DEFAULT_NETWORKS).split(",")
    if n.strip()
]
SESSION_MINUTES = int(os.environ.get("ADMIN_SESSION_MINUTES", "30"))
TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
SESSION_COOKIE = "kcg_admin_session"

MAX_FAILURES = 5
LOCKOUT_SECONDS = 5 * 60

PBKDF2_ITERATIONS = 310_000

# ----------------- 감사 로그 -----------------

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_LOG_DIR, exist_ok=True)
audit_logger = logging.getLogger("kcg_admin_audit")
if not audit_logger.handlers:
    _h = logging.FileHandler(os.path.join(_LOG_DIR, "admin_audit.log"), encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
    audit_logger.addHandler(_h)
    audit_logger.setLevel(logging.INFO)

def audit(ip: str, action: str, detail: str = "") -> None:
    audit_logger.info(f"{ip}\t{action}\t{detail}")

# ----------------- IP 판별 -----------------

def get_client_ip(request: Request) -> str:
    if TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            # 프록시가 마지막에 덧붙인 값(가장 오른쪽)이 신뢰 가능한 실제 클라이언트 IP
            return xff.split(",")[-1].strip()
    return request.client.host if request.client else ""

def is_ip_allowed(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    return any(addr in net for net in ALLOWED_NETWORKS)

# ----------------- 비밀번호 해시 (PBKDF2-SHA256, 표준 라이브러리) -----------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )

def verify_password(password: str) -> bool:
    stored = os.environ.get("ADMIN_PASSWORD_HASH", "")
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iters)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False

def is_password_configured() -> bool:
    return os.environ.get("ADMIN_PASSWORD_HASH", "").startswith("pbkdf2_sha256$")

# ----------------- 로그인 실패 잠금 -----------------

_lock = threading.Lock()
_failures: Dict[str, Tuple[int, float]] = {}  # ip -> (실패횟수, 잠금해제시각)

def lockout_remaining(ip: str) -> int:
    with _lock:
        cnt, until = _failures.get(ip, (0, 0.0))
        remain = int(until - time.time())
        return remain if remain > 0 else 0

def record_failure(ip: str) -> None:
    with _lock:
        cnt, until = _failures.get(ip, (0, 0.0))
        if until and until < time.time():
            cnt = 0
        cnt += 1
        until = time.time() + LOCKOUT_SECONDS if cnt >= MAX_FAILURES else 0.0
        _failures[ip] = (cnt, until)

def clear_failures(ip: str) -> None:
    with _lock:
        _failures.pop(ip, None)

# ----------------- 세션 -----------------

_sessions: Dict[str, dict] = {}

def create_session(ip: str) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {"ip": ip, "expires": time.time() + SESSION_MINUTES * 60}
    return token

def validate_session(token: Optional[str], ip: str) -> bool:
    if not token:
        return False
    with _lock:
        s = _sessions.get(token)
        if not s:
            return False
        if s["expires"] < time.time() or s["ip"] != ip:
            _sessions.pop(token, None)
            return False
        s["expires"] = time.time() + SESSION_MINUTES * 60  # 사용 시 만료 연장
        return True

def destroy_session(token: Optional[str]) -> None:
    if token:
        with _lock:
            _sessions.pop(token, None)

def is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    return TRUST_PROXY and request.headers.get("x-forwarded-proto", "") == "https"

# ----------------- 보호 대상 경로 판별 -----------------

def _norm(path: str) -> str:
    p = path.lower()
    while "//" in p:
        p = p.replace("//", "/")
    return p.rstrip("/") or "/"

def requires_admin(path: str, method: str) -> bool:
    """관리자 IP + 로그인이 필요한 요청인지 판별합니다."""
    p = _norm(path)
    if p == "/admin" or (p.startswith("/static/") and p.endswith("/admin.html")):
        return True
    if p.startswith("/api/sync"):
        return True
    if p.startswith("/api/laws") and method not in ("GET", "HEAD", "OPTIONS"):
        return True
    return False

def requires_admin_ip_only(path: str) -> bool:
    """로그인 전이라도 관리자 IP만 접근 가능한 경로 (로그인 화면/처리)."""
    p = _norm(path)
    return p in ("/admin/login", "/api/admin/login") or p.endswith("/admin_login.html")


if __name__ == "__main__":
    # 관리자 비밀번호 해시 생성 도구:  python -m server.security
    import getpass
    pw = getpass.getpass("새 관리자 비밀번호: ")
    if len(pw) < 10:
        raise SystemExit("비밀번호는 10자 이상으로 설정해 주세요.")
    if pw != getpass.getpass("비밀번호 확인: "):
        raise SystemExit("비밀번호가 일치하지 않습니다.")
    print("\n아래 값을 환경변수 ADMIN_PASSWORD_HASH 로 설정하세요:\n")
    print(hash_password(pw))
