# [Architecture] 해양경찰 법령정보센터 시스템 아키텍처 및 설계서

## 1. 기술적 요구사항 및 스택 선정

### 1.1 기술 스택 요약
| 영역 | 기술 요소 | 버전 / 사양 | 선정 이유 |
| :--- | :--- | :--- | :--- |
| **운영체제** | Microsoft Windows | Windows 10/11 (PowerShell/CMD) | 사용자 로컬 환경 기본 사양 |
| **백엔드 언어** | Python | 3.12.10 (현재 PC 설치됨) | 법령 조문 텍스트 분석, 정규식 파싱, 파일 입출력 최적화 |
| **웹 프레임워크**| FastAPI | ^0.115.0 | 초고속 비동기 REST API, 자동 Swagger 문서화, 경량화 |
| **ASGI 서버** | Uvicorn | ^0.32.0 | 가벼운 파이썬 비동기 웹 서버 |
| **데이터베이스**| SQLite3 (FTS 지원)| 내장 (Python 기본) | 외부 DB 설치 불필요, 단일 파일 영구 저장, 키워드 전문 검색 지원 |
| **프론트엔드** | Modern Vanilla JS + CSS3 | ES6+, HTML5 | 별도 빌드/컴파일 없이 즉시 구동, 첨부3 컬러 테마 및 첨부2 2열 뷰어 최적 구현 |
| **실행 스크립트**| Windows Batch Script | `start.bat` | 더블클릭 원클릭 무인 실행 및 브라우저 자동 오픈 |

---

## 2. 시스템 아키텍처 구성도

```mermaid
graph TD
    subgraph Browser ["클라이언트 (웹 브라우저)"]
        HomeView["메인 홈 & 통합 검색 (index.html)"]
        ListView["법령 / 행정규칙 목록 (list.html)"]
        SearchView["검색 결과 화면 (search.html)"]
        ViewerView["새 창: 국가법령정보센터 2열 뷰어 (viewer.html)"]
        AdminView["관리자 파일 업로드 & 관리 (admin.html)"]
    end

    subgraph Backend ["로컬 백엔드 서버 (FastAPI on localhost:8000)"]
        Router["API 엔드포인트 라우터 (main.py)"]
        DocParser["법령 조문 구조 파서 (parser.py)"]
        SearchEngine["전문 검색 & 하이라이터 (search.py)"]
        StorageMgr["로컬 파일 저장소 관리자 (storage.py)"]
        DBMgr["SQLite 데이터베이스 핸들러 (database.py)"]
    end

    subgraph Disk ["로컬 PC 디스크 (c:/antigravity/kcg_laws/data/)"]
        DB[(kcg_laws.db - SQLite 메타 및 FTS)]
        LawDir["/storage/laws/ (법령 원본 파일)"]
        RuleDir["/storage/rules/ (행정규칙 원본 파일)"]
        CommDir["/storage/commentary/ (법령해설 원본 파일)"]
    end

    HomeView -->|GET /api/search, GET /api/stats| Router
    ListView -->|GET /api/laws?category=...| Router
    SearchView -->|GET /api/search?q=...| Router
    ViewerView -->|GET /api/laws/{id}| Router
    AdminView -->|POST /api/laws/upload, DELETE| Router

    Router --> DocParser
    Router --> SearchEngine
    Router --> StorageMgr
    Router --> DBMgr

    DocParser --> DBMgr
    SearchEngine --> DBMgr
    StorageMgr --> LawDir
    StorageMgr --> RuleDir
    StorageMgr --> CommDir
    DBMgr --> DB
```

---

## 3. 프로젝트 디렉터리 구조

```
c:\antigravity\kcg_laws\
├── start.bat                   # [원클릭 실행 파일] 서버 구동 및 브라우저 오픈
├── requirements.txt            # 파이썬 의존성 목록
├── README.md                   # 프로젝트 개요 (한글)
├── PRD.md                      # 기능 요구사항 정의서
├── Architecture.md             # 시스템 구조 및 설계서 (본 문서)
├── Operation.md                # 실행 및 운영 가이드
├── API_Integration.md          # 국가법령정보센터 Open API 연동 규격서
│
├── server\                     # 백엔드 소스코드
│   ├── __init__.py
│   ├── main.py                 # FastAPI 애플리케이션 진입점 및 라우팅
│   ├── database.py             # SQLite 연결, 스키마 생성 및 쿼리
│   ├── parser.py               # 조문(장/절/조/항/호/부칙/별표) 구조화 파서
│   ├── search.py               # 키워드 검색 및 스니펫 하이라이팅
│   ├── seed_data.py            # 초기 샘플 데이터 탑재 스크립트
│   └── api_sync.py             # 국가법령정보센터 Open API 연동 및 일괄 수집기
│
├── data\                       # 로컬 데이터 영구 보관소
│   ├── kcg_laws.db             # 로컬 메타데이터 및 전문 인덱스 DB
│   └── storage\
│       ├── laws\               # 법령 업로드/수집 원본 파일
│       │   └── annex\          # 법령 별표/서식 다운로드 파일 (PDF/HWP)
│       ├── rules\              # 행정규칙 업로드/수집 원본 파일
│       │   └── annex\          # 행정규칙 별표/서식 다운로드 파일 (PDF/HWP)
│       └── commentary\         # 해양경찰 법령해설(유권해석례) 원본 파일
│
└── static\                     # 프론트엔드 정적 웹 리소스
    ├── index.html              # 홈 메인 화면
    ├── list.html               # 법령/행정규칙/법령해설 목록 화면 (홈 복귀 기능 포함)
    ├── search.html             # 검색 결과 화면
    ├── viewer.html             # [첨부2 뷰어] 새 창 상세 법령 본문 뷰어
    ├── admin.html              # 관리자 파일 업로드 및 관리 대시보드
    ├── css\
    │   ├── theme.css           # [첨부3 컬러] CSS 전역 테마 토큰
    │   ├── main.css            # 공통 헤더/푸터 및 컴포넌트 스타일
    │   ├── list.css            # 목록 및 검색 화면 스타일
    │   └── viewer.css          # 첨부2 2열 뷰어 레이아웃 스타일
    └── js\
        ├── common.js           # 공통 헤더/푸터 및 API 통신 모듈
        ├── main.js             # 홈 화면 인터랙션 및 추천 검색어
        ├── list.js             # 목록 필터링 및 홈 복귀 처리
        ├── search.js           # 검색 결과 렌더링 및 하이라이트
        ├── viewer.js           # 목차 트리 생성, 스크롤 싱크, 화면내 검색
        └── admin.js            # 파일 업로드 및 관리자 기능
```

