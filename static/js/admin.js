// 관리자 화면 스크립트

let adminSearchKeyword = "";
let adminCategoryFilter = "";

document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  setupUploadForm();
  setupSearchAndFilter();
  setupEditModal();
  setupApiSync();
  loadAdminList();
});

function setupApiSync() {
  const btnSync = document.getElementById("btnSyncApi");
  const progressArea = document.getElementById("syncProgressArea");
  const resultArea = document.getElementById("syncResultArea");
  const resultMsg = document.getElementById("syncResultMsg");
  const syncBtnText = document.getElementById("syncBtnText");
  const syncStatusMsg = document.getElementById("syncStatusMsg");
  const syncProgressBar = document.getElementById("syncProgressBar");
  const syncProgressPercent = document.getElementById("syncProgressPercent");

  const lawQueriesInput = document.getElementById("syncLawQueries");
  const ruleQueriesInput = document.getElementById("syncRuleQueries");
  const expcQueriesInput = document.getElementById("syncExpcQueries");
  const scopeSelect = document.getElementById("syncScope");

  if (!btnSync) return;

  let pollTimer = null;

  async function pollStatus() {
    try {
      const sResp = await fetch("/api/sync/status");
      if (!sResp.ok) return;
      const status = await sResp.json();

      if (syncStatusMsg) syncStatusMsg.innerText = status.message || "동기화 진행 중...";

      let percent = 10;
      if (status.step === "collecting_laws") {
        if (status.laws_total > 0) {
          percent = 10 + Math.round((status.laws_done / status.laws_total) * 30);
        }
      } else if (status.step === "collecting_rules") {
        percent = 40;
        if (status.rules_total > 0) {
          percent = 40 + Math.round((status.rules_done / status.rules_total) * 35);
        }
      } else if (status.step === "collecting_commentary") {
        percent = 75;
        if (status.commentary_total > 0) {
          percent = 75 + Math.round((status.commentary_done / status.commentary_total) * 20);
        }
      } else if (status.step === "completed") {
        percent = 100;
      }

      percent = Math.min(percent, 98);
      if (syncProgressBar) syncProgressBar.style.width = `${percent}%`;
      if (syncProgressPercent) syncProgressPercent.innerText = `${percent}%`;
    } catch (e) {
      // ignore transient poll errors
    }
  }

  btnSync.addEventListener("click", async () => {
    const rawLawQ = (lawQueriesInput ? lawQueriesInput.value : "").trim();
    const rawRuleQ = (ruleQueriesInput ? ruleQueriesInput.value : "").trim();
    const rawExpcQ = (expcQueriesInput ? expcQueriesInput.value : "").trim();
    const scopeVal = scopeSelect ? scopeSelect.value : "all";

    const lawQueries = rawLawQ ? rawLawQ.split(",").map(s => s.trim()).filter(Boolean) : ["해양경찰", "해양경찰청", "해양경비", "수상레저", "연안사고", "수색구조"];
    const ruleQueries = rawRuleQ ? rawRuleQ.split(",").map(s => s.trim()).filter(Boolean) : ["해양경찰청", "해양경찰"];
    const expcQueries = rawExpcQ ? rawExpcQ.split(",").map(s => s.trim()).filter(Boolean) : ["해양경찰", "해양경찰청"];
    const limit = scopeVal === "all" ? 0 : parseInt(scopeVal, 10);

    const confirmMsg = scopeVal === "all"
      ? "국가법령정보센터에서 '해양경찰청', '해양경찰' 관련 법령·행정규칙·법령해설 전체를 일괄 수집하시겠습니까? (법령 약 30건 + 행정규칙 328건 + 법령해설 50+건)"
      : `국가법령정보센터에서 법령/행정규칙/법령해설 각 ${limit}건을 테스트 수집하시겠습니까?`;

    if (!confirm(confirmMsg)) return;

    btnSync.disabled = true;
    if (syncBtnText) syncBtnText.innerText = "전체 동기화 진행 중...";
    if (progressArea) progressArea.style.display = "block";
    if (resultArea) resultArea.style.display = "none";
    if (syncProgressBar) syncProgressBar.style.width = "5%";
    if (syncProgressPercent) syncProgressPercent.innerText = "5%";
    if (syncStatusMsg) syncStatusMsg.innerText = "국가법령정보센터 API 연결 및 목록 조회 중...";

    // 800ms 주기로 실시간 진행률 폴링
    pollTimer = setInterval(pollStatus, 800);

    try {
      const resp = await fetch("/api/sync/kcg-laws", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          law_queries: lawQueries,
          rule_queries: ruleQueries,
          expc_queries: expcQueries,
          law_limit: limit,
          rule_limit: limit,
          expc_limit: limit,
          download_annex: true
        })
      });

      clearInterval(pollTimer);
      const data = await resp.json();

      if (syncProgressBar) syncProgressBar.style.width = "100%";
      if (syncProgressPercent) syncProgressPercent.innerText = "100%";
      setTimeout(() => {
        if (progressArea) progressArea.style.display = "none";
      }, 1200);

      btnSync.disabled = false;
      if (syncBtnText) syncBtnText.innerText = "전체 법령·행정규칙·해설 일괄 동기화";

      if (resp.ok && data.status === "success") {
        if (resultArea && resultMsg) {
          resultArea.style.display = "block";
          resultArea.style.background = "#E8F5E9";
          resultArea.style.color = "#2E7D32";

          const lawsCnt = data.db_law_count || data.laws_synced || 0;
          const rulesCnt = data.db_rule_count || data.rules_synced || 0;
          const commsCnt = data.db_commentary_count || data.commentaries_synced || 0;
          const totalCnt = data.db_total_count || data.total_synced || (lawsCnt + rulesCnt + commsCnt);

          resultMsg.innerHTML = `<strong>✅ 전체 동기화 성공!</strong> 해양경찰 법령 <strong>${lawsCnt}건</strong>, 행정규칙 <strong>${rulesCnt}건</strong>, 법령해설 <strong>${commsCnt}건</strong> (총 <strong>${totalCnt}건</strong>)이 로컬 저장소 및 DB에 완벽히 구축되었습니다. (인증키: <code>${data.oc_key}</code>)`;
        }
        loadAdminList();
      } else {
        if (resultArea && resultMsg) {
          resultArea.style.display = "block";
          resultArea.style.background = "#FFEBEE";
          resultArea.style.color = "#C62828";
          resultMsg.innerHTML = `<strong>❌ 동기화 실패:</strong> ${data.detail || "오류가 발생했습니다."}`;
        }
      }
    } catch (err) {
      clearInterval(pollTimer);
      if (progressArea) progressArea.style.display = "none";
      btnSync.disabled = false;
      if (syncBtnText) syncBtnText.innerText = "전체 법령·행정규칙·해설 일괄 동기화";
      if (resultArea && resultMsg) {
        resultArea.style.display = "block";
        resultArea.style.background = "#FFEBEE";
        resultArea.style.color = "#C62828";
        resultMsg.innerHTML = `<strong>❌ 네트워크 오류:</strong> ${err.message}`;
      }
    }
  });
}

