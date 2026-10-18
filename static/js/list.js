// 목록 화면 스크립트

let currentCategory = "law";
let currentSubCategory = "전체";
let currentSearch = "";

document.addEventListener("DOMContentLoaded", () => {
  // 현재 URL 경로 감지 (/laws vs /rules)
  const path = window.location.pathname;
  const urlParams = new URLSearchParams(window.location.search);
  const typeParam = urlParams.get("type");

  if (path.includes("commentary") || typeParam === "commentary") {
    currentCategory = "commentary";
    document.getElementById("navCommentary")?.classList.add("active");
    document.getElementById("pageTitle").textContent = "법령해설 (법제처 유권해석례) 목록";
    initTabs(["전체", "법령해석례"]);
  } else if (path.includes("rules") || typeParam === "rule") {
    currentCategory = "rule";
    document.getElementById("navRules")?.classList.add("active");
    document.getElementById("pageTitle").textContent = "행정규칙 목록";
    initTabs(["전체", "훈령", "예규", "고시", "부령"]);
  } else {
    currentCategory = "law";
    document.getElementById("navLaws")?.classList.add("active");
    document.getElementById("pageTitle").textContent = "법령 목록";
    initTabs(["전체", "법률", "대통령령", "부령"]);
  }

  // 검색 이벤트 연결
  document.getElementById("btnListSearch").addEventListener("click", doListSearch);
  document.getElementById("listSearchInput").addEventListener("keyup", (e) => {
    if (e.key === "Enter") doListSearch();
  });

  loadList();
});

function initTabs(tabs) {
  const container = document.getElementById("subCategoryTabs");
  container.innerHTML = tabs.map((t, idx) => `
    <button type="button" class="tab-btn ${idx === 0 ? 'active' : ''}" onclick="switchSubTab('${t}', this)">
      ${t}
    </button>
  `).join("");
}

function switchSubTab(sub, btnElem) {
  currentSubCategory = sub;
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  btnElem.classList.add("active");
  loadList();
}

function doListSearch() {
  currentSearch = document.getElementById("listSearchInput").value.trim();
  loadList();
}

async function loadList() {
  const tbody = document.getElementById("lawTableBody");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--kcg-slate);">목록을 조회하는 중입니다...</td></tr>`;

  try {
    let url = `/api/laws?category=${currentCategory}`;
    if (currentSubCategory && currentSubCategory !== "전체") {
      url += `&sub_category=${encodeURIComponent(currentSubCategory)}`;
    }
    if (currentSearch) {
      url += `&q=${encodeURIComponent(currentSearch)}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error("서버 응답 오류");
    const data = await res.json();

    document.getElementById("pageCount").textContent = `총 ${data.length}건`;

    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 3rem; color: var(--kcg-slate);">해당 조건의 법령/행정규칙이 존재하지 않습니다.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map((item, idx) => `
      <tr>
        <td style="text-align: center; color: var(--kcg-slate-dark); font-weight: 600;">${idx + 1}</td>
        <td>${getCategoryBadge(item.category, item.sub_category)}</td>
        <td>
          <div class="law-title-cell" onclick="openViewer(${item.id})">
            <span>${escapeHtml(item.title)}</span>
            <span class="new-window-icon">새 창 ↗</span>
          </div>
        </td>
        <td style="font-size: 13px; color: var(--kcg-slate-dark);">${escapeHtml(item.promulgation_no || '-')}</td>
        <td style="font-size: 13px;">${item.enforcement_date || '-'}</td>
        <td style="font-size: 13px;">${escapeHtml(item.department || '해양경찰청')}</td>
        <td style="text-align: center;">
          <a href="/api/download/${item.id}" title="로컬 저장 원문 다운로드" style="font-size: 16px;">💾</a>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    console.error("목록 조회 실패:", err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: red;">데이터를 불러오는 중 오류가 발생했습니다.</td></tr>`;
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
