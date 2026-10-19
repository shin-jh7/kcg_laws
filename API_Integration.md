# [API_Integration] 국가법령정보센터 Open API 연동 및 별표/서식 수집 명세서

## 1. 개요
본 문서는 국가법령정보공동활용포털(open.law.go.kr)에서 발급받은 공공 Open API 사용자 인증키를 이용하여, 해양경찰 소관 **법령, 행정규칙(훈령/예규/고시) 및 별표/서식 파일(HWP/PDF)**을 로컬 시스템에 자동으로 수집·적재·동기화하는 아키텍처와 상세 규격을 정의합니다.

---

## 2. 연동 인증 정보 및 기본 사양

| 항목 | 설정 값 / 사양 | 비고 |
| :--- | :--- | :--- |
| **제공 기관** | 법제처 국가법령정보공동활용 (open.law.go.kr) | 공공데이터 법령 정보 API |
| **사용자 인증키 (OC)** | 환경 변수 (`LAW_GO_KR_OC_KEY`) / 기본값 `test` | 국가법령정보공동활용 승인 키 설정 권장 |
| **기본 호출 도메인** | `http://www.law.go.kr` | REST API (HTTP GET) |
| **응답 포맷** | XML (기본) 및 JSON 지원 | 인코딩: UTF-8 |
| **수집 대상 분류** | - 법령 (법률, 대통령령, 해양수산부령)<br>- 행정규칙 (해양경찰청 훈령, 예규, 고시)<br>- 별표 및 법정 서식 첨부 파일<br>- 법령해설 (법제처 해양경찰 법령해석례, `target=expc`) |

---

## 3. Open API 엔드포인트 및 호출 규격

### 3.1 법령 목록 검색 API (`lawSearch.do`)
- **요청 URL**: `http://www.law.go.kr/DRF/lawSearch.do`
- **주요 파라미터**:
  - `OC`: 사용자 인증키 (환경 변수 `LAW_GO_KR_OC_KEY` 또는 `.env`)
  - `target`: `law`
  - `type`: `XML`
  - `display`: 페이지당 건수 (기본 100건 지원)
  - `page`: 페이지 번호 (1, 2, 3...)
  - `query`: 다중 검색어 순회 (`해양경찰`, `해양경찰청`, `해양경비`, `수상레저`, `연안사고`, `수색구조`)
- **자동 수집 정책**:
  - `totalCnt`를 감지하여 모든 페이지를 자동 순회
  - 법령일련번호(`MST`)를 기준으로 고유 식별하여 중복 방지

### 3.2 법령 본문 및 별표/서식 상세 API (`lawService.do`)
- **요청 URL**: `http://www.law.go.kr/DRF/lawService.do`
- **주요 파라미터**:
  - `OC`: 사용자 인증키 (환경 변수 `LAW_GO_KR_OC_KEY` 또는 `.env`)
  - `target`: `law`
  - `MST`: 법령일련번호
  - `type`: `XML`
- **응답 핵심 필드**:
  - `기본정보`: 법령명, 시행일자, 공포번호, 소관부처, 연락처
  - `조문/조문단위`: `조문번호`, `조문제목`, `조문내용`, `항/호/목`
  - `부칙/부칙단위`: `부칙공포일자`, `부칙내용`
  - `별표/별표단위`:
    - `별표구분`: 별표 또는 서식
    - `별표번호`, `별표제목`: 별표 명칭 (예: `[별표 1] 경찰모의 제식`)
    - `별표서식파일링크`: HWP/HWPX 파일 다운로드 상대 경로
    - `별표서식PDF파일링크`: PDF 파일 다운로드 상대 경로

### 3.3 행정규칙 목록 및 상세 API
- **목록 검색**:
  - URL: `http://www.law.go.kr/DRF/lawSearch.do?OC={OC}&target=admrul&type=XML&query={query}&display=100&page={page}`
  - 대상 검색어: `해양경찰청`, `해양경찰` (320여건 전체 순회)
  - 식별자: `행정규칙일련번호`