function setupSearchAndFilter() {
  const searchInput = document.getElementById("adminSearchInput");
  const btnSearch = document.getElementById("btnAdminSearch");
  const catFilter = document.getElementById("adminFilterCategory");

  if (btnSearch && searchInput) {
    btnSearch.addEventListener("click", () => {
      adminSearchKeyword = searchInput.value.trim();
      loadAdminList();
    });

    searchInput.addEventListener("keyup", (e) => {
      if (e.key === "Enter") {
        adminSearchKeyword = searchInput.value.trim();
        loadAdminList();
      }
    });
  }

  if (catFilter) {
    catFilter.addEventListener("change", (e) => {
      adminCategoryFilter = e.target.value;
      loadAdminList();
    });
  }
}

// ----------------- 스마트 파일명 메타데이터 자동 파서 -----------------
function parseFileNameMetadata(fullFileName) {
  // 확장자 제거
  const nameWithoutExt = fullFileName.replace(/\.[^/.]+$/, "").trim();

  const result = {
    pureTitle: "",
    category: "",
    subCategory: "",
    promulgationNo: "",
    enforcementDate: ""
  };

  // 1. 발령번호 추출 (예: 제00717호, 제250호)
  const promMatch = nameWithoutExt.match(/제\s*0*(\d+)\s*호/);
  if (promMatch) {
    result.promulgationNo = `제${promMatch[1]}호`;
  }

  // 2. 시행일자 추출 (예: 20250117 또는 2025-01-17)
  const dateMatch8 = nameWithoutExt.match(/(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])/);
  if (dateMatch8) {
    const raw = dateMatch8[0];
    result.enforcementDate = `${raw.substring(0, 4)}-${raw.substring(4, 6)}-${raw.substring(6, 8)}`;
  } else {
    const dateMatchHyphen = nameWithoutExt.match(/(?:19|20)\d{2}-\d{2}-\d{2}/);
    if (dateMatchHyphen) {
      result.enforcementDate = dateMatchHyphen[0];
    }
  }

  // 3. 대분류 및 세부분류 자동 판별
  if (nameWithoutExt.includes("해양수산부령") || nameWithoutExt.includes("부령")) {
    result.category = "law";
    result.subCategory = "부령";
    if (result.promulgationNo) result.promulgationNo = `해양수산부령 ${result.promulgationNo}`;
  } else if (nameWithoutExt.includes("대통령령")) {
    result.category = "law";
    result.subCategory = "대통령령";
    if (result.promulgationNo) result.promulgationNo = `대통령령 ${result.promulgationNo}`;
  } else if (nameWithoutExt.includes("법률")) {
    result.category = "law";
    result.subCategory = "법률";
    if (result.promulgationNo) result.promulgationNo = `법률 ${result.promulgationNo}`;
  } else if (nameWithoutExt.includes("훈령")) {
    result.category = "rule";
    result.subCategory = "훈령";
    if (result.promulgationNo) result.promulgationNo = `해양경찰청훈령 ${result.promulgationNo}`;
  } else if (nameWithoutExt.includes("예규")) {
    result.category = "rule";
    result.subCategory = "예규";
    if (result.promulgationNo) result.promulgationNo = `해양경찰청예규 ${result.promulgationNo}`;
  } else if (nameWithoutExt.includes("고시")) {
    result.category = "rule";
    result.subCategory = "고시";
    if (result.promulgationNo) result.promulgationNo = `해양경찰청고시 ${result.promulgationNo}`;
  } else if (nameWithoutExt.includes("해석") || nameWithoutExt.includes("해설")) {
    result.category = "commentary";
    result.subCategory = "법령해석례";
  }

  // 4. 순수 법령명 추출 (괄호 및 대괄호 메타데이터 제거)
  let cleanTitle = nameWithoutExt
    .replace(/\([^)]*\)/g, "")
    .replace(/\[[^\]]*\]/g, "")
    .replace(/_/g, " ")
    .trim();

  // 연속 공백 제거
  cleanTitle = cleanTitle.replace(/\s+/g, " ").trim();
  result.pureTitle = cleanTitle || nameWithoutExt;

  return result;
}

function setupDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileNameDisplay = document.getElementById("selectedFileName");

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      applyParsedFileMetadata(fileInput.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      applyParsedFileMetadata(fileInput.files[0]);
    } else {
      fileNameDisplay.textContent = "";
    }
  });

  function applyParsedFileMetadata(file) {
    const parsed = parseFileNameMetadata(file.name);
    
    fileNameDisplay.innerHTML = `
      <span>선택된 파일: <strong>${escapeHtml(file.name)}</strong> (${(file.size / 1024).toFixed(1)} KB)</span>
      <div style="font-size: 12px; color: #2E7D32; font-weight: normal; margin-top: 3px;">
        ✨ 파일명에서 법령명('<strong>${escapeHtml(parsed.pureTitle)}</strong>')과 메타데이터가 자동 분석되어 적용되었습니다.
      </div>
    `;

    // 1. 파일명 기반으로 법령명 자동 덮어쓰기 (불일치 방지)
    const titleInput = document.getElementById("formTitle");
    if (parsed.pureTitle) {
      titleInput.value = parsed.pureTitle;
    }

    // 2. 대분류 및 세부분류 자동 설정
    if (parsed.category) {
      const catSelect = document.getElementById("formCategory");
      catSelect.value = parsed.category;
    }
    if (parsed.subCategory) {
      const subSelect = document.getElementById("formSubCategory");
      subSelect.value = parsed.subCategory;
    }

    // 3. 발령번호 자동 설정
    if (parsed.promulgationNo) {
      const promInput = document.getElementById("formPromulgationNo");
      promInput.value = parsed.promulgationNo;
    }

    // 4. 시행일자 자동 설정
    if (parsed.enforcementDate) {
      const dateInput = document.getElementById("formEnforcementDate");
      dateInput.value = parsed.enforcementDate;
    }
  }
}

function setupUploadForm() {
  const form = document.getElementById("uploadForm");
  const btnSubmit = document.getElementById("btnSubmit");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById("fileInput");
    if (!fileInput.files || fileInput.files.length === 0) {
      alert("업로드할 파일을 선택해 주세요.");
      return;
    }

    btnSubmit.disabled = true;
    btnSubmit.textContent = "로컬 저장소 저장 및 파싱 중...";

    const formData = new FormData(form);

    try {
      const res = await fetch("/api/laws/upload", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "업로드 실패");
      }

      const result = await res.json();
      alert(`[등록 완료]\n${result.message}\n(조문 파싱: ${result.sections_count}건)\n로컬 저장 위치: ${result.file_path}`);

      // 폼 초기화
      form.reset();
      document.getElementById("selectedFileName").textContent = "";
      loadAdminList();

    } catch (err) {
      alert(`오류 발생: ${err.message}`);
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.textContent = "💾 로컬 디렉터리 저장 및 등록하기";
    }
  });
}