---

## 4. 모듈별 역할 및 책임 (Module Responsibilities)

### 4.1 백엔드 모듈
1. **`server/main.py`**
   - FastAPI 인스턴스 생성 및 정적 파일 디렉터리(`static/`, `data/storage/`) 마운트
   - REST 엔드포인트 정의:
     - `GET /api/laws`: 목록 조회 (유형별 필터: law, rule, 세부분류)
     - `GET /api/laws/{id}`: 단일 법령 메타데이터 및 조문 상세 트리 조회
     - `GET /api/search`: 통합 키워드 검색 및 스니펫 반환
     - `POST /api/laws/upload`: 관리자 수동 파일 업로드 및 자동 파싱 저장
     - `DELETE /api/laws/{id}`: 법령 및 로컬 파일 삭제
     - `GET /api/stats`: 통계 정보 (등록 법령 수, 행정규칙 수 등)
2. **`server/parser.py`**
   - 텍스트/마크다운 파일에서 법령의 계층 구조를 정규식(`re`)으로 분석:
     - `제\d+장\s+(.+)` : 장(Chapter) 감지
     - `제(\d+)조(?:\(([^)]+)\))?\s*` : 조문 번호 및 제목 추출
     - `부\s*칙` : 부칙 섹션 분리
     - `\[별표\s*\d*\]` : 별표 및 서식 섹션 분리
   - 우측 본문용 HTML 구조화 및 좌측 목차 트리용 JSON 구조체 생성
3. **`server/database.py`**
   - SQLite 테이블(`laws`, `law_sections`, `law_fts`) 초기화
   - 트랜잭션 관리 및 CRUD 작업 수행
4. **`server/search.py`**
   - 사용자 쿼리를 기반으로 제목, 조문 내용 검색
   - 검색어가 포함된 문맥 앞뒤 80자를 추출하여 하이라이트 태그(`<mark>...</mark>`) 삽입

### 4.2 프론트엔드 모듈
1. **`css/theme.css`**
   - 첨부3에서 추출한 5개 컬러 CSS 변수(`--kcg-navy`, `--kcg-steel`, `--kcg-ice`, `--kcg-slate`, `--kcg-white`) 선언
2. **`js/viewer.js`**
   - 첨부2의 국가법령정보센터 2열 뷰어 동작 담당:
     - 좌측 목차 클릭 시 `scrollIntoView({ behavior: 'smooth' })`로 즉시 스크롤
     - 우측 본문 스크롤 시 현재 읽고 있는 조문을 감지하여 좌측 목차 하이라이트 (IntersectionObserver)
     - 화면 내 단어 검색(이전/다음 포커스)
3. **`js/admin.js`**
   - 드래그 앤 드롭 파일 업로드 지원 및 FormData 기반 비동기 업로드

---

## 5. 데이터베이스 스키마 설계 (SQLite)

### 5.1 `laws` (법령 및 행정규칙 기본 정보 테이블)
| 컬럼명 | 타입 | 제약조건 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 고유 식별자 |
| `title` | TEXT | NOT NULL | 법령/규칙명 (예: 해양경찰청 소속 경찰공무원 복제에 관한 규칙) |
| `category` | TEXT | NOT NULL | 대분류 (`law`: 법령, `rule`: 행정규칙) |
| `sub_category` | TEXT | | 세부분류 (`법률`, `대통령령`, `부령`, `훈령`, `예규`, `고시`) |
| `promulgation_no` | TEXT | | 발령번호 (예: 해양수산부령 제696호) |
| `promulgation_date` | TEXT | | 발령일자 (YYYY-MM-DD) |
| `enforcement_date` | TEXT | | 시행일자 (YYYY-MM-DD) |
| `department` | TEXT | | 소관부서 (예: 해양경찰청 장비관리과) |
| `department_phone` | TEXT | | 소관부서 연락처 (예: 032-835-2276) |
| `file_path` | TEXT | | 로컬 저장소 내 파일 상대 경로 |
| `file_name` | TEXT | | 원본 파일명 |
| `raw_content` | TEXT | | 법령 원문 텍스트 |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 등록 일시 |

### 5.2 `law_sections` (조문 및 목차 트리 테이블)
| 컬럼명 | 타입 | 제약조건 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 고유 식별자 |
| `law_id` | INTEGER | FOREIGN KEY REFERENCES laws(id) | 소속 법령 ID |
| `section_type` | TEXT | NOT NULL | 섹션 구분 (`chapter`, `article`, `addenda`, `annex`) |
| `section_no` | TEXT | | 조문 번호 (예: `제1조`, `제2조`, `제1장`) |
| `section_title` | TEXT | | 조문 제목 (예: `목적`, `착용수칙`) |
| `content` | TEXT | NOT NULL | 해당 조문 본문 내용 (항/호 포함) |
| `order_idx` | INTEGER | NOT NULL | 목차 정렬 순번 |
