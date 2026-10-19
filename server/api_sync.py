import os
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .database import get_connection, insert_law, update_law, replace_law_sections


PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))

def _load_env_file():
    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

# 국가법령정보센터 Open API 인증키: 환경변수(LAW_GO_KR_OC_KEY, KCG_LAW_OC_KEY 또는 OC_KEY)에서 로드, 미설정 시 공용 테스트 키("test") 사용
OC_KEY = os.environ.get("LAW_GO_KR_OC_KEY") or os.environ.get("KCG_LAW_OC_KEY") or os.environ.get("OC_KEY") or "test"
BASE_URL = "http://www.law.go.kr"

LAWS_DIR = os.path.join(PROJECT_DIR, "data", "storage", "laws")
RULES_DIR = os.path.join(PROJECT_DIR, "data", "storage", "rules")
COMMENTARY_DIR = os.path.join(PROJECT_DIR, "data", "storage", "commentary")
LAWS_ANNEX_DIR = os.path.join(LAWS_DIR, "annex")
RULES_ANNEX_DIR = os.path.join(RULES_DIR, "annex")

# 기본 검색 키워드 목록
DEFAULT_LAW_QUERIES = ["해양경찰", "해양경찰청", "해양경비", "수상레저", "연안사고", "수색구조"]
DEFAULT_RULE_QUERIES = ["해양경찰청", "해양경찰"]
DEFAULT_EXPC_QUERIES = ["해양경찰", "해양경찰청"]

# 전역 동기화 상태 추적 객체 (웹 UI 실시간 모니터링용)
SYNC_STATUS = {
    "is_running": False,
    "step": "idle",
    "message": "대기 중",
    "laws_total": 0,
    "laws_done": 0,
    "rules_total": 0,
    "rules_done": 0,
    "comms_total": 0,
    "comms_done": 0,
    "last_result": None,
    "error": None
}

def download_file(url: str, save_path: str) -> bool:
    """국가법령정보센터 첨부 파일(별표/서식 등)을 다운로드합니다. (이미 존재 시 재사용)"""
    try:
        if os.path.exists(save_path) and os.path.getsize(save_path) > 100:
            return True

        full_url = url if url.startswith("http") else BASE_URL + url
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
            if len(content) > 100:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(content)
                return True
    except Exception as e:
        print(f"[다운로드 오류] {url} -> {e}")
    return False

# ----------------- 1. 목록 수집 (다중 키워드 및 페이지네이션 자동 순회) -----------------

def collect_unique_law_items(queries: List[str], limit: int = 0) -> List[Tuple[str, ET.Element]]:
    """여러 검색어로 법령 목록을 검색하여 중복 없는 (MST, Element) 목록을 반환합니다."""
    unique_items: Dict[str, ET.Element] = {}

    for q in queries:
        page = 1
        while True:
            params = urllib.parse.urlencode({
                "OC": OC_KEY,
                "target": "law",
                "type": "XML",
                "query": q,
                "display": 100,
                "page": page
            })
            search_url = f"{BASE_URL}/DRF/lawSearch.do?{params}"
            try:
                req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    xml_data = resp.read()
                root = ET.fromstring(xml_data)
                items = root.findall("law")
                if not items:
                    break
                for it in items:
                    mst = it.findtext("법령일련번호") or it.findtext("일련번호")
                    if mst and mst not in unique_items:
                        unique_items[mst] = it
                        if limit > 0 and len(unique_items) >= limit:
                            return list(unique_items.items())

                total_cnt = int(root.findtext("totalCnt") or "0")
                if page * 100 >= total_cnt:
                    break
                page += 1
            except Exception as e:
                print(f"[법령 목록 오류] 검색어 '{q}', 페이지 {page}: {e}")
                break

    return list(unique_items.items())