- **상세 및 별표 조회**:
  - URL: `http://www.law.go.kr/DRF/lawService.do?OC={OC}&target=admrul&ID={행정규칙일련번호}&type=XML`
  - `별표/별표단위/별표파일링크` 및 `별표PDF파일링크` 제공

### 3.4 해양경찰 법령해설(법제처 법령해석례) API (`target=expc`)
- **목록 검색**:
  - URL: `http://www.law.go.kr/DRF/lawSearch.do?OC={OC}&target=expc&type=XML&query={query}&display=100&page={page}`
  - 대상 검색어: `해양경찰`, `해양경찰청` (전체 53건 순회 수집)
  - 식별자: `해석례일련번호` (seq)
  - 인증키 정책: 환경 변수 발급키 우선 시도 후 미승인 시 법제처 오픈 키(`test`)로 자동 폴백(Fallback) 연동
- **상세 본문 조회**:
  - URL: `http://www.law.go.kr/DRF/lawService.do?OC={OC}&target=expc&ID={seq}&type=XML`
  - 응답 핵심 필드 구조화:
    - `안건명`: 법령해설 제명
    - `안건번호`: 발령/안건 번호 (예: `안건번호 19-0044`)
    - `해석일자`: 유권해석 회신 일자
    - `질의기관 / 해석기관`: 질의 및 유권해석 주체
    - `질의요지`: 1. 질의요지 섹션으로 파싱
    - `회답`: 2. 회답 섹션으로 파싱
    - `이유`: 3. 이유(상세 법리적 근거) 섹션으로 파싱
    - `관계법령`: 4. 관련 법령 근거 섹션으로 파싱

---

## 4. 로컬 적재 및 파일 저장 정책

```
c:\antigravity\kcg_laws\
├── server\
│   └── api_sync.py              # 국가법령정보센터 Open API 수집/동기화 모듈
└── data\storage\
    ├── laws\
    │   ├── annex\               # 법령 별표/서식 다운로드 파일 (PDF/HWP)
    │   └── *.txt / *.pdf        # 법령 본문 파일
    ├── rules\
    │   ├── annex\               # 행정규칙 별표/서식 다운로드 파일 (PDF/HWP)
    │   └── *.txt / *.pdf        # 행정규칙 본문 파일
    └── commentary\
        └── *.txt                # 법령해설(유권해석례) 질의요지·회답·이유 본문 파일
```

1. **별표/서식 및 해설 파일 저장**:
   - 별표 다운로드 URL: `http://www.law.go.kr` + `별표파일링크`
   - 저장 위치: `data/storage/laws/annex/`, `data/storage/rules/annex/`, `data/storage/commentary/`
   - 파일명 규격: `{법령ID}_{별표구분}_{별표번호}_{별표명}.pdf` (또는 `.txt`)
2. **데이터베이스 적재 (`kcg_laws.db`)**:
   - `laws` 테이블:
     - `category = 'law'` : 법령 30건
     - `category = 'rule'` : 행정규칙 328건
     - `category = 'commentary'` : 법령해설 53건 (총 411건)
   - `law_sections` 테이블: 총 3,872개 조문 및 섹션 파싱 적재
     - `section_type = 'chapter'` : 장 정보
     - `section_type = 'article'` : 조문 본문 및 질의요지/회답/이유/관계법령
     - `section_type = 'addenda'` : 부칙 본문
     - `section_type = 'annex'`   : 별표/서식 (로컬 파일 링크 및 별표 제목 연동)

---

## 5. 실행 및 동기화 방안

1. **독립 CLI 실행**:
   ```powershell
   # 법령, 행정규칙, 법령해설 전체 자동 수집
   python -m server.api_sync
   ```
2. **관리자 웹 화면 연동**:
   - 관리자 페이지(`admin.html`)에 **[🔄 전체 법령·행정규칙·해설 일괄 동기화]** 제공
   - 법령/행정규칙/법령해설 검색어를 각각 커스터마이징하여 백그라운드 원클릭 동기화 지원
   - 실시간 진행 상태바 및 완료 건수 집계 표시
