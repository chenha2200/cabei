const SOURCE_BASE = "https://www.bcie.org/adquisiciones-institucionales/en-curso";
let SNAPSHOT = new Date();
let opportunities = [];
let officialAttachments = {};
let taiwanCompanySuggestions = {};

const $ = (selector) => document.querySelector(selector);
const cardsEl = $("#cards");
const emptyEl = $("#empty");
const activeCapabilities = new Set();
const watched = new Set(JSON.parse(localStorage.getItem("cabei-watchlist") || "[]"));

const capabilityGroups = [
  ["數位科技", ["軟體授權", "虛擬化", "資料中心", "系統維運", "企業軟體", "Microsoft Azure", "Microsoft 365", "AI 治理", "SaaS 導入"]],
  ["資安網通", ["CCTV", "影像監控", "網路設備", "網路資安", "雲端資安", "身分存取管理", "系統整合", "供應鏈資安", "第三方風險管理", "資安監控"]],
  ["智慧城市", ["智慧城市", "數位治理", "IoT 感測", "智慧建築", "設施管理"]],
  ["環境永續", ["環境影響評估", "ESG", "水污染治理", "湖泊復育", "環境工程", "環境監測", "有機廢棄物", "循環經濟", "碳管理", "雨水排水", "水利工程"]],
  ["研究顧問", ["市場研究", "資料分析", "品牌策略", "調查研究", "投資規劃", "專案顧問"]],
  ["交通工程", ["軌道顧問", "運輸規劃", "需求預測", "GIS", "可行性研究", "土木施工", "管線工程", "測量與施工管理"]],
  ["金融專業", ["金融風險", "會計審計", "信用模型", "國際金融"]],
  ["一般供應", ["辦公家具", "空間配置", "整批供應", "現場安裝", "清潔服務", "車輛駕駛"]]
];