def collect_unique_rule_items(queries: List[str], limit: int = 0) -> List[Tuple[str, ET.Element]]:
    """여러 검색어로 행정규칙 목록을 검색하여 중복 없는 (행정규칙일련번호, Element) 목록을 반환합니다."""
    unique_items: Dict[str, ET.Element] = {}

    for q in queries:
        page = 1
        while True:
            params = urllib.parse.urlencode({
                "OC": OC_KEY,
                "target": "admrul",
                "type": "XML",
                "query": q,
                "display": 100,
                "page": page
            })
            search_url = f"{BASE_URL}/DRF/lawSearch.do?{params}"
            try:
                req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    xml_data = resp.read()
                root = ET.fromstring(xml_data)
                items = root.findall("admrul")
                if not items:
                    break
                for it in items:
                    seq = it.findtext("행정규칙일련번호")
                    if seq and seq not in unique_items:
                        unique_items[seq] = it
                        if limit > 0 and len(unique_items) >= limit:
                            return list(unique_items.items())

                total_cnt = int(root.findtext("totalCnt") or "0")
                if page * 100 >= total_cnt:
                    break
                page += 1
            except Exception as e:
                print(f"[행정규칙 목록 오류] 검색어 '{q}', 페이지 {page}: {e}")
                break

    return list(unique_items.items())

def collect_unique_expc_items(queries: List[str], limit: int = 0) -> List[Tuple[str, ET.Element]]:
    """법령해석례(법령해설) 목록을 수집하여 중복 없는 (일련번호, Element) 목록을 반환합니다."""
    unique_items: Dict[str, ET.Element] = {}
    active_oc = OC_KEY

    for q in queries:
        page = 1
        while True:
            params = urllib.parse.urlencode({
                "OC": active_oc,
                "target": "expc",
                "type": "XML",
                "query": q,
                "display": 100,
                "page": page
            })
            search_url = f"{BASE_URL}/DRF/lawSearch.do?{params}"
            try:
                req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    xml_data = resp.read()

                # 사용자 키가 '미신청 서비스'일 경우 법제처 공용 test 키로 자동 전환
                if b'error500' in xml_data and active_oc != "test":
                    print("[API 법령해설] 사용자 키 미신청 상태 감지 -> 공용 Open API 키(test)로 자동 전환하여 수집합니다.")
                    active_oc = "test"
                    continue

                root = ET.fromstring(xml_data)
                items = root.findall(".//expc")
                if not items:
                    break
                for it in items:
                    seq = it.findtext("법령해석례일련번호") or it.findtext("일련번호")
                    if seq and seq not in unique_items:
                        unique_items[seq] = it
                        if limit > 0 and len(unique_items) >= limit:
                            return list(unique_items.items())

                total_cnt = int(root.findtext("totalCnt") or "0")
                if page * 100 >= total_cnt:
                    break
                page += 1
            except Exception as e:
                print(f"[법령해설 목록 오류] 검색어 '{q}', 페이지 {page}: {e}")
                break

    return list(unique_items.items())

# ----------------- 2. 개별 상세 파싱 함수 -----------------

