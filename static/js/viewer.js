// 첨부2 국가법령정보센터 스타일 상세 뷰어 스크립트

let currentLaw = null;
let currentFontSize = 15;
let searchMatches = [];
let currentMatchIdx = -1;

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const lawId = urlParams.get("id");

  if (!lawId) {
    alert("열람할 법령 ID가 지정되지 않았습니다.");
    return;
  }

  loadLawDetail(lawId);

  // 이벤트 핸들러 바인딩
  document.getElementById("btnFontUp").addEventListener("click", () => changeFontSize(1));
  document.getElementById("btnFontDown").addEventListener("click", () => changeFontSize(-1));

  document.getElementById("inPageSearchInput").addEventListener("input", handleInPageSearch);
  document.getElementById("inPageSearchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      if (e.shiftKey) navigateMatch(-1);
      else navigateMatch(1);
    }
  });

  document.getElementById("btnPrevMatch").addEventListener("click", () => navigateMatch(-1));
  document.getElementById("btnNextMatch").addEventListener("click", () => navigateMatch(1));

  document.getElementById("articleQuickSelect").addEventListener("change", (e) => {
    if (e.target.value) {
      scrollToSection(e.target.value);
    }
  });
});

async function loadLawDetail(lawId) {
  try {
    const res = await fetch(`/api/laws/${lawId}`);
    if (!res.ok) throw new Error("법령 상세 조회 실패");
    const law = await res.json();
    currentLaw = law;

    renderViewer(law);
  } catch (err) {
    console.error("법령 상세 로드 실패:", err);
    document.getElementById("bannerLawTitle").textContent = "법령을 불러올 수 없습니다.";
  }
}