function unique(values) { return [...new Set(values)].sort((a, b) => a.localeCompare(b, "zh-Hant")); }
function daysUntil(iso) { return Math.max(0, Math.ceil((new Date(iso) - SNAPSHOT) / 86400000)); }
function dateLabel(date) { return new Intl.DateTimeFormat("zh-TW", {year:"numeric", month:"2-digit", day:"2-digit"}).format(new Date(`${date}T12:00:00+08:00`)); }
function taiwanDeadline(iso) { return new Intl.DateTimeFormat("zh-TW", {timeZone:"Asia/Taipei", year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", hour12:false}).format(new Date(iso)); }
function utcDeadline(iso) { return iso.replace("T", " ").replace(":00Z", " UTC"); }
function detailUrl(item) { return `${SOURCE_BASE}/${item.id}?documentNumber=${encodeURIComponent(item.document)}`; }
function escapeHTML(value) { return String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }
function companiesFor(item) { return taiwanCompanySuggestions[item.id] || []; }

function populateControls() {
  unique(opportunities.map(x => x.industry)).forEach(value => $("#industry").insertAdjacentHTML("beforeend", `<option value="${escapeHTML(value)}">${escapeHTML(value)}</option>`));
  unique(opportunities.map(x => x.country)).forEach(value => $("#country").insertAdjacentHTML("beforeend", `<option value="${escapeHTML(value)}">${escapeHTML(value)}</option>`));
  capabilityGroups.forEach(([label]) => $("#capabilities").insertAdjacentHTML("beforeend", `<button class="cap-chip" type="button" data-cap="${escapeHTML(label)}" aria-pressed="false">${escapeHTML(label)}</button>`));
}

function capabilityMatch(item) {
  if (!activeCapabilities.size) return true;
  return [...activeCapabilities].some(group => {
    const terms = capabilityGroups.find(([label]) => label === group)?.[1] || [];
    return item.capabilities.some(capability => terms.includes(capability));
  });
}

function currentFilters() {
  return {
    search: $("#search").value.trim().toLocaleLowerCase("zh-Hant"),
    industry: $("#industry").value,
    country: $("#country").value,
    deadline: $("#deadline").value,
    fit: Number($("#fit").value),
    sort: $("#sort").value
  };
}

function filteredData() {
  const f = currentFilters();
  const data = opportunities.filter(item => {
    const companyText = companiesFor(item).flatMap(company => [company.name, company.role, company.why]);
    const haystack = [item.title, item.originalTitle, item.process, item.document, item.country, item.industry, item.category, item.summary, item.documentSummary, item.amount, item.amountNote || "", item.reason, ...item.qualifications, ...item.capabilities, ...companyText].join(" ").toLocaleLowerCase("zh-Hant");
    return (!f.search || haystack.includes(f.search))
      && (f.industry === "all" || item.industry === f.industry)
      && (f.country === "all" || item.country === f.country)
      && (f.deadline === "all" || daysUntil(item.deadlineUtc) <= Number(f.deadline))
      && item.fit >= f.fit
      && capabilityMatch(item);
  });
  data.sort((a, b) => f.sort === "deadline"
    ? a.deadlineUtc.localeCompare(b.deadlineUtc) || b.fit - a.fit
    : f.sort === "newest"
      ? b.published.localeCompare(a.published) || b.fit - a.fit
      : b.fit - a.fit || a.deadlineUtc.localeCompare(b.deadlineUtc));
  return data;
}

function urgencyText(item) {
  const days = daysUntil(item.deadlineUtc);
  if (days <= 1) return `<strong class="urgent">24 小時內截止</strong>`;
  if (days <= 3) return `<strong class="urgent">${days} 天內截止</strong>`;
  return `<strong>${taiwanDeadline(item.deadlineUtc)} · ${days} 天</strong>`;
}

function fitClass(score) { return score >= 85 ? "fit-high" : score >= 65 ? "fit-mid" : ""; }

function scopeItemsFor(item) {
  return [
    `官方採購標的：${item.summary}`,
    `台灣可主攻能力：${item.capabilities.join("、")}。`,
    item.category === "顧問服務" ? "核心專家、人月、成果報告、田野與駐地要求須依完整需求規範確認。" : item.category === "貨品" ? "數量、規格、交付、安裝、測試、教育訓練與保固範圍須依完整文件確認。" : "服務項目、人員配置、服務水準、履約地點、期間與驗收方式須依完整文件確認。"
  ];
}

function companySuggestionsTemplate(item) {
  const companies = companiesFor(item);
  if (!companies.length) {
    return `<div class="company-empty"><strong>暫不建議配置台灣廠商。</strong>${escapeHTML(item.noCompanyReason || "本案的履約條件高度在地化，建議先由當地合格業者評估。")}</div>`;
  }
  return `<div class="company-grid">${companies.map(company => `
    <a class="company-card" href="${escapeHTML(company.url)}" target="_blank" rel="noopener">
      <span class="company-role">${escapeHTML(company.role)}</span>
      <strong>${escapeHTML(company.name)}</strong>
      <p>${escapeHTML(company.why)}</p>
      <span class="company-link">公司能力來源 ↗</span>
    </a>`).join("")}</div>`;
}

function attachmentType(name) {
  const match = name.match(/\.([a-z0-9]+)$/i);
  return match ? match[1].toUpperCase() : "附件";
}

function attachmentsTemplate(item) {
  const attachments = officialAttachments[item.id] || [];
  if (!attachments.length) {
    return `<div class="attachment-empty">CABEI 官方案件頁目前沒有可下載的招標文件或附件連結。</div>`;
  }
  return `<div class="attachment-list">${attachments.map(file => `
    <a class="attachment-card" href="${escapeHTML(file.url)}" target="_blank" rel="noopener">
      <span class="attachment-type">${escapeHTML(attachmentType(file.name))}</span>
      <strong>${escapeHTML(file.name)}</strong>
      <span class="attachment-link">開啟附件 ↗</span>
    </a>`).join("")}</div>`;
}

function cardTemplate(item) {
  const isWatched = watched.has(item.id);
  return `<article class="card" data-id="${escapeHTML(item.id)}">
    <div class="card-top">
      <div class="tags"><span class="tag ${fitClass(item.fit)}">適配 ${item.fit}</span><span class="tag">${escapeHTML(item.country)}</span><span class="tag">${escapeHTML(item.industry)}</span></div>
      <button class="watch ${isWatched ? "active" : ""}" type="button" data-watch="${escapeHTML(item.id)}" aria-pressed="${isWatched}" aria-label="${isWatched ? "取消追蹤" : "加入追蹤"}">${isWatched ? "★" : "☆"}</button>
    </div>
    <h3>${escapeHTML(item.title)}</h3>
    <div class="card-id"><a href="${detailUrl(item)}" target="_blank" rel="noopener">案號 ${escapeHTML(item.process)} ↗</a><span> · CABEI 系統文件 ${escapeHTML(item.document)}</span></div>
    <p class="summary">${escapeHTML(item.summary)}</p>${item.translationWarnings?.length ? `<p class="qualification-note">翻譯待校訂：${escapeHTML(item.translationWarnings.join("、"))}；請核對官方原文。</p>` : ""}
    <div class="card-grid">
      <div class="metric amount-metric"><span>公告金額</span><strong>${escapeHTML(item.amount)}</strong>${item.amountNote ? `<small>${escapeHTML(item.amountNote)}</small>` : ""}</div>
      <div class="metric"><span>採購方式</span><strong>${escapeHTML(item.method)}／${escapeHTML(item.category)}</strong></div>
      <div class="metric"><span>截止日期（台灣）</span>${urgencyText(item)}</div>
      <div class="metric"><span>台灣適配度</span><div class="fit-line"><div class="fit-track"><div class="fit-fill" style="width:${item.fit}%"></div></div><strong>${item.fit}/100</strong></div></div>
    </div>
    <div class="card-actions"><div class="fit-reason"><strong>適配理由：</strong>${escapeHTML(item.reason)}</div><button class="details-button" type="button" aria-expanded="false">查看商機公告</button></div>
    <div class="details"><div class="notice-sheet">
      <div class="notice-title">【商機公告】中美洲經濟整合銀行（CABEI）${escapeHTML(item.method)}：${escapeHTML(item.title)}（案號：${escapeHTML(item.process)}）</div>
      <div class="notice-body">
        <div class="notice-facts">
          <div class="notice-fact"><span>發布日期</span><strong>${dateLabel(item.published)}</strong></div>
          <div class="notice-fact"><span>招標機構</span><strong>中美洲經濟整合銀行（CABEI）</strong></div>
          <div class="notice-fact"><span>招標案號</span><strong>${escapeHTML(item.process)}（系統文件 ${escapeHTML(item.document)}）</strong></div>
          <div class="notice-fact"><span>採購方式</span><strong>${escapeHTML(item.method)}／${escapeHTML(item.category)}</strong></div>
          <div class="notice-fact"><span>公告金額</span><strong>${escapeHTML(item.amount)}${item.amountNote ? `<br><small>${escapeHTML(item.amountNote)}</small>` : ""}</strong></div>
          <div class="notice-fact"><span>說明會／現勘</span><strong class="pending">${escapeHTML(item.briefing || "公開清單未載明")}</strong></div>
          <div class="notice-fact"><span>廠商提問期限</span><strong class="pending">${escapeHTML(item.questionsDue || "公開清單未載明")}</strong></div>
          <div class="notice-fact"><span>投標截止</span><strong>${taiwanDeadline(item.deadlineUtc)}（台灣）<br><small>${utcDeadline(item.deadlineUtc)}</small></strong></div>
          <div class="notice-fact"><span>投標語言</span><strong class="pending">${escapeHTML(item.language || "公開清單未載明")}</strong></div>
        </div>
        <section class="notice-section"><h4>一、專案背景與商機說明</h4><p>${escapeHTML(item.summary)} 官方原文標題為「${escapeHTML(item.originalTitle)}」。</p></section>
        <section class="notice-section"><h4>二、主要工作／供應範疇</h4><ul class="notice-list">${scopeItemsFor(item).map(text => `<li>${escapeHTML(text)}</li>`).join("")}</ul></section>
        <section class="notice-section"><h4>三、投標廠商資格</h4><ul class="notice-list qualification-list">${item.qualifications.map(text => `<li>${escapeHTML(text)}</li>`).join("")}</ul><p class="qualification-note">此處為 TOR 主要門檻摘要；表單、聲明、財務、保證、稅務與其他完整要求仍以官方文件為準。</p></section>
        <section class="notice-section"><h4>四、適合接洽的台灣廠商</h4>${companySuggestionsTemplate(item)}<p class="company-disclaimer">名單依各公司公開產品與服務能力初步配對，不代表該公司已表達投標意願、符合本案全部資格，亦不構成 CABEI 或標案機關背書。請先取得完整招標文件並直接向公司確認供貨、認證與合作意願。</p></section>
        <section class="notice-section document-summary"><h4>五、招標文件／附件摘要</h4><p>${escapeHTML(item.documentSummary)}</p>${attachmentsTemplate(item)}<p class="attachment-note">附件名稱與連結取自 CABEI 官方案件頁；若官方後續修正，請以案號連結所列最新文件為準。</p></section>
      </div>
    </div></div>
  </article>`;
}

function currentWatchedCount() { return opportunities.filter(item => watched.has(item.id)).length; }

function renderActiveFilters() {
  const f = currentFilters();
  const labels = [];
  if (f.search) labels.push(f.search);
  if (f.industry !== "all") labels.push(f.industry);
  if (f.country !== "all") labels.push(f.country);
  if (f.deadline !== "all") labels.push(`${f.deadline} 天內截止`);
  if (f.fit) labels.push(`適配 ${f.fit} 分以上`);
  activeCapabilities.forEach(group => labels.push(group));
  $("#active-filters").innerHTML = labels.map(label => `<span class="active-filter">${escapeHTML(label)}</span>`).join("");
}

function render() {
  const data = filteredData();
  cardsEl.innerHTML = data.map(cardTemplate).join("");
  emptyEl.style.display = data.length ? "none" : "block";
  $("#result-meta").textContent = `顯示 ${data.length}／${opportunities.length} 筆 · 已追蹤 ${currentWatchedCount()} 筆`;
  renderActiveFilters();
}

function resetFilters() {
  $("#search").value = "";
  $("#industry").value = "all";
  $("#country").value = "all";
  $("#deadline").value = "all";
  $("#fit").value = 0;
  $("#fit-value").textContent = "0";
  $("#sort").value = "fit";
  activeCapabilities.clear();
  document.querySelectorAll(".cap-chip").forEach(chip => { chip.classList.remove("active"); chip.setAttribute("aria-pressed", "false"); });
  render();
}

$("#search").addEventListener("input", render);
["industry", "country", "deadline", "sort"].forEach(id => $("#" + id).addEventListener("change", render));
$("#fit").addEventListener("input", event => { $("#fit-value").textContent = event.target.value; render(); });
$("#reset").addEventListener("click", resetFilters);
$("#capabilities").addEventListener("click", event => {
  const chip = event.target.closest("[data-cap]");
  if (!chip) return;
  const group = chip.dataset.cap;
  activeCapabilities.has(group) ? activeCapabilities.delete(group) : activeCapabilities.add(group);
  chip.classList.toggle("active");
  chip.setAttribute("aria-pressed", chip.classList.contains("active"));
  render();
});

cardsEl.addEventListener("click", event => {
  const watchButton = event.target.closest("[data-watch]");
  if (watchButton) {
    const id = watchButton.dataset.watch;
    watched.has(id) ? watched.delete(id) : watched.add(id);
    localStorage.setItem("cabei-watchlist", JSON.stringify([...watched]));
    render();
    return;
  }
  const detailsButton = event.target.closest(".details-button");
  if (detailsButton) {
    const card = detailsButton.closest(".card");
    const open = card.classList.toggle("open");
    detailsButton.textContent = open ? "收合商機公告" : "查看商機公告";
    detailsButton.setAttribute("aria-expanded", open);
  }
});

$("#filter-toggle").addEventListener("click", event => {
  const open = $("#filters").classList.toggle("open");
  event.currentTarget.textContent = open ? "收合篩選條件" : "開啟篩選條件";
  event.currentTarget.setAttribute("aria-expanded", open);
});
async function initialize() {
  try {
    const response = await fetch("data/opportunities.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`資料載入失敗（${response.status}）`);
    const payload = await response.json();
    opportunities = Array.isArray(payload.opportunities) ? payload.opportunities : [];
    officialAttachments = payload.officialAttachments || {};
    taiwanCompanySuggestions = payload.taiwanCompanySuggestions || {};
    SNAPSHOT = new Date();
    populateControls();
    render();
    $("#stat-opportunities").textContent = opportunities.length;
    $("#brand-count").textContent = opportunities.length;
    $("#stat-countries").textContent = unique(opportunities.map(x => x.country)).length;
    $("#stat-highfit").textContent = opportunities.filter(x => x.fit >= 85).length;
    const generated = payload.generatedAt ? new Date(payload.generatedAt) : null;
    $("#snapshot").textContent = generated && !Number.isNaN(generated.valueOf())
      ? `資料更新：${new Intl.DateTimeFormat("zh-TW", { timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(generated)}（台灣時間）`
      : "資料更新時間未載明";
  } catch (error) {
    console.error(error);
    $("#result-meta").textContent = "資料暫時無法載入，請稍後再試。";
    $("#empty").style.display = "block";
    $("#empty").innerHTML = `<strong>無法載入商機資料</strong>${escapeHTML(error.message)}`;
  }
}

initialize();
