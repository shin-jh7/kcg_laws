import re
from typing import List, Dict, Any
from .database import get_connection

def search_laws_and_sections(keyword: str, category: str = None) -> List[Dict[str, Any]]:
    """
    키워드를 기반으로 법령 제목 및 조문 내용을 통합 검색하고 하이라이트된 스니펫을 반환합니다.
    """
    keyword = keyword.strip()
    if not keyword:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT 
        l.id as law_id,
        l.title as law_title,
        l.category,
        l.sub_category,
        l.promulgation_no,
        l.enforcement_date,
        l.department,
        s.id as section_id,
        s.section_type,
        s.section_no,
        s.section_title,
        s.content as section_content
    FROM laws l
    LEFT JOIN law_sections s ON l.id = s.law_id
    WHERE (l.title LIKE ? OR s.content LIKE ? OR s.section_title LIKE ?)
    """
    params = [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]

    if category and category in ("law", "rule"):
        sql += " AND l.category = ?"
        params.append(category)

    sql += " ORDER BY l.id DESC, s.order_idx ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # 법령별로 그룹화 및 스니펫 추출
    grouped: Dict[int, Dict[str, Any]] = {}
    
    # 대소문자 무시 정규식 패턴 생성
    regex_kw = re.compile(re.escape(keyword), re.IGNORECASE)

    for r in rows:
        lid = r["law_id"]
        if lid not in grouped:
            # 제목에 키워드가 있는지 확인
            title_matched = bool(regex_kw.search(r["law_title"]))
            highlighted_title = regex_kw.sub(lambda m: f"<mark>{m.group(0)}</mark>", r["law_title"])

            grouped[lid] = {
                "law_id": lid,
                "title": r["law_title"],
                "highlighted_title": highlighted_title,
                "category": r["category"],
                "sub_category": r["sub_category"],
                "promulgation_no": r["promulgation_no"],
                "enforcement_date": r["enforcement_date"],
                "department": r["department"],
                "title_matched": title_matched,
                "matched_sections": []
            }

        sec_content = r["section_content"] or ""
        sec_title = r["section_title"] or ""
        sec_no = r["section_no"] or ""

        match = regex_kw.search(sec_content)
        if match:
            start_pos = max(0, match.start() - 40)
            end_pos = min(len(sec_content), match.end() + 60)
            snippet = sec_content[start_pos:end_pos]
            
            if start_pos > 0:
                snippet = "..." + snippet
            if end_pos < len(sec_content):
                snippet = snippet + "..."

            highlighted_snippet = regex_kw.sub(lambda m: f"<mark>{m.group(0)}</mark>", snippet)
            
            sec_display = f"{sec_no} {sec_title}".strip()
            if not sec_display:
                sec_display = "본문 내용"

            grouped[lid]["matched_sections"].append({
                "section_no": sec_no,
                "section_title": sec_title,
                "section_display": sec_display,
                "snippet": highlighted_snippet
            })

    results = list(grouped.values())
    return results