function renderViewer(law) {
  // 문서 타이틀 변경
  document.title = `${law.title} - 해양경찰 법령정보센터`;

  // 1. 헤더 업데이트
  document.getElementById("viewerCategoryBadge").textContent = law.sub_category || (law.category === "law" ? "법령" : "행정규칙");
  document.getElementById("viewerLawTitleHeader").textContent = law.title;
  document.getElementById("bannerLawTitle").textContent = law.title;

  // 메타 배너
  let metaHtml = "";
  if (law.enforcement_date) metaHtml += `[시행 ${law.enforcement_date}] `;
  if (law.promulgation_no) metaHtml += `[${law.promulgation_no}] `;
  document.getElementById("bannerMeta").textContent = metaHtml.trim();

  let deptHtml = "";
  if (law.department) deptHtml += `소관부서: ${law.department} `;
  if (law.department_phone) deptHtml += `, ${law.department_phone}`;
  document.getElementById("bannerDept").textContent = deptHtml.trim();

  // 원본 다운로드 버튼 연동
  document.getElementById("btnDownloadOriginal").onclick = () => {
    window.location.href = `/api/download/${law.id}`;
  };

  // PDF 전용 탭 전환 지원
  const tabTextMode = document.getElementById("tabTextMode");
  const tabPdfMode = document.getElementById("tabPdfMode");
  const paperSheet = document.getElementById("paperSheetContainer");
  const pdfContainer = document.getElementById("pdfViewerContainer");
  const pdfIframe = document.getElementById("pdfIframe");

  const isPdf = law.file_name && law.file_name.toLowerCase().endsWith(".pdf");
  if (isPdf && tabPdfMode) {
    tabPdfMode.style.display = "inline-block";
    tabPdfMode.onclick = () => {
      tabTextMode.classList.remove("active");
      tabPdfMode.classList.add("active");
      if (paperSheet) paperSheet.style.display = "none";
      if (pdfContainer) {
        pdfContainer.style.display = "block";
        if (!pdfIframe.src || pdfIframe.src === "about:blank" || !pdfIframe.src.includes(`/api/pdf/${law.id}`)) {
          pdfIframe.src = `/api/pdf/${law.id}`;
        }
      }
    };
    tabTextMode.onclick = () => {
      tabPdfMode.classList.remove("active");
      tabTextMode.classList.add("active");
      if (pdfContainer) pdfContainer.style.display = "none";
      if (paperSheet) paperSheet.style.display = "block";
    };
  } else if (tabPdfMode) {
    tabPdfMode.style.display = "none";
  }

  // 2. 좌측 목차(TOC) 및 우측 본문 렌더링
  const tocList = document.getElementById("tocList");
  const bodyContainer = document.getElementById("lawBodyContainer");
  const selectBox = document.getElementById("articleQuickSelect");

  tocList.innerHTML = "";
  bodyContainer.innerHTML = "";
  selectBox.innerHTML = '<option value="">조문선택</option>';

  const sections = law.sections || [];

  sections.forEach((sec, idx) => {
    const secId = `sec-${idx}`;
    const secType = sec.section_type;
    const secNo = sec.section_no || "";
    const secTitle = sec.section_title || "";

    // A. 목차(TOC) 아이템 생성
    const li = document.createElement("li");
    li.className = "toc-node";

    if (secType === "chapter") {
      li.className += " toc-item-chapter";
      li.textContent = `${secNo} ${secTitle}`.trim();
    } else {
      const a = document.createElement("a");
      a.className = "toc-item-link";
      a.href = `#${secId}`;
      a.id = `toc-link-${secId}`;

      if (secType === "article") {
        a.className += " toc-item-article";
        if (law.category === "commentary" || (secNo && secNo.endsWith("."))) {
          a.textContent = `${secNo} ${secTitle}`.trim();
        } else {
          a.textContent = secTitle ? `${secNo}(${secTitle})` : secNo;
        }

        // 조문 셀렉트 옵션 추가
        const opt = document.createElement("option");
        opt.value = secId;
        opt.textContent = a.textContent;
        selectBox.appendChild(opt);
      } else if (secType === "addenda") {
        a.className += " toc-item-addenda";
        a.textContent = "부칙";
      } else if (secType === "annex") {
        a.className += " toc-item-annex";
        a.textContent = secNo || "별표·서식";
      }

      a.addEventListener("click", (e) => {
        e.preventDefault();
        scrollToSection(secId);
      });
      li.appendChild(a);
    }
    tocList.appendChild(li);

    // B. 우측 본문 블록 생성
    const block = document.createElement("div");
    block.id = secId;

    if (secType === "chapter") {
      block.className = "law-chapter-block";
      block.textContent = `${secNo} ${secTitle}`.trim();
    } else if (secType === "addenda") {
      block.className = "law-addenda-block";
      block.innerHTML = `
        <div class="section-box-title">부칙</div>
        <div class="article-paragraphs">${formatBodyLines(sec.content)}</div>
      `;
    } else if (secType === "annex") {
      block.className = "law-annex-block";
      block.innerHTML = `
        <div class="section-box-title">${escapeHtml(secNo)} ${escapeHtml(secTitle)}</div>
        <div class="article-paragraphs">${formatBodyLines(sec.content)}</div>
      `;
    } else {
      // 일반 조문 (Article) 또는 법령해설 섹션
      block.className = "law-article-block";

      if (law.category === "commentary") {
        block.innerHTML = `
          <div style="margin-bottom: 10px; border-bottom: 1px dashed var(--kcg-ice-dark); padding-bottom: 6px;">
            <span class="article-no-title" style="color: #D97706; font-size: 16px; font-weight: 700;">
              💡 【${escapeHtml(secNo)} ${escapeHtml(secTitle)}】
            </span>
          </div>
          <div class="article-paragraphs" style="white-space: pre-wrap; line-height: 1.85; font-size: inherit; color: var(--kcg-text-main);">
            ${escapeHtml(sec.content)}
          </div>
        `;
      } else {
        const headText = secTitle ? `${secNo}(${secTitle})` : secNo;
        
        // 본문 텍스트에서 첫 줄(조문 제목) 이후 항/호 분리
        const lines = sec.content.split("\n");
        const firstLine = lines[0] || "";
        const remainingLines = lines.slice(1);

        // 첫 줄에서 제O조(제목) 부분 이후 텍스트 추출
        let firstBodyText = firstLine;
        if (firstLine.startsWith(secNo)) {
          firstBodyText = firstLine.replace(secNo, "").trim();
          if (secTitle && firstBodyText.startsWith(`(${secTitle})`)) {
            firstBodyText = firstBodyText.replace(`(${secTitle})`, "").trim();
          }
        }

        let contentHtml = `
          <div>
            <span class="article-no-title">${escapeHtml(headText)}</span>
            <span class="article-content-text">${escapeHtml(firstBodyText)}</span>
          </div>
        `;

        if (remainingLines.length > 0) {
          contentHtml += `
            <div class="article-paragraphs">
              ${formatBodyLines(remainingLines.join("\n"))}
            </div>
          `;
        }

        block.innerHTML = contentHtml;
      }
    }

    bodyContainer.appendChild(block);
  });
}