def parse_single_law(mst: str, item: ET.Element, download_annex: bool = True) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], int]]:
    """단일 법령의 상세 조문 및 별표 파일을 파싱합니다."""
    title = item.findtext("법령명한글") or "법령"
    detail_url = f"{BASE_URL}/DRF/lawService.do?OC={OC_KEY}&target=law&MST={mst}&type=XML"
    
    try:
        d_req = urllib.request.Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(d_req, timeout=20) as d_resp:
            d_xml = d_resp.read()

        d_root = ET.fromstring(d_xml)
        meta_title = d_root.findtext("기본정보/법령명_한글") or title
        prom_no = d_root.findtext("기본정보/공포번호") or item.findtext("공포번호") or ""
        if prom_no and not prom_no.startswith("제") and "호" not in prom_no:
            prom_no = f"제{prom_no}호"

        enf_date_raw = d_root.findtext("기본정보/시행일자") or item.findtext("시행일자") or ""
        enf_date = f"{enf_date_raw[:4]}-{enf_date_raw[4:6]}-{enf_date_raw[6:]}" if len(enf_date_raw) == 8 else enf_date_raw

        dept = d_root.findtext("기본정보/소관부처") or item.findtext("소관부처명") or "해양경찰청"
        sub_cat = d_root.findtext("기본정보/법종구분") or item.findtext("법령구분명") or "법률"

        sections = []
        full_body_lines = [f"{meta_title}\n[시행 {enf_date}] [{prom_no}]\n소관부서: {dept}\n"]

        # 조문단위
        for art in d_root.findall(".//조문단위"):
            art_no = (art.findtext("조문번호") or "").strip()
            if art_no and not art_no.startswith("제"):
                art_no = f"제{art_no}조"
            art_title = (art.findtext("조문제목") or "").strip()
            art_content = (art.findtext("조문내용") or "").strip()

            sub_lines = []
            for p in art.findall(".//항"):
                p_content = (p.findtext("항내용") or "").strip()
                if p_content:
                    sub_lines.append(p_content)
                for h in p.findall(".//호"):
                    h_content = (h.findtext("호내용") or "").strip()
                    if h_content:
                        sub_lines.append(h_content)

            combined_content = art_content
            if sub_lines:
                combined_content += "\n" + "\n".join(sub_lines)

            sections.append({
                "section_type": "article",
                "section_no": art_no,
                "section_title": art_title,
                "content": combined_content
            })
            full_body_lines.append(combined_content)

        # 부칙단위
        for add in d_root.findall(".//부칙단위"):
            add_content = (add.findtext("부칙내용") or "").strip()
            if add_content:
                sections.append({
                    "section_type": "addenda",
                    "section_no": "부칙",
                    "section_title": "부칙",
                    "content": add_content
                })
                full_body_lines.append(add_content)

        # 별표단위 및 파일 다운로드
        annex_saved_count = 0
        for byl in d_root.findall(".//별표단위"):
            byl_no = (byl.findtext("별표번호") or "").strip()
            byl_title = (byl.findtext("별표제목") or byl.findtext("별표명") or "").strip()
            byl_link = byl.findtext("별표서식PDF파일링크") or byl.findtext("별표서식파일링크") or byl.findtext("별표파일링크") or ""

            byl_display_no = f"[별표 {byl_no}]" if byl_no else "[별표]"
            annex_content = f"{byl_display_no} {byl_title}"

            if download_annex and byl_link:
                ext = ".pdf" if "pdf" in byl_link.lower() else ".hwp"
                safe_title = re.sub(r'[\\/*?:"<>|]', "", byl_title)[:30]
                annex_filename = f"law_{mst}_별표{byl_no}_{safe_title}{ext}"
                save_path = os.path.join(LAWS_ANNEX_DIR, annex_filename)
                if download_file(byl_link, save_path):
                    annex_saved_count += 1
                    rel_annex = os.path.relpath(save_path, PROJECT_DIR)
                    annex_content += f"\n(로컬 저장 첨부: {rel_annex})"

            sections.append({
                "section_type": "annex",
                "section_no": byl_display_no,
                "section_title": byl_title,
                "content": annex_content
            })
            full_body_lines.append(annex_content)

        raw_text = "\n\n".join(full_body_lines)
        safe_law_title = re.sub(r'[\\/*?:"<>|]', "", meta_title)
        law_file_name = f"{safe_law_title}_{mst}.txt"
        law_file_path = os.path.join(LAWS_DIR, law_file_name)
        with open(law_file_path, "w", encoding="utf-8") as f:
            f.write(raw_text)

        rel_law_path = os.path.relpath(law_file_path, PROJECT_DIR)

        law_dict = {
            "title": meta_title,
            "category": "law",
            "sub_category": sub_cat,
            "promulgation_no": prom_no,
            "enforcement_date": enf_date,
            "department": dept,
            "department_phone": "",
            "file_path": rel_law_path,
            "file_name": law_file_name,
            "raw_content": raw_text
        }

        return (law_dict, sections, annex_saved_count)

    except Exception as e:
        print(f"[법령 상세 오류] {title} (MST:{mst}): {e}")
        return None