async function loadAdminList() {
  const tbody = document.getElementById("adminTableBody");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem;">목록을 조회하는 중...</td></tr>`;

  try {
    let url = "/api/laws?";
    const params = [];
    if (adminCategoryFilter) params.push(`category=${encodeURIComponent(adminCategoryFilter)}`);
    if (adminSearchKeyword) params.push(`q=${encodeURIComponent(adminSearchKeyword)}`);
    url += params.join("&");

    const res = await fetch(url);
    if (!res.ok) throw new Error("목록 조회 실패");
    const data = await res.json();

    document.getElementById("adminListCount").textContent = `총 ${data.length}건`;

    // 상단 동기화 현황 배지 실시간 업데이트
    try {
      const statsRes = await fetch("/api/stats");
      if (statsRes.ok) {
        const stats = await statsRes.json();
        const bTotal = document.getElementById("statBadgeTotal");
        const bLaw = document.getElementById("statBadgeLaw");
        const bRule = document.getElementById("statBadgeRule");
        const bComm = document.getElementById("statBadgeCommentary");
        const bSec = document.getElementById("statBadgeSec");
        if (bTotal) bTotal.textContent = `총 ${stats.total_count}건`;
        if (bLaw) bLaw.textContent = stats.law_count;
        if (bRule) bRule.textContent = stats.rule_count;
        if (bComm) bComm.textContent = stats.commentary_count || 0;
        if (bSec) bSec.textContent = stats.section_count ? stats.section_count.toLocaleString() : "0";
      }
    } catch (e) {}

    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2.5rem; color: var(--kcg-slate);">검색된 법령/행정규칙이 없습니다.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map(item => `
      <tr class="clickable-row" onclick="handleRowClick(event, ${item.id})">
        <td style="text-align: center; font-weight: 700; color: var(--kcg-slate-dark);">${item.id}</td>
        <td>${getCategoryBadge(item.category, item.sub_category)}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-weight: 700; color: var(--kcg-navy);">${escapeHtml(item.title)}</span>
            <span style="font-size: 11px; color: var(--kcg-steel); background: var(--kcg-ice-light); padding: 1px 5px; border-radius: 3px;">수정 ✎</span>
          </div>
        </td>
        <td style="font-size: 13px;">${item.enforcement_date || '-'}</td>
        <td style="font-size: 13px;">${escapeHtml(item.department || '-')}</td>
        <td style="font-size: 12px; color: var(--kcg-slate-dark); font-family: monospace;">
          ${escapeHtml(item.file_name || '-')}
        </td>
        <td style="text-align: center;" onclick="event.stopPropagation()">
          <button type="button" class="btn-edit" onclick="openEditModal(${item.id})" title="대분류, 세부분류, 법령명 등 수정">
            수정 ✏️
          </button>
          <button type="button" class="btn-header-action" onclick="openViewer(${item.id})" style="background: var(--kcg-steel); font-size: 11px; padding: 4px 7px; margin-right: 4px;" title="본문 새 창 보기">
            보기 ↗
          </button>
          <button type="button" class="btn-danger" onclick="deleteLawItem(${item.id}, '${escapeHtml(item.title)}')">
            삭제
          </button>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    console.error("관리자 목록 로드 오류:", err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: red; padding: 2rem;">목록 로드 실패</td></tr>`;
  }
}

function handleRowClick(event, lawId) {
  openEditModal(lawId);
}

// ----------------- 수정 모달 로직 -----------------

function setupEditModal() {
  const modal = document.getElementById("editModal");
  const btnClose = document.getElementById("btnModalClose");
  const btnCancel = document.getElementById("btnModalCancel");
  const editCategory = document.getElementById("editCategory");
  const editForm = document.getElementById("editForm");
  const btnReplaceFile = document.getElementById("btnReplaceFileAction");

  btnClose.addEventListener("click", closeEditModal);
  btnCancel.addEventListener("click", closeEditModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeEditModal();
  });

  editCategory.addEventListener("change", (e) => {
    updateSubCategoryOptions(e.target.value);
  });

  // 수정 폼 제출
  editForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const lawId = document.getElementById("editLawId").value;
    const btnSave = document.getElementById("btnModalSave");
    btnSave.disabled = true;
    btnSave.textContent = "저장 중...";

    const payload = {
      category: document.getElementById("editCategory").value,
      sub_category: document.getElementById("editSubCategory").value,
      title: document.getElementById("editTitle").value.trim(),
      department: document.getElementById("editDepartment").value.trim(),
      department_phone: document.getElementById("editDepartmentPhone").value.trim(),
      promulgation_no: document.getElementById("editPromulgationNo").value.trim(),
      enforcement_date: document.getElementById("editEnforcementDate").value,
      file_name: document.getElementById("editFileName").value.trim()
    };

    try {
      const res = await fetch(`/api/laws/${lawId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "수정 실패");
      }

      alert("법령 정보 및 파일명이 성공적으로 수정되었습니다.");
      closeEditModal();
      loadAdminList();

    } catch (err) {
      alert(`수정 오류: ${err.message}`);
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = "💾 수정 내용 저장";
    }
  });

  // 새 파일로 교체 업로드 처리
  if (btnReplaceFile) {
    btnReplaceFile.addEventListener("click", async () => {
      const lawId = document.getElementById("editLawId").value;
      const fileInput = document.getElementById("replaceFileInput");
      
      if (!fileInput.files || fileInput.files.length === 0) {
        alert("교체할 새 파일을 선택해 주세요.");
        return;
      }

      const file = fileInput.files[0];
      if (!confirm(`'${file.name}' 파일로 기존 문서를 교체하시겠습니까?`)) {
        return;
      }

      btnReplaceFile.disabled = true;
      btnReplaceFile.textContent = "교체 중...";

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch(`/api/laws/${lawId}/replace-file`, {
          method: "POST",
          body: formData
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "파일 교체 실패");
        }

        const data = await res.json();
        alert(data.message);
        
        // 파일명 필드 업데이트
        document.getElementById("editFileName").value = data.file_name;
        document.getElementById("displayEditFile").textContent = data.file_name;
        fileInput.value = "";
        
        loadAdminList();

      } catch (err) {
        alert(`파일 교체 오류: ${err.message}`);
      } finally {
        btnReplaceFile.disabled = false;
        btnReplaceFile.textContent = "🔄 파일 교체";
      }
    });
  }
}

function updateSubCategoryOptions(category, selectedVal = "") {
  const subSelect = document.getElementById("editSubCategory");
  let options = [];

  if (category === "law") {
    options = ["법률", "대통령령", "부령"];
  } else if (category === "commentary") {
    options = ["법령해석례"];
  } else {
    options = ["훈령", "예규", "고시", "부령"];
  }

  subSelect.innerHTML = options.map(opt => `
    <option value="${opt}" ${opt === selectedVal ? 'selected' : ''}>${opt}</option>
  `).join("");
}

async function openEditModal(lawId) {
  try {
    const res = await fetch(`/api/laws/${lawId}`);
    if (!res.ok) throw new Error("법령 상세 조회 실패");
    const law = await res.json();

    document.getElementById("editLawId").value = law.id;
    document.getElementById("displayEditId").textContent = law.id;
    document.getElementById("displayEditFile").textContent = law.file_name || "없음";
    document.getElementById("editFileName").value = law.file_name || "";

    document.getElementById("editCategory").value = law.category || "law";
    updateSubCategoryOptions(law.category || "law", law.sub_category || "");

    document.getElementById("editTitle").value = law.title || "";
    document.getElementById("editDepartment").value = law.department || "";
    document.getElementById("editDepartmentPhone").value = law.department_phone || "";
    document.getElementById("editPromulgationNo").value = law.promulgation_no || "";
    document.getElementById("editEnforcementDate").value = law.enforcement_date || "";

    // 파일 교체 input 초기화
    const replaceInput = document.getElementById("replaceFileInput");
    if (replaceInput) replaceInput.value = "";

    document.getElementById("editModal").classList.add("show");

  } catch (err) {
    alert(`법령 정보 로드 오류: ${err.message}`);
  }
}

function closeEditModal() {
  document.getElementById("editModal").classList.remove("show");
}

async function deleteLawItem(id, title) {
  if (!confirm(`'${title}' 법령 및 로컬 저장된 파일을 정말로 삭제하시겠습니까?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/laws/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("삭제 처리 실패");
    alert("삭제되었습니다.");
    loadAdminList();
  } catch (err) {
    alert(`삭제 오류: ${err.message}`);
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