function formatBodyLines(text) {
  if (!text) return "";
  return text.split("\n").map(line => {
    line = line.trim();
    if (!line) return "";
    
    // ①, ② 등 항 번호 처리
    if (/^[①-⑳]/.test(line)) {
      return `<div class="law-paragraph-row">${escapeHtml(line)}</div>`;
    }
    // 1., 2. 등 호 번호 처리
    if (/^\d+\./.test(line)) {
      return `<div class="law-subitem-row">${escapeHtml(line)}</div>`;
    }
    return `<div>${escapeHtml(line)}</div>`;
  }).join("");
}

function scrollToSection(secId) {
  const target = document.getElementById(secId);
  if (!target) return;

  target.scrollIntoView({ behavior: "smooth", block: "start" });

  // 좌측 TOC 하이라이트 동기화
  document.querySelectorAll(".toc-item-link").forEach(el => el.classList.remove("active"));
  const tocLink = document.getElementById(`toc-link-${secId}`);
  if (tocLink) tocLink.classList.add("active");

  // 타겟 섹션 일시적 강조
  target.classList.add("active-target");
  setTimeout(() => {
    target.classList.remove("active-target");
  }, 1800);
}

function changeFontSize(delta) {
  currentFontSize = Math.max(12, Math.min(24, currentFontSize + delta));
  const container = document.getElementById("lawBodyContainer");
  container.style.fontSize = `${currentFontSize}px`;
}

// 화면 내 단어 검색 핸들러
function handleInPageSearch(e) {
  const term = e.target.value.trim();
  const countLabel = document.getElementById("searchMatchCount");
  
  // 기존 하이라이트 복원
  clearInPageSearchHighlights();
  searchMatches = [];
  currentMatchIdx = -1;

  if (!term || term.length < 1) {
    countLabel.textContent = "";
    return;
  }

  // 본문 내 텍스트 노드 탐색 및 하이라이트
  const container = document.getElementById("lawBodyContainer");
  highlightTextNodes(container, term);

  searchMatches = Array.from(document.querySelectorAll(".in-page-highlight"));
  countLabel.textContent = `${searchMatches.length}건`;

  if (searchMatches.length > 0) {
    navigateMatch(1);
  }
}

function highlightTextNodes(element, term) {
  const regex = new RegExp(`(${escapeRegExp(term)})`, "gi");
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
  const textNodes = [];

  while (walker.nextNode()) {
    textNodes.push(walker.currentNode);
  }

  textNodes.forEach(node => {
    if (!node.nodeValue.match(regex)) return;
    const parent = node.parentNode;
    if (parent && parent.classList && parent.classList.contains("in-page-highlight")) return;

    const frag = document.createDocumentFragment();
    const parts = node.nodeValue.split(regex);

    parts.forEach(part => {
      if (part.toLowerCase() === term.toLowerCase()) {
        const mark = document.createElement("mark");
        mark.className = "in-page-highlight";
        mark.style.backgroundColor = "#FFEB3B";
        mark.style.color = "#000";
        mark.textContent = part;
        frag.appendChild(mark);
      } else if (part) {
        frag.appendChild(document.createTextNode(part));
      }
    });

    if (parent) {
      parent.replaceChild(frag, node);
    }
  });
}

function clearInPageSearchHighlights() {
  document.querySelectorAll(".in-page-highlight").forEach(mark => {
    const parent = mark.parentNode;
    if (parent) {
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    }
  });
}

function navigateMatch(direction) {
  if (searchMatches.length === 0) return;

  if (currentMatchIdx >= 0 && currentMatchIdx < searchMatches.length) {
    searchMatches[currentMatchIdx].style.backgroundColor = "#FFEB3B";
  }

  currentMatchIdx = (currentMatchIdx + direction + searchMatches.length) % searchMatches.length;
  const currentElem = searchMatches[currentMatchIdx];

  currentElem.style.backgroundColor = "#FF9800";
  currentElem.scrollIntoView({ behavior: "smooth", block: "center" });

  document.getElementById("searchMatchCount").textContent = `${currentMatchIdx + 1}/${searchMatches.length}`;
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