def parse_single_rule(seq: str, item: ET.Element, download_annex: bool = True) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], int]]:
    """단일 행정규칙(훈령/예규/고시)의 상세 조문 및 별표 파일을 파싱합니다."""
    title = item.findtext("행정규칙명") or "행정규칙"
    kind = item.findtext("행정규칙종류") or "훈령"
    detail_url = f"{BASE_URL}/DRF/lawService.do?OC={OC_KEY}&target=admrul&ID={seq}&type=XML"

    try:
        d_req = urllib.request.Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(d_req, timeout=20) as d_resp:
            d_xml = d_resp.read()

        d_root = ET.fromstring(d_xml)
        meta_title = d_root.findtext(".//행정규칙명") or title
        prom_no = d_root.findtext(".//발령번호") or item.findtext("발령번호") or ""
        if prom_no and "호" not in prom_no:
            prom_no = f"제{prom_no}호"

        enf_date_raw = d_root.findtext(".//시행일자") or item.findtext("시행일자") or ""
        enf_date = f"{enf_date_raw[:4]}-{enf_date_raw[4:6]}-{enf_date_raw[6:]}" if len(enf_date_raw) == 8 else enf_date_raw

        dept = d_root.findtext(".//소관부처명") or item.findtext("소관부처명") or "해양경찰청"

        sections = []
        full_body_lines = [f"{meta_title}\n[시행 {enf_date}] [{prom_no}]\n소관부서: {dept}\n"]

        for art in d_root.findall(".//조문단위"):
            art_no = (art.findtext("조문번호") or "").strip()
            if art_no and not art_no.startswith("제"):
                art_no = f"제{art_no}조"
            art_title = (art.findtext("조문제목") or "").strip()
            art_content = (art.findtext("조문내용") or "").strip()

            sections.append({
                "section_type": "article",
                "section_no": art_no,
                "section_title": art_title,
                "content": art_content
            })
            full_body_lines.append(art_content)

        annex_saved_count = 0
        for byl in d_root.findall(".//별표단위"):
            byl_no = (byl.findtext("별표번호") or "").strip()
            byl_title = (byl.findtext("별표명") or byl.findtext("별표제목") or "").strip()
            byl_link = byl.findtext("별표PDF파일링크") or byl.findtext("별표파일링크") or byl.findtext("별표서식파일링크") or ""

            byl_display_no = f"[별표 {byl_no}]" if byl_no else "[별표]"
            annex_content = f"{byl_display_no} {byl_title}"

            if download_annex and byl_link:
                ext = ".pdf" if "pdf" in byl_link.lower() else ".hwp"
                safe_title = re.sub(r'[\\/*?:"<>|]', "", byl_title)[:30]
                annex_filename = f"rule_{seq}_별표{byl_no}_{safe_title}{ext}"
                save_path = os.path.join(RULES_ANNEX_DIR, annex_filename)
                if download_file(byl_link, save_path):
                    annex_saved_count += 1
                    rel_annex = os.path.relpath(save_path, PROJECT_DIR)
                    annex_content += f"\n(로컬 저장 첨부: {rel_annex})"

            sections.append({
                "section_type": "annex",
                "section_no": byl_display_no,
                "section_title": byl_title,
                "content": annex_content
            })
            full_body_lines.append(annex_content)

        if not sections:
            full_raw = d_root.findtext(".//행정규칙본문") or ""
            if full_raw:
                sections.append({
                    "section_type": "article",
                    "section_no": "본문",
                    "section_title": "전문",
                    "content": full_raw
                })
                full_body_lines.append(full_raw)

        raw_text = "\n\n".join(full_body_lines)
        safe_rule_title = re.sub(r'[\\/*?:"<>|]', "", meta_title)
        rule_file_name = f"{safe_rule_title}_{seq}.txt"
        rule_file_path = os.path.join(RULES_DIR, rule_file_name)
        with open(rule_file_path, "w", encoding="utf-8") as f:
            f.write(raw_text)

        rel_rule_path = os.path.relpath(rule_file_path, PROJECT_DIR)

        rule_dict = {
            "title": meta_title,
            "category": "rule",
            "sub_category": kind,
            "promulgation_no": prom_no,
            "enforcement_date": enf_date,
            "department": dept,
            "department_phone": "",
            "file_path": rel_rule_path,
            "file_name": rule_file_name,
            "raw_content": raw_text
        }

        return (rule_dict, sections, annex_saved_count)

    except Exception as e:
        print(f"[행정규칙 상세 오류] {title} (ID:{seq}): {e}")
        return None

