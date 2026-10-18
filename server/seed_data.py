import os
from .database import init_db, insert_law, get_connection
from .parser import parse_law_text

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LAWS_DIR = os.path.join(BASE_DIR, "data", "storage", "laws")
RULES_DIR = os.path.join(BASE_DIR, "data", "storage", "rules")

def seed_sample_data():
    os.makedirs(LAWS_DIR, exist_ok=True)
    os.makedirs(RULES_DIR, exist_ok=True)
    init_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM laws")
    count = cursor.fetchone()[0]
    conn.close()

    if count > 0:
        print(f"[Seed] 이미 {count}건의 법령/규칙 데이터가 존재합니다. 시딩을 건너뜁니다.")
        return

    print("[Seed] 초기 샘플 법령 및 행정규칙 데이터 등록을 시작합니다...")

    samples = [
        # 1. 첨부2에 등장한 대표 규칙: 해양경찰청 소속 경찰공무원 복제에 관한 규칙
        {
            "category": "rule",
            "sub_category": "부령",
            "title": "해양경찰청 소속 경찰공무원 복제에 관한 규칙",
            "promulgation_no": "해양수산부령 제696호",
            "promulgation_date": "2024-10-21",
            "enforcement_date": "2024-10-21",
            "department": "해양경찰청 (장비관리과)",
            "department_phone": "032-835-2276",
            "file_name": "해양경찰청_소속_경찰공무원_복제에_관한_규칙.txt",
            "storage_sub": "rules",
            "content": """해양경찰청 소속 경찰공무원 복제에 관한 규칙
[시행 2024. 10. 21.] [해양수산부령 제696호, 2024. 10. 21., 일부개정]
해양경찰청 (장비관리과), 032-835-2276

제1장 총칙

제1조(목적) 이 규칙은 「경찰공무원법」 제25조제3항에 따른 해양경찰청 및 그 소속기관의 경찰공무원의 복제(服制: 제복 규격과 그 착용에 관한 사항)를 규정함을 목적으로 한다.

제2조(착용수칙) ① 해양경찰청 및 그 소속기관의 경찰공무원(이하 "경찰공무원"이라 한다)은 이 규칙에서 정하는 바에 따라 경찰공무원의 제복(이하 "경찰제복"이라 한다)을 착용해야 한다.
② 경찰공무원은 복장과 용모를 단정히 하고, 항상 품위를 유지해야 한다.

제2장 경찰제복의 종류 및 제식

제3조(경찰제복의 구분) 경찰제복은 정복, 근무복, 기동복, 점퍼, 외투 및 그 부속물로 구분하고, 그 밖의 제복은 해양경찰청장이 정할 수 있다.

제4조(경찰모) 경찰모는 정모 및 근무모로 구분하며, 그 도형ㆍ제식 등은 별표 1과 같다.

제5조(경찰복) 경찰복은 다음 각 호와 같이 구분하고, 그 도형ㆍ제식 등은 별표 2와 같다.
1. 정복
2. 근무복
3. 기동복
4. 점퍼
5. 외투

제6조(부속물 및 특수복 등) ① 경찰제복의 부속물은 계급장, 명찰, 흉장 및 넥타이 등으로 한다.
② 특수임무를 수행하는 함정 요원 및 특공대 요원의 특수복 제식은 해양경찰청장이 따로 정한다.

제3장 보칙

제7조(착용기간) 하절기 근무복 착용기간은 6월 1일부터 9월 30일까지로 하며, 기후 조건에 따라 소속기관의 장이 조정할 수 있다.

부칙 <제696호, 2024. 10. 21.>
이 규칙은 공포한 날부터 시행한다.

[별표 1] 경찰모의 제식 및 형상 (정모 및 근무모 구분)
[별표 2] 경찰복의 제식 및 색상 (정복, 근무복, 기동복의 색상 규격)
"""
        },
        # 2. 해양경비법 (법령 - 법률)
        {
            "category": "law",
            "sub_category": "법률",
            "title": "해양경비법",
            "promulgation_no": "법률 제18985호",
            "promulgation_date": "2023-01-03",
            "enforcement_date": "2023-07-04",
            "department": "해양경찰청 (경비과)",
            "department_phone": "032-835-2151",
            "file_name": "해양경비법.txt",
            "storage_sub": "laws",
            "content": """해양경비법
[시행 2023. 7. 4.] [법률 제18985호, 2023. 1. 3., 일부개정]
해양경찰청 (경비과), 032-835-2151

제1장 총칙

제1조(목적) 이 법은 해양에서의 경찰작전, 해상대간첩작전, 치안질서의 유지, 해상수색 및 구조, 해양환경의 보전 등 해양경비에 필요한 사항을 규정함으로써 해양주권을 수호하고 국민의 생명과 재산을 보호함을 목적으로 한다.

제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
1. "해양"이란 「영해 및 접속수역법」에 따른 내수(내수면은 제외한다), 영해 및 접속수역과 「배타적 경제수역 및 대륙붕법」에 따른 배타적 경제수역 및 대륙붕을 말한다.
2. "해양경비"란 해양경찰관이 해양에서의 안전과 질서를 유지하기 위하여 행하는 경비활동을 말한다.

제2장 해양경비활동

제3조(해양경비계획의 수립) 해양경찰청장은 관할 해역의 특성을 고려하여 종합적인 해양경비계획을 수립ㆍ시행하여야 한다.

제4조(선박의 검문검색) ① 해양경찰관은 해양경비 임무를 수행하기 위하여 필요한 경우 수상한 선박에 대하여 정선(停船)명령 및 승선ㆍ검문검색을 실시할 수 있다.
② 제1항에 따른 검문검색 대상 선박의 선장 또는 승무원은 정당한 사유 없이 이에 불응하거나 방해하여서는 아니 된다.

제5조(무기의 사용) 해양경찰관은 범인의 체포, 도주의 방지, 자기 또는 타인의 생명ㆍ신체의 방어 및 정당한 직무집행에 대한 저항의 억제를 위하여 필요한 상당한 이유가 있을 때에는 경찰관 직무집행법이 정하는 바에 따라 무기를 사용할 수 있다.

부칙 <제18985호, 2023. 1. 3.>
이 법은 공포 후 6개월이 경과한 날부터 시행한다.
"""
        },
        # 3. 수상레저안전법 (법령 - 법률)
        {
            "category": "law",
            "sub_category": "법률",
            "title": "수상레저안전법",
            "promulgation_no": "법률 제19420호",
            "promulgation_date": "2023-05-16",
            "enforcement_date": "2024-05-17",
            "department": "해양경찰청 (수상레저과)",
            "department_phone": "032-835-2153",
            "file_name": "수상레저안전법.txt",
            "storage_sub": "laws",
            "content": """수상레저안전법
[시행 2024. 5. 17.] [법률 제19420호, 2023. 5. 16., 전부개정]
해양경찰청 (수상레저과), 032-835-2153

제1장 총칙

제1조(목적) 이 법은 수상레저활동의 안전과 질서를 확보하고 수상레저사업의 건전한 발전을 도모함을 목적으로 한다.

제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
1. "수상레저활동"이란 수상(水上)에서 수상레저기구를 이용하여 취미ㆍ오락ㆍ스포츠 등을 즐기는 활동을 말한다.
2. "수상레저기구"란 수상레저활동에 이용되는 모터보트, 세일링요트, 수상오토바이, 고무보트, 패들보드 등을 말한다.

제2장 조종면허 및 안전운항

제3조(조종면허) 동력수상레저기구를 조종하려는 자는 해양경찰청장이 실시하는 조종면허시험에 합격하여 조종면허를 받아야 한다.

제4조(주취운항 금지) 수상레저기구의 조종자는 혈중알코올농도 0.03퍼센트 이상의 상태에서 수상레저기구를 조종하여서는 아니 된다.

부칙 <제19420호, 2023. 5. 16.>
이 법은 공포 후 1년이 경과한 날부터 시행한다.
"""
        },
        # 4. 해양경찰청 함정 운용관리 규칙 (행정규칙 - 훈령)
        {
            "category": "rule",
            "sub_category": "훈령",
            "title": "해양경찰청 함정 운용관리 규칙",
            "promulgation_no": "해양경찰청훈령 제245호",
            "promulgation_date": "2024-03-15",
            "enforcement_date": "2024-03-15",
            "department": "해양경찰청 (경비과)",
            "department_phone": "032-835-2152",
            "file_name": "해양경찰청_함정_운용관리_규칙.txt",
            "storage_sub": "rules",
            "content": """해양경찰청 함정 운용관리 규칙
[시행 2024. 3. 15.] [해양경찰청훈령 제245호, 2024. 3. 15., 일부개정]
해양경찰청 (경비과), 032-835-2152

제1장 총칙

제1조(목적) 이 규칙은 해양경찰청 소속 경비함정의 효율적인 운용과 정비 및 관리에 필요한 사항을 규정하여 해상치안 임무의 완벽한 수행을 도모함을 목적으로 한다.

제2조(적용범위) 해양경찰청 및 소속기관에서 운용하는 모든 경비함정, 특수정, 방제정 등에 대하여 적용한다.

제2장 함정 출동 및 당직

제3조(출동태세 확립) 함정의 장은 항상 즉각 출동할 수 있는 태세를 유지하여야 하며, 무기, 통신장비, 구명의 등 안전장비를 상시 점검하여야 한다.

제4조(해상당직) 항해 중 또는 정박 중 함정에는 필수 당직근무자를 배치하여 당직근무를 철저히 이행하여야 한다.

부칙 <제245호, 2024. 3. 15.>
이 규칙은 발령한 날부터 시행한다.
"""
        },
        # 5. 해양오염방제 자재 및 약제 운용 관리 규칙 (행정규칙 - 예규)
        {
            "category": "rule",
            "sub_category": "예규",
            "title": "해양오염방제 자재 및 약제 운용 관리 규칙",
            "promulgation_no": "해양경찰청예규 제118호",
            "promulgation_date": "2023-11-20",
            "enforcement_date": "2023-11-20",
            "department": "해양경찰청 (방제기획과)",
            "department_phone": "032-835-2391",
            "file_name": "해양오염방제_자재_및_약제_운용_관리_규칙.txt",
            "storage_sub": "rules",
            "content": """해양오염방제 자재 및 약제 운용 관리 규칙
[시행 2023. 11. 20.] [해양경찰청예규 제118호, 2023. 11. 20., 일부개정]
해양경찰청 (방제기획과), 032-835-2391

제1장 총칙

제1조(목적) 이 규칙은 해양에 배출된 기름 등 오염물질을 방제하기 위하여 보유하는 자재 및 약제의 효율적인 비축, 보관, 사용 및 관리에 필요한 기준을 정함을 목적으로 한다.

제2조(비축기준) 해양경찰서장은 관할 해역의 유류물동량 및 사고 발생 위험도를 고려하여 오일펜스, 유흡착재, 유처리제 등의 방제자재를 기준량 이상 상시 비축하여야 한다.

제3조(자재의 점검) 방제자재는 매월 1회 이상 정기점검을 실시하여 이상 유무를 확인하여야 한다.

부칙 <제118호, 2023. 11. 20.>
이 예규는 발령한 날부터 시행한다.
"""
        },
        # 6. 수상구조사 양성기관 지정 및 관리 규정 (행정규칙 - 고시)
        {
            "category": "rule",
            "sub_category": "고시",
            "title": "수상구조사 양성기관 지정 및 관리 규정",
            "promulgation_no": "해양경찰청고시 제2024-5호",
            "promulgation_date": "2024-01-10",
            "enforcement_date": "2024-01-10",
            "department": "해양경찰청 (수색구조과)",
            "department_phone": "032-835-2161",
            "file_name": "수상구조사_양성기관_지정_및_관리_규정.txt",
            "storage_sub": "rules",
            "content": """수상구조사 양성기관 지정 및 관리 규정
[시행 2024. 1. 10.] [해양경찰청고시 제2024-5호, 2024. 1. 10., 일부개정]
해양경찰청 (수색구조과), 032-835-2161

제1조(목적) 이 고시는 「수상에서의 수색 및 구조 등에 관한 법률」 제30조의2에 따라 수상구조사 양성기관의 지정기준, 지정절차 및 사후관리 등에 관하여 필요한 사항을 정함을 목적으로 한다.

제2조(지정요건) 수상구조사 양성기관으로 지정받으려는 자는 규격에 적합한 실내수영장 및 강의실, 수상구조용 마네킹, AED 등 교육장비와 전담 교수요원을 갖추어야 한다.

제3조(교육과정) 양성기관은 영법, 응급처치, 구조장비 운용 등 64시간 이상의 법정 교육과정을 편성하여 운영하여야 한다.

부칙 <제2024-5호, 2024. 1. 10.>
이 고시는 고시한 날부터 시행한다.
"""
        }
    ]

    for item in samples:
        # 파일 로컬 저장소에 저장
        target_dir = LAWS_DIR if item["storage_sub"] == "laws" else RULES_DIR
        file_path = os.path.join(target_dir, item["file_name"])
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(item["content"])

        rel_path = os.path.relpath(file_path, BASE_DIR)
        meta, sections = parse_law_text(item["content"], default_title=item["title"])

        law_data = {
            "title": item["title"],
            "category": item["category"],
            "sub_category": item["sub_category"],
            "promulgation_no": item["promulgation_no"] or meta.get("promulgation_no"),
            "promulgation_date": item["promulgation_date"],
            "enforcement_date": item["enforcement_date"] or meta.get("enforcement_date"),
            "department": item["department"] or meta.get("department"),
            "department_phone": item["department_phone"] or meta.get("department_phone"),
            "file_path": rel_path,
            "file_name": item["file_name"],
            "raw_content": item["content"]
        }
        
        law_id = insert_law(law_data, sections)
        print(f"  - 등록 완료 (ID: {law_id}): [{item['sub_category']}] {item['title']} (조문 수: {len(sections)})")

    print("[Seed] 초기 샘플 데이터 등록이 완료되었습니다.")

if __name__ == "__main__":
    seed_sample_data()
