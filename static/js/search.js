// 검색 결과 화면 스크립트

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const query = urlParams.get("q") || "";
  const category = urlParams.get("category") || "";

  document.getElementById("displayKeyword").textContent = query;
  document.getElementById("reSearchInput").value = query;

  document.getElementById("btnReSearch").addEventListener("click", () => {
    const newQ = document.getElementById("reSearchInput").value.trim();
    if (newQ) {
      window.location.href = `/search?q=${encodeURIComponent(newQ)}`;
    }
  });

  document.getElementById("reSearchInput").addEventListener("keyup", (e) => {
    if (e.key === "Enter") {
      const newQ = document.getElementById("reSearchInput").value.trim();
      if (newQ) {
        window.location.href = `/search?q=${encodeURIComponent(newQ)}`;
      }
    }
  });

  if (query) {
    executeSearch(query, category);
  } else {
    document.getElementById("searchResultsContainer").innerHTML = `
      <div style="text-align: center; padding: 3rem; color: var(--kcg-slate);">
        검색어를 입력해 주세요.
      </div>
    `;
  }
});

async function executeSearch(query, category) {
  const container = document.getElementById("searchResultsContainer");
  container.innerHTML = `<div style="text-align: center; padding: 3rem; color: var(--kcg-slate);">검색 결과를 조회 중입니다...</div>`;

  try {
    let url = `/api/search?q=${encodeURIComponent(query)}`;
    if (category) {
      url += `&category=${encodeURIComponent(category)}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error("검색 API 오류");
    const data = await res.json();

    document.getElementById("searchResultCount").textContent = `총 ${data.count}건`;

    if (data.results.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 4rem; background: white; border: 1px solid var(--kcg-ice); border-radius: var(--radius-md);">
          <div style="font-size: 36px; margin-bottom: 10px;">🔍</div>
          <h3 style="color: var(--kcg-navy); margin-bottom: 8px;">검색 결과가 없습니다.</h3>
          <p style="color: var(--kcg-slate-dark); font-size: 14px;">입력하신 단어('<strong>${escapeHtml(query)}</strong>')와 일치하는 법령 또는 조문 내용이 없습니다.<br>단어의 철자를 확인하거나 다른 검색어로 다시 검색해 보세요.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = data.results.map(item => {
      const snippetsHtml = item.matched_sections && item.matched_sections.length > 0 
        ? `
          <div class="result-snippets">
            ${item.matched_sections.slice(0, 3).map(s => `
              <div class="snippet-item">
                <span class="snippet-sec-name">[${escapeHtml(s.section_display)}]</span>
                <span>${s.snippet}</span>
              </div>
            `).join("")}
            ${item.matched_sections.length > 3 ? `<div style="font-size: 12px; color: var(--kcg-steel); margin-top: 4px;">외 ${item.matched_sections.length - 3}개 조문 일치...</div>` : ''}
          </div>
        ` 
        : (item.title_matched ? `<div class="result-snippets"><div class="snippet-item" style="color: var(--kcg-steel-dark);">법령 제명(제목)에 검색어가 포함되어 있습니다.</div></div>` : '');

      return `
        <div class="search-result-card">
          <div class="result-header">
            <div>
              ${getCategoryBadge(item.category, item.sub_category)}
              <div class="result-title" onclick="openViewer(${item.law_id})" style="margin-left: 6px;">
                <span>${item.highlighted_title || escapeHtml(item.title)}</span>
                <span class="new-window-icon">새 창 본문 열기 ↗</span>
              </div>
            </div>
          </div>

          <div class="result-meta">
            <span><strong>발령번호:</strong> ${escapeHtml(item.promulgation_no || '-')}</span>
            <span><strong>시행일자:</strong> ${item.enforcement_date || '-'}</span>
            <span><strong>소관부서:</strong> ${escapeHtml(item.department || '해양경찰청')}</span>
          </div>

          ${snippetsHtml}
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("검색 실패:", err);
    container.innerHTML = `<div style="text-align: center; padding: 2rem; color: red;">검색 중 오류가 발생했습니다.</div>`;
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