def parse_single_expc(seq: str, item: ET.Element) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """단일 법령해설(법제처 법령해석례)의 질의요지, 회답, 이유, 관계법령을 파싱합니다."""
    title = item.findtext("안건명") or "법령해설"
    item_no = item.findtext("안건번호") or ""

    for oc in [OC_KEY, "test"]:
        detail_url = f"{BASE_URL}/DRF/lawService.do?OC={oc}&target=expc&ID={seq}&type=XML"
        try:
            d_req = urllib.request.Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(d_req, timeout=15) as d_resp:
                d_xml = d_resp.read()

            if b'error500' in d_xml and oc != "test":
                continue

            d_root = ET.fromstring(d_xml)
            meta_title = d_root.findtext(".//안건명") or title
            meta_no = d_root.findtext(".//안건번호") or item_no
            prom_no = f"안건번호 {meta_no}" if meta_no and not meta_no.startswith("안건번호") else meta_no

            r_date_raw = d_root.findtext(".//해석일자") or d_root.findtext(".//회신일자") or d_root.findtext(".//일시") or ""
            r_date = f"{r_date_raw[:4]}-{r_date_raw[4:6]}-{r_date_raw[6:]}" if len(r_date_raw) == 8 else r_date_raw

            dept = d_root.findtext(".//질의기관") or item.findtext("질의기관") or "해양경찰청"
            interp_org = d_root.findtext(".//해석기관") or "법제처"
            dept_display = f"{dept} (해석: {interp_org})" if interp_org and interp_org not in dept else dept

            q_summary = (d_root.findtext(".//질의요지") or "").strip()
            answer = (d_root.findtext(".//회답") or "").strip()
            reason = (d_root.findtext(".//이유") or "").strip()
            rel_law = (d_root.findtext(".//관계법령") or "").strip()

            sections = []
            full_body_lines = [
                f"[해양경찰 법령해설] {meta_title}",
                f"[해석일자: {r_date}] [{prom_no}]",
                f"소관부서: {dept_display}\n"
            ]

            if q_summary:
                sections.append({
                    "section_type": "article",
                    "section_no": "1.",
                    "section_title": "질의요지",
                    "content": q_summary
                })
                full_body_lines.append(f"【질의요지】\n{q_summary}")

            if answer:
                sections.append({
                    "section_type": "article",
                    "section_no": "2.",
                    "section_title": "회답",
                    "content": answer
                })
                full_body_lines.append(f"【회답】\n{answer}")

            if reason:
                sections.append({
                    "section_type": "article",
                    "section_no": "3.",
                    "section_title": "이유",
                    "content": reason
                })
                full_body_lines.append(f"【이유】\n{reason}")

            if rel_law:
                sections.append({
                    "section_type": "article",
                    "section_no": "4.",
                    "section_title": "관계법령",
                    "content": rel_law
                })
                full_body_lines.append(f"【관계법령】\n{rel_law}")

            raw_text = "\n\n".join(full_body_lines)
            safe_title = re.sub(r'[\\/*?:"<>|]', "", meta_title)[:40]
            comm_file_name = f"commentary_{seq}_{safe_title}.txt"
            os.makedirs(COMMENTARY_DIR, exist_ok=True)
            comm_file_path = os.path.join(COMMENTARY_DIR, comm_file_name)
            with open(comm_file_path, "w", encoding="utf-8") as f:
                f.write(raw_text)

            rel_comm_path = os.path.relpath(comm_file_path, PROJECT_DIR)

            comm_dict = {
                "title": meta_title,
                "category": "commentary",
                "sub_category": "법령해설",
                "promulgation_no": prom_no,
                "enforcement_date": r_date,
                "department": dept_display,
                "department_phone": "",
                "file_path": rel_comm_path,
                "file_name": comm_file_name,
                "raw_content": raw_text
            }

            return (comm_dict, sections)

        except Exception as e:
            print(f"[법령해설 상세 오류] {title} (ID:{seq}): {e}")
            return None

    return None

# ----------------- 3. 일괄 수집 및 데이터베이스 트랜잭션 적재 -----------------

