import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "kcg_laws.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 메인 법령/행정규칙 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS laws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,          -- 'law' (법령) 또는 'rule' (행정규칙)
        sub_category TEXT,               -- 법률, 대통령령, 부령, 훈령, 예규, 고시 등
        promulgation_no TEXT,            -- 발령번호 (예: 해양수산부령 제696호)
        promulgation_date TEXT,          -- 발령일자 (YYYY-MM-DD)
        enforcement_date TEXT,           -- 시행일자 (YYYY-MM-DD)
        department TEXT,                 -- 소관부서 (예: 해양경찰청 장비관리과)
        department_phone TEXT,           -- 연락처 (예: 032-835-2276)
        file_path TEXT,                  -- 로컬 저장소 파일 상대 경로
        file_name TEXT,                  -- 원본 파일명
        raw_content TEXT,                -- 원문 전체 텍스트
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. 목차 및 조문 구조화 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS law_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        law_id INTEGER NOT NULL,
        section_type TEXT NOT NULL,      -- 'chapter', 'article', 'addenda', 'annex'
        section_no TEXT,                 -- 예: '제1장', '제1조', '부칙', '[별표 1]'
        section_title TEXT,              -- 예: '총칙', '목적', '경찰모의 제식'
        content TEXT NOT NULL,           -- 조문 본문 내용 (항/호/목)
        order_idx INTEGER NOT NULL,      -- 목차 순서
        FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
    );
    """)

    # 3. 색인 생성
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_laws_category ON laws(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_laws_subcategory ON laws(sub_category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_law_id ON law_sections(law_id);")

    conn.commit()
    conn.close()

def insert_law(law_data: Dict[str, Any], sections: List[Dict[str, Any]]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO laws (
        title, category, sub_category, promulgation_no, promulgation_date,
        enforcement_date, department, department_phone, file_path, file_name, raw_content
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        law_data.get("title", ""),
        law_data.get("category", "law"),
        law_data.get("sub_category", "법률"),
        law_data.get("promulgation_no", ""),
        law_data.get("promulgation_date", ""),
        law_data.get("enforcement_date", ""),
        law_data.get("department", "해양경찰청"),
        law_data.get("department_phone", ""),
        law_data.get("file_path", ""),
        law_data.get("file_name", ""),
        law_data.get("raw_content", "")
    ))
    
    law_id = cursor.lastrowid
    
    for idx, sec in enumerate(sections):
        cursor.execute("""
        INSERT INTO law_sections (
            law_id, section_type, section_no, section_title, content, order_idx
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            law_id,
            sec.get("section_type", "article"),
            sec.get("section_no", ""),
            sec.get("section_title", ""),
            sec.get("content", ""),
            idx
        ))
        
    conn.commit()
    conn.close()
    return law_id

def replace_law_sections(law_id: int, sections: List[Dict[str, Any]], raw_content: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    if raw_content is not None:
        cursor.execute("UPDATE laws SET raw_content = ? WHERE id = ?", (raw_content, law_id))
        
    cursor.execute("DELETE FROM law_sections WHERE law_id = ?", (law_id,))
    
    for idx, sec in enumerate(sections):
        cursor.execute("""
        INSERT INTO law_sections (
            law_id, section_type, section_no, section_title, content, order_idx
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            law_id,
            sec.get("section_type", "article"),
            sec.get("section_no", ""),
            sec.get("section_title", ""),
            sec.get("content", ""),
            idx
        ))
        
    conn.commit()
    conn.close()


def get_laws(category: Optional[str] = None, sub_category: Optional[str] = None, keyword: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT id, title, category, sub_category, promulgation_no, promulgation_date, enforcement_date, department, department_phone, file_name, created_at FROM laws WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    if sub_category and sub_category != "전체":
        query += " AND sub_category = ?"
        params.append(sub_category)
    if keyword:
        query += " AND (title LIKE ? OR raw_content LIKE ?)"
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_law_by_id(law_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM laws WHERE id = ?", (law_id,))
    law_row = cursor.fetchone()
    if not law_row:
        conn.close()
        return None
        
    law = dict(law_row)
    
    cursor.execute("""
    SELECT id, section_type, section_no, section_title, content, order_idx
    FROM law_sections
    WHERE law_id = ?
    ORDER BY order_idx ASC
    """, (law_id,))
    
    sections = [dict(row) for row in cursor.fetchall()]
    law["sections"] = sections
    conn.close()
    return law

def delete_law(law_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    # 첨부 파일 삭제용 경로 조회
    cursor.execute("SELECT file_path FROM laws WHERE id = ?", (law_id,))
    row = cursor.fetchone()
    if row and row["file_path"]:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), row["file_path"])
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception:
                pass
                
    cursor.execute("DELETE FROM law_sections WHERE law_id = ?", (law_id,))
    cursor.execute("DELETE FROM laws WHERE id = ?", (law_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM laws WHERE category = 'law'")
    law_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM laws WHERE category = 'rule'")
    rule_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM laws WHERE category = 'commentary'")
    commentary_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM law_sections")
    section_count = cursor.fetchone()[0]
    
    conn.close()
    return {
        "law_count": law_count,
        "rule_count": rule_count,
        "commentary_count": commentary_count,
        "total_count": law_count + rule_count + commentary_count,
        "section_count": section_count
    }

def update_law(law_id: int, update_data: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    # 파일명 변경 요청 시 실제 디스크 파일 이름 변경
    if "file_name" in update_data and update_data["file_name"]:
        cursor.execute("SELECT file_path, file_name FROM laws WHERE id = ?", (law_id,))
        cur_row = cursor.fetchone()
        if cur_row and cur_row["file_path"] and cur_row["file_name"] != update_data["file_name"].strip():
            old_rel_path = cur_row["file_path"]
            old_full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), old_rel_path)
            new_file_name = update_data["file_name"].strip()
            new_rel_path = os.path.join(os.path.dirname(old_rel_path), new_file_name)
            new_full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), new_rel_path)
            
            if os.path.exists(old_full_path):
                try:
                    os.rename(old_full_path, new_full_path)
                    update_data["file_path"] = new_rel_path
                except Exception as e:
                    print(f"Error renaming file: {e}")

    fields = []
    params = []
    
    allowed_fields = [
        "title", "category", "sub_category", "department", 
        "department_phone", "promulgation_no", "promulgation_date", "enforcement_date",
        "file_name", "file_path"
    ]
    
    for f in allowed_fields:
        if f in update_data:
            fields.append(f"{f} = ?")
            params.append(update_data[f])
            
    if not fields:
        conn.close()
        return False
        
    params.append(law_id)
    sql = f"UPDATE laws SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(sql, params)
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

