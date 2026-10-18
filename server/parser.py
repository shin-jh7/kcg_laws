import io
import re
from typing import List, Dict, Any, Tuple
import pypdf

def extract_text_from_pdf(content_bytes: bytes) -> str:
    """
    바이너리 PDF 데이터로부터 텍스트를 추출합니다.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        pages_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
        return "\n".join(pages_text)
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

def parse_law_text(text: str, default_title: str = "법령 명칭 미상") -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    법령 텍스트를 파싱하여 메타정보와 계층적 조문(장, 조, 부칙, 별표) 목록을 반환합니다.
    """
    lines = [line.strip() for line in text.strip().splitlines()]
    if not lines:
        return {"title": default_title}, []

    meta = {
        "title": default_title,
        "promulgation_no": "",
        "enforcement_date": "",
        "department": "해양경찰청",
        "department_phone": ""
    }

    # 1. 상단 메타데이터 파싱 (첫 20줄 이내에서 탐색)
    header_idx_limit = min(len(lines), 20)
    content_start_line = 0
    
    for i in range(header_idx_limit):
        line = lines[i]
        if not line:
            continue
            
        # 법제처 / 국가법령정보센터 워터마크 줄 건너뛰기
        if "국가법령정보센터" in line and "법제처" in line:
            continue

        # 첫 번째 유의미한 줄을 제목 후보로 사용 (사용자가 따로 제목을 준 경우 제외)
        if meta["title"] == default_title and not line.startswith("[") and not line.startswith("제") and ("해양경찰" in line or "규칙" in line or "법" in line or "규정" in line or "고시" in line):
            meta["title"] = line
            continue

        # 시행일자 및 발령정보: [시행 2024. 10. 21.] [해양수산부령 제696호, 2024. 10. 21., 일부개정]
        enf_match = re.search(r"시행\s*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2})", line)
        if enf_match:
            meta["enforcement_date"] = enf_match.group(1).replace(" ", "")

        prom_match = re.search(r"([가-힣]+(?:령|훈령|예규|고시)\s*제\d+호)", line)
        if prom_match:
            meta["promulgation_no"] = prom_match.group(1)

        # 소관부서 및 연락처: 해양경찰청 (장비관리과), 032-835-2276
        dept_match = re.search(r"([가-힣]+청(?:\s*\([가-힣]+\))?)", line)
        if dept_match and ("소관" in line or "관리" in line or "과" in line):
            meta["department"] = dept_match.group(1)
            
        phone_match = re.search(r"(\d{2,3}-\d{3,4}-\d{4})", line)
        if phone_match:
            meta["department_phone"] = phone_match.group(1)

        # 제1장 또는 제1조 시작 지점을 찾으면 헤더 종료
        if re.match(r"^제\d+장\s+", line) or re.match(r"^제\d+조(?:\([^)]+\))?", line):
            content_start_line = i
            break

    # 2. 본문 조문 및 섹션 파싱
    sections: List[Dict[str, Any]] = []
    current_sec: Optional[Dict[str, Any]] = None
    body_lines = lines[content_start_line:]
    
    # 정규식 패턴 정의
    chapter_pattern = re.compile(r"^(제\d+장)\s*(.*)$")
    article_pattern = re.compile(r"^(제\d+조(?:의\d+)?)(?:\(([^)]+)\))?\s*(.*)$")
    addenda_pattern = re.compile(r"^(부\s*칙)(.*)$")
    annex_pattern = re.compile(r"^(\[별표\s*\d*\]|\[서식\s*\d*\])\s*(.*)$")

    current_chapter = ""

    for line in body_lines:
        if not line:
            continue

        # 장 (Chapter) 감지
        chap_match = chapter_pattern.match(line)
        if chap_match:
            if current_sec:
                sections.append(current_sec)
                current_sec = None
            current_chapter = f"{chap_match.group(1)} {chap_match.group(2)}".strip()
            sections.append({
                "section_type": "chapter",
                "section_no": chap_match.group(1).strip(),
                "section_title": chap_match.group(2).strip(),
                "content": line
            })
            continue

        # 부칙 (Addenda) 감지
        add_match = addenda_pattern.match(line)
        if add_match:
            if current_sec:
                sections.append(current_sec)
            current_sec = {
                "section_type": "addenda",
                "section_no": "부칙",
                "section_title": add_match.group(2).strip() or "부칙",
                "content": line
            }
            continue

        # 별표/서식 (Annex) 감지
        annex_match = annex_pattern.match(line)
        if annex_match:
            if current_sec:
                sections.append(current_sec)
            current_sec = {
                "section_type": "annex",
                "section_no": annex_match.group(1).strip(),
                "section_title": annex_match.group(2).strip() or "별표",
                "content": line
            }
            continue

        # 조문 (Article) 감지
        art_match = article_pattern.match(line)
        if art_match:
            if current_sec:
                sections.append(current_sec)
            
            sec_no = art_match.group(1).strip()
            sec_title = (art_match.group(2) or "").strip()
            first_body = (art_match.group(3) or "").strip()
            
            content_text = f"{sec_no}({sec_title}) {first_body}".strip() if sec_title else f"{sec_no} {first_body}".strip()
            
            current_sec = {
                "section_type": "article",
                "section_no": sec_no,
                "section_title": sec_title,
                "content": content_text
            }
            continue

        # 현재 진행 중인 섹션에 줄 추가
        if current_sec:
            current_sec["content"] += "\n" + line
        else:
            # 시작 전 일반 전문/개요 문장인 경우
            current_sec = {
                "section_type": "article",
                "section_no": "전문",
                "section_title": "제정/개정문",
                "content": line
            }

    if current_sec:
        sections.append(current_sec)

    # 섹션이 하나도 안 뽑혔을 경우 (일반 자유 텍스트 문서 fallback)
    if not sections:
        sections.append({
            "section_type": "article",
            "section_no": "본문",
            "section_title": "전문",
            "content": text
        })

    return meta, sections