def sync_laws(queries: Optional[List[str]] = None, limit: int = 0, download_annex: bool = True) -> Dict[str, Any]:
    """해양경찰 관련 법률/시행령/시행규칙을 다중 검색어로 일괄 수집합니다."""
    os.makedirs(LAWS_ANNEX_DIR, exist_ok=True)
    queries = queries or DEFAULT_LAW_QUERIES

    print(f"[API 법령 수집] 검색어: {queries} (제한: {'전체' if limit <= 0 else limit}건)")
    law_items = collect_unique_law_items(queries, limit=limit)
    print(f"[API 법령 수집] 중복 제거된 고유 법령 {len(law_items)}건 발견")

    SYNC_STATUS["laws_total"] = len(law_items)
    SYNC_STATUS["laws_done"] = 0

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {
            executor.submit(parse_single_law, mst, item, download_annex): (mst, item.findtext("법령명한글") or "법령")
            for mst, item in law_items
        }
        for future in as_completed(future_map):
            mst, title = future_map[future]
            parsed = future.result()
            SYNC_STATUS["laws_done"] += 1
            if parsed:
                law_dict, sections, annex_saved = parsed
                results.append((law_dict, sections, annex_saved))

    synced_laws = []
    conn = get_connection()
    cursor = conn.cursor()

    for law_dict, sections, annex_saved in results:
        title = law_dict["title"]
        cursor.execute("SELECT id FROM laws WHERE title = ?", (title,))
        existing = cursor.fetchone()

        if existing:
            law_id = existing["id"]
            update_law(law_id, law_dict)
            replace_law_sections(law_id, sections, raw_content=law_dict["raw_content"])
            action = "갱신"
        else:
            law_id = insert_law(law_dict, sections)
            action = "신규등록"

        synced_laws.append({"id": law_id, "title": title, "action": action, "sections": len(sections)})

    conn.close()
    return {"status": "success", "count": len(synced_laws), "items": synced_laws}

def sync_admin_rules(queries: Optional[List[str]] = None, limit: int = 0, download_annex: bool = True) -> Dict[str, Any]:
    """해양경찰청 소관 행정규칙(훈령/예규/고시)을 다중 검색어로 일괄 수집합니다."""
    os.makedirs(RULES_ANNEX_DIR, exist_ok=True)
    queries = queries or DEFAULT_RULE_QUERIES

    print(f"[API 행정규칙 수집] 검색어: {queries} (제한: {'전체' if limit <= 0 else limit}건)")
    rule_items = collect_unique_rule_items(queries, limit=limit)
    print(f"[API 행정규칙 수집] 중복 제거된 고유 행정규칙 {len(rule_items)}건 발견")

    SYNC_STATUS["rules_total"] = len(rule_items)
    SYNC_STATUS["rules_done"] = 0

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {
            executor.submit(parse_single_rule, seq, item, download_annex): (seq, item.findtext("행정규칙명") or "행정규칙")
            for seq, item in rule_items
        }
        for future in as_completed(future_map):
            seq, title = future_map[future]
            parsed = future.result()
            SYNC_STATUS["rules_done"] += 1
            if parsed:
                rule_dict, sections, annex_saved = parsed
                results.append((rule_dict, sections, annex_saved))

    synced_rules = []
    conn = get_connection()
    cursor = conn.cursor()

    for rule_dict, sections, annex_saved in results:
        title = rule_dict["title"]
        cursor.execute("SELECT id FROM laws WHERE title = ?", (title,))
        existing = cursor.fetchone()

        if existing:
            law_id = existing["id"]
            update_law(law_id, rule_dict)
            replace_law_sections(law_id, sections, raw_content=rule_dict["raw_content"])
            action = "갱신"
        else:
            law_id = insert_law(rule_dict, sections)
            action = "신규등록"

        synced_rules.append({"id": law_id, "title": title, "action": action, "sections": len(sections)})

    conn.close()
    return {"status": "success", "count": len(synced_rules), "items": synced_rules}

def sync_commentaries(queries: Optional[List[str]] = None, limit: int = 0) -> Dict[str, Any]:
    """해양경찰 관련 법령해설(법제처 법령해석례)을 일괄 수집합니다."""
    os.makedirs(COMMENTARY_DIR, exist_ok=True)
    queries = queries or DEFAULT_EXPC_QUERIES

    print(f"[API 법령해설 수집] 검색어: {queries} (제한: {'전체' if limit <= 0 else limit}건)")
    expc_items = collect_unique_expc_items(queries, limit=limit)
    print(f"[API 법령해설 수집] 중복 제거된 고유 법령해설 {len(expc_items)}건 발견")

    SYNC_STATUS["comms_total"] = len(expc_items)
    SYNC_STATUS["comms_done"] = 0

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {
            executor.submit(parse_single_expc, seq, item): (seq, item.findtext("안건명") or "법령해설")
            for seq, item in expc_items
        }
        for future in as_completed(future_map):
            seq, title = future_map[future]
            parsed = future.result()
            SYNC_STATUS["comms_done"] += 1
            if parsed:
                comm_dict, sections = parsed
                results.append((comm_dict, sections))

    synced_comms = []
    conn = get_connection()
    cursor = conn.cursor()

    for comm_dict, sections in results:
        title = comm_dict["title"]
        prom_no = comm_dict.get("promulgation_no", "")
        if prom_no:
            cursor.execute("SELECT id FROM laws WHERE category = 'commentary' AND promulgation_no = ?", (prom_no,))
        else:
            cursor.execute("SELECT id FROM laws WHERE category = 'commentary' AND title = ?", (title,))
        existing = cursor.fetchone()

        if existing:
            law_id = existing["id"]
            update_law(law_id, comm_dict)
            replace_law_sections(law_id, sections, raw_content=comm_dict["raw_content"])
            action = "갱신"
        else:
            law_id = insert_law(comm_dict, sections)
            action = "신규등록"

        synced_comms.append({"id": law_id, "title": title, "action": action, "sections": len(sections)})

    conn.close()
    return {"status": "success", "count": len(synced_comms), "items": synced_comms}

