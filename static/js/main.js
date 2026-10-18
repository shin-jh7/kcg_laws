// 홈 화면 데이터 로드 및 초기화

document.addEventListener("DOMContentLoaded", async () => {
  loadStats();
  loadQuickLists();
});

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("statTotal").textContent = data.total_count || 0;
    document.getElementById("statLaws").textContent = data.law_count || 0;
    document.getElementById("statRules").textContent = data.rule_count || 0;
    const commEl = document.getElementById("statCommentaries");
    if (commEl) commEl.textContent = data.commentary_count || 0;
    document.getElementById("statSections").textContent = data.section_count || 0;
  } catch (err) {
    console.error("통계 로드 실패:", err);
  }
}

async function loadQuickLists() {
  try {
    // 1. 법령 목록 (상위 5건)
    const lawRes = await fetch("/api/laws?category=law");
    if (lawRes.ok) {
      const laws = await lawRes.json();
      renderCardList("mainLawsList", laws.slice(0, 5));
    }

    // 2. 행정규칙 목록 (상위 5건)
    const ruleRes = await fetch("/api/laws?category=rule");
    if (ruleRes.ok) {
      const rules = await ruleRes.json();
      renderCardList("mainRulesList", rules.slice(0, 5));
    }

    // 3. 법령해설 목록 (상위 5건)
    const commRes = await fetch("/api/laws?category=commentary");
    if (commRes.ok) {
      const comms = await commRes.json();
      renderCardList("mainCommentaryList", comms.slice(0, 5));
    }
  } catch (err) {
    console.error("목록 로드 실패:", err);
  }
}

function renderCardList(targetId, items) {
  const container = document.getElementById(targetId);
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = '<li class="card-item"><span class="card-item-title" style="color:var(--kcg-slate);">등록된 내역이 없습니다.</span></li>';
    return;
  }

  container.innerHTML = items.map(item => `
    <li class="card-item">
      <span class="card-item-title" onclick="openViewer(${item.id})">
        ${getCategoryBadge(item.category, item.sub_category)}
        <span>${escapeHtml(item.title)}</span>
      </span>
      <span class="card-item-meta">${item.enforcement_date ? '시행 ' + item.enforcement_date : ''}</span>
    </li>
  `).join("");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
