// 해양경찰 법령정보센터 공통 JavaScript 모듈

function openViewer(lawId) {
  // 첨부2 참조: 새 창(또는 브라우저 새 탭)으로 본문 뷰어 열기
  const url = `/viewer?id=${lawId}`;
  const windowFeatures = "width=1280,height=900,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes";
  const newWin = window.open(url, `_blank`, windowFeatures);
  if (newWin) {
    newWin.focus();
  } else {
    // 팝업 차단 시 일반 새 탭 이동
    window.open(url, "_blank");
  }
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  return dateStr;
}

function getCategoryBadge(category, subCategory) {
  let badgeClass = "badge-law";
  let defaultText = "법령";
  if (category === "commentary") {
    badgeClass = "badge-commentary";
    defaultText = "법령해설";
  } else if (category === "rule") {
    badgeClass = "badge-rule";
    defaultText = "행정규칙";
  }
  const text = subCategory || defaultText;
  return `<span class="badge ${badgeClass}">${text}</span>`;
}