def run_all_sync(
    queries_law: Optional[List[str]] = None,
    queries_rule: Optional[List[str]] = None,
    queries_expc: Optional[List[str]] = None,
    law_limit: int = 0,
    rule_limit: int = 0,
    expc_limit: int = 0,
    download_annex: bool = True
) -> Dict[str, Any]:
    """법령, 행정규칙, 법령해설을 모두 수집하고 전역 상태를 갱신합니다."""
    global SYNC_STATUS
    SYNC_STATUS["is_running"] = True
    SYNC_STATUS["step"] = "collecting_laws"
    SYNC_STATUS["message"] = "국가법령정보센터로부터 해양경찰 법령을 검색 및 수집 중입니다..."
    SYNC_STATUS["error"] = None

    try:
        # 1. 법령 수집
        res_laws = sync_laws(queries=queries_law, limit=law_limit, download_annex=download_annex)

        # 2. 행정규칙 수집
        SYNC_STATUS["step"] = "collecting_rules"
        SYNC_STATUS["message"] = f"법령 {res_laws['count']}건 수집 완료! 행정규칙(훈령/예규/고시)을 검색 및 수집 중입니다..."
        res_rules = sync_admin_rules(queries=queries_rule, limit=rule_limit, download_annex=download_annex)

        # 3. 법령해설(법령해석례) 수집
        SYNC_STATUS["step"] = "collecting_commentary"
        SYNC_STATUS["message"] = f"행정규칙 {res_rules['count']}건 수집 완료! 해양경찰 법령해설(유권해석례)을 수집 중입니다..."
        res_comms = sync_commentaries(queries=queries_expc, limit=expc_limit)

        total_cnt = res_laws["count"] + res_rules["count"] + res_comms["count"]
        result = {
            "status": "success",
            "laws_count": res_laws["count"],
            "rules_count": res_rules["count"],
            "comms_count": res_comms["count"],
            "total_count": total_cnt,
            "laws": res_laws,
            "rules": res_rules,
            "commentaries": res_comms
        }

        SYNC_STATUS["is_running"] = False
        SYNC_STATUS["step"] = "completed"
        SYNC_STATUS["message"] = f"동기화 완료: 법령 {res_laws['count']}건, 행정규칙 {res_rules['count']}건, 법령해설 {res_comms['count']}건 적재 성공!"
        SYNC_STATUS["last_result"] = result
        return result

    except Exception as e:
        SYNC_STATUS["is_running"] = False
        SYNC_STATUS["step"] = "failed"
        SYNC_STATUS["error"] = str(e)
        SYNC_STATUS["message"] = f"동기화 중 오류 발생: {str(e)}"
        raise

if __name__ == "__main__":
    print("=" * 65)
    print(" [국가법령정보센터 Open API] 해양경찰 법령, 행정규칙 및 법령해설 전체 수집")
    masked_key = f"{OC_KEY[:3]}***{OC_KEY[-2:]}" if len(OC_KEY) > 5 else OC_KEY
    print(f" 사용자 인증키: {masked_key} ({'사용자 발급키' if OC_KEY != 'test' else '공용 테스트키'})")
    print("=" * 65)
    run_all_sync(law_limit=0, rule_limit=0, expc_limit=0, download_annex=True)
