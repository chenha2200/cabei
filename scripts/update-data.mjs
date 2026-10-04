import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE_PAGE = "https://www.bcie.org/adquisiciones-institucionales/en-curso";
const LIST_API = "https://www.bcie.org/api/adquisitions/in-progres";
const FILES_API = "https://www.bcie.org/api/adquisitions/files";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DATA_FILE = path.join(ROOT, "public", "data", "opportunities.json");

// CABEI may republish the same procurement under a new internal ID. Match the
// stable process number together with title keywords instead of AUCTION_HEADER_ID.
const titleRules = [
  { process: "035/2026", test: /smart cities|ciudades inteligentes/i, title: "中美洲與多明尼加智慧城市區域投資計畫" },
  { process: "044/2026", test: /lago ilopango|coatepeque/i, title: "薩爾瓦多 Ilopango 與 Coatepeque 湖泊整治及復育計畫" },
  { process: "045/2026", test: /vmware/i, title: "VMware 平台授權更新" },
  { process: "046/2026", test: /drenaje pluvial|sistema de drenaje/i, title: "CABEI 尼加拉瓜辦公大樓雨水排水系統改善與擴建" },
  { process: "047/2026", test: /mantenimiento.*limpieza|limpieza.*cafeter[ií]a/i, title: "CABEI 尼加拉瓜辦公室綜合設施服務" },
  { process: "048/2026", test: /purestorage/i, title: "PureStorage 儲存設備支援續約" },
  { process: "048/2026", test: /seguridad.*guatemala|gerencia de pa[ií]s.*guatemala/i, title: "CABEI 瓜地馬拉國家管理處安全服務" },
  { process: "049/2026", test: /voceros|comunicaci[oó]n/i, title: "CABEI 官方發言人策略溝通培訓" },
  { process: "050/2026", test: /zero waste to landfill/i, title: "CABEI 五國辦公設施零廢棄物掩埋認證診斷與準備顧問服務" },
  { process: "050/2026", test: /rehabilitaci[oó]n.*cubierta|cubierta.*balcones/i, title: "CABEI 哥斯大黎加辦公大樓屋頂、陽台及附屬區域修繕工程" },
  { process: "051/2026", test: /indicadores.*ambientales.*sociales.*gobernanza|sistema.*monitoreo.*evaluaci[oó]n/i, title: "制定環境、社會和治理指標監測和評估系統 — 第一階段" },
  { process: "052/2026", test: /seguridad f[ií]sica.*nicaragua|edificio.*nicaragua/i, title: "CABEI 尼加拉瓜國家管理處實體安全服務" },
  { process: "053/2026", test: /plataforma central.*procesamiento.*telecomunicaciones|telecomunicaciones.*procesamiento/i, title: "CABEI 核心運算與電信平台更新（二期）" }
];

const companyCatalog = {
  cloud: [
    { name: "精誠資訊（SYSTEX）", role: "雲端與資安整合", why: "可評估雲端、企業軟體與資安方案整合；原廠資格及跨境服務範圍仍須逐案核對。", url: "https://www.systex.com/" },
    { name: "安碁資訊", role: "資安治理與監控", why: "可支援資安治理、監控及事件應變，並與具原廠授權及西語能力的夥伴組隊。", url: "https://www.acercsi.com/" },
    { name: "資拓宏宇（IISI）", role: "系統整合", why: "可評估企業 IT、雲端平台、資料介接及維運服務。", url: "https://www.iisigroup.com/en/about-en/services/" }
  ],
  ict: [
    { name: "精誠資訊（SYSTEX）", role: "企業 IT 整合", why: "企業軟體、資料中心與維運服務可對應授權或設備支援案件。", url: "https://www.systex.com/" },
    { name: "資拓宏宇（IISI）", role: "系統整合與維運", why: "可評估平台整合、資料中心服務與技術維運；須確認指定品牌授權。", url: "https://www.iisigroup.com/en/about-en/services/" }
  ],
  engineering: [
    { name: "中華顧問工程司（CECI）", role: "工程顧問／專案管理", why: "公共建設、交通、水利與專案管理能力可支援設計審查或工程顧問角色。", url: "https://www.ceci.org.tw/en/about/our-story.aspx" },
    { name: "亞新工程顧問（MAA Group）", role: "工程與環境顧問", why: "可評估建築、基礎設施、環境及專案管理工作，並與當地執業團隊合作。", url: "https://www2.maaconsultants.com/en/about/detail.php?dpid=2" },
    { name: "中鼎工程（CTCI）", role: "EPC／工程整合", why: "可評估工程整合、機電或環境技術分包；現地施工宜由區域夥伴主導。", url: "https://www.ctci.com/" }
  ],
  smartCity: [
    { name: "資拓宏宇（IISI）", role: "數位治理／系統整合", why: "政府與城市資訊系統、AIoT 及數位轉型能力可支援平台整合。", url: "https://www.iisigroup.com/en/about-en/services/" },
    { name: "研華科技", role: "IoT 技術夥伴", why: "城市 IoT、邊緣運算與平台能力可提供可落地的技術方案。", url: "https://www.advantech.com/" },
    { name: "中華顧問工程司（CECI）", role: "城市與工程顧問", why: "公共建設、交通及專案顧問能力可支援投資項目盤點與可行性研究。", url: "https://www.ceci.org.tw/en/about/our-story.aspx" }
  ]
};

const classificationRules = [
  { test: /microsoft|azure|o365|securityscorecard|ciber|cyber|seguridad (?:informática|en la nube|de proveedores)/i, industry: "雲端與資安", capabilities: ["雲端資安", "網路資安", "系統整合"], fit: 91, companies: "cloud" },
  { test: /purestorage|vmware|licenciamiento|almacenamiento|software|soporte para equipos|plataforma central.*procesamiento.*telecomunicaciones/i, industry: "數位與資通訊", capabilities: ["資訊基礎設施", "網路與電信", "系統整合"], fit: 86, companies: "ict" },
  { test: /smart cities|ciudades inteligentes/i, industry: "智慧城市與顧問", capabilities: ["智慧城市", "數位治理", "IoT 感測"], fit: 84, companies: "smartCity" },
  { test: /zero waste|residuos|ambiental|saneamiento|lago|sostenibilidad/i, industry: "永續與環境顧問", capabilities: ["環境影響評估", "ESG", "環境工程"], fit: 72, companies: "engineering" },
  { test: /drenaje|pluvial|rehabilitación|cubierta|balcones|obra|construcción/i, industry: "水利與土木工程", capabilities: ["土木施工", "水利工程", "測量與施工管理"], fit: 48, companies: "engineering" },
  { test: /seguridad física|servicios de seguridad|vigilancia/i, industry: "設施與一般服務", capabilities: ["設施管理"], fit: 22, companies: null },
  { test: /capacitación|voceros|comunicación/i, industry: "教育訓練與傳播", capabilities: ["專案顧問"], fit: 46, companies: null }
];

function normalizeText(value = "") {
  return String(value).normalize("NFKC").replace(/\s+/g, " ").trim();
}

function documentBase(value = "") {
  return String(value).split(",")[0].trim();
}

function processNumber(...values) {
  const text = values.map(normalizeText).join(" ");
  const match = text.match(/\b(\d{3})\s*\/?\s*(20\d{2})\b/);
  return match ? `${match[1]}/${match[2]}` : "未載明";
}

function localizedTitle(process, originalTitle) {
  const matched = titleRules.find(rule => rule.process === process && rule.test.test(originalTitle));
  if (matched) return matched.title;
  return originalTitle.replace(/^\s*\d{3}\s*\/?\s*20\d{2}\s*[–—:-]?\s*/i, "");
}

function inferCountry(text) {
  const matches = [
    ["哥斯大黎加", /costa rica/i], ["尼加拉瓜", /nicaragua/i], ["宏都拉斯", /honduras/i],
    ["薩爾瓦多", /el salvador/i], ["瓜地馬拉", /guatemala/i], ["巴拿馬", /panam[aá]/i],
    ["多明尼加共和國", /rep[uú]blica dominicana/i], ["貝里斯", /belice/i]
  ].filter(([, pattern]) => pattern.test(text)).map(([name]) => name);
  if (matches.length > 1) return "區域";
  return matches[0] || "區域／未載明";
}

function inferClassification(text, category) {
  const matched = classificationRules.find(rule => rule.test.test(text));
  if (matched) return matched;
  if (/consultor/i.test(category)) return { industry: "專業顧問", capabilities: ["專案顧問"], fit: 62, companies: null };
  if (/bienes/i.test(category)) return { industry: "一般供應", capabilities: ["整批供應", "現場安裝"], fit: 58, companies: null };
  return { industry: "設施與一般服務", capabilities: ["設施管理"], fit: 35, companies: null };
}

function categoryLabel(value = "") {
  if (/consultor/i.test(value)) return "顧問服務";
  if (/bienes/i.test(value)) return "貨品";
  return "服務";
}

function methodLabel(value = "") {
  if (/cotizaci/i.test(value)) return "公開詢價";
  if (/licitaci/i.test(value)) return "公開招標";
  return value || "公開採購";
}

function reasonFor(classification) {
  if (classification.fit >= 85) return "台灣在相關軟硬體、資安與系統整合領域供應成熟；建議搭配原廠資格及中美洲西語交付夥伴。";
  if (classification.companies === "engineering") return "台灣工程顧問與設備供應鏈可切入設計、技術或專案管理，但現地執照、施工與西語團隊仍需區域夥伴。";
  if (classification.industry === "設施與一般服務") return "本案以當地人力及即時履約為主，台灣跨境供應優勢有限。";
  return "可由具相關實績的台灣團隊評估合作，但須先核對西語、在地履約及完整資格門檻。";
}

function caveatFor(classification) {
  if (classification.industry === "設施與一般服務") return "高度依賴當地人力、許可、勞動法遵與現場管理，不建議台灣廠商單獨投標。";
  if (classification.companies === "engineering") return "須核對當地執業資格、強制現勘、工程保險、財務門檻及聯合投標規則。";
  return "須依 TOR 核對原廠授權、相似實績、人員資格、語言、稅務與跨境交付條件。";
}

function suggestionsFor(classification) {
  return classification.companies ? companyCatalog[classification.companies] : [];
}

async function postJSON(url, body) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json", "user-agent": "CABEI-Taiwan-Opportunity-Radar/1.0" },
        body: body === undefined ? "" : JSON.stringify(body)
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      if (attempt < 3) await new Promise(resolve => setTimeout(resolve, attempt * 1500));
    }
  }
  throw lastError;
}

async function fetchAttachments(id, fallback = []) {
  try {
    const payload = await postJSON(FILES_API, { auctionHeaderId: id });
    const files = Array.isArray(payload.data) ? payload.data : [];
    return files.map(file => ({
      name: normalizeText(file.FileName || file.Title || file.Description || "官方附件"),
      url: file.localFile || file.Url || ""
    })).filter(file => /^https:\/\//i.test(file.url));
  } catch (error) {
    console.warn(`附件同步失敗：${id}，保留既有資料。`, error.message);
    return fallback;
  }
}

const current = JSON.parse(await fs.readFile(DATA_FILE, "utf8"));
const listPayload = await postJSON(LIST_API);
const rows = (Array.isArray(listPayload.data) ? listPayload.data : [])
  .filter(row => row.CLOSE_BIDDING_DATE && new Date(row.CLOSE_BIDDING_DATE).getTime() > Date.now());

const existingById = new Map(current.opportunities.map(item => [String(item.id), item]));
const existingByDocument = new Map(current.opportunities.map(item => [documentBase(item.document), item]));
const officialAttachments = {};
const taiwanCompanySuggestions = {};

const opportunities = await Promise.all(rows.map(async row => {
  const id = String(row.AUCTION_HEADER_ID);
  const document = String(row.DOCUMENT_NUMBER || "");
  const previous = existingById.get(id) || existingByDocument.get(documentBase(document));
  const previousId = previous ? String(previous.id) : null;
  const previousWasRuleGenerated = previous?.analysisMode === "rules"
    || previous?.qualifications?.[0]?.startsWith("CABEI 公開清單未載明完整資格");
  const preserveAnalysis = previous && !previousWasRuleGenerated;
  const originalTitle = normalizeText(row.ITEM_DESCRIPTION || row.AUCTION_TITLE || "未載明");
  const combinedText = `${originalTitle} ${normalizeText(row.AUCTION_TITLE)}`;
  const classification = inferClassification(combinedText, row.CATEGORY_NAME || "");
  const process = processNumber(originalTitle, row.AUCTION_TITLE);
  const fallbackAttachments = previousId ? (current.officialAttachments[previousId] || []) : [];
  const attachments = await fetchAttachments(id, fallbackAttachments);
  officialAttachments[id] = attachments;
  taiwanCompanySuggestions[id] = preserveAnalysis && previousId && current.taiwanCompanySuggestions[previousId]
    ? current.taiwanCompanySuggestions[previousId]
    : suggestionsFor(classification);

  const generatedTitle = localizedTitle(process, originalTitle);
  const generatedSummary = `CABEI 公開採購「${generatedTitle}」。完整工作範圍、交付內容與驗收方式請以官方 TOR 為準。`;
  const generatedDocumentSummary = attachments.length
    ? `CABEI 官方案件頁目前提供 ${attachments.length} 份文件：${attachments.map(file => file.name).join("、")}。請逐份核對最新版本、修正通知、資格及投標格式。`
    : "CABEI 官方案件頁目前未提供可下載附件；請持續查看案號連結是否新增 TOR 或修正文件。";

  return {
    ...(previous || {}),
    id,
    document,
    process,
    country: preserveAnalysis ? previous.country : inferCountry(combinedText),
    industry: preserveAnalysis ? previous.industry : classification.industry,
    category: categoryLabel(row.CATEGORY_NAME),
    method: methodLabel(row.STYLE_NAME),
    published: new Date(row.PUBLISH_DATE).toISOString().slice(0, 10),
    deadlineUtc: new Date(row.CLOSE_BIDDING_DATE).toISOString(),
    fit: preserveAnalysis ? previous.fit : classification.fit,
    title: preserveAnalysis ? previous.title : generatedTitle,
    ruleTitle: generatedTitle,
    originalTitle,
    summary: preserveAnalysis ? previous.summary : generatedSummary,
    capabilities: preserveAnalysis ? previous.capabilities : classification.capabilities,
    reason: preserveAnalysis ? previous.reason : reasonFor(classification),
    caveat: preserveAnalysis ? previous.caveat : caveatFor(classification),
    noCompanyReason: preserveAnalysis ? previous.noCompanyReason : (!classification.companies ? "本案偏重在地人力、語言或現場履約，暫不自動列出台灣直接投標候選；建議先尋找中美洲合格主承包或專業夥伴。" : undefined),
    amount: preserveAnalysis ? previous.amount : "未載明",
    documentSummary: preserveAnalysis ? previous.documentSummary : generatedDocumentSummary,
    qualifications: preserveAnalysis ? previous.qualifications : ["CABEI 公開清單未載明完整資格；請下載 TOR 核對公司年資、相似實績、財務能力、原廠授權與核心人員要求。"],
    analysisMode: preserveAnalysis ? (previous.analysisMode || "curated") : "rules",
    documentUrl: attachments[0]?.url || previous?.documentUrl || ""
  };
}));

opportunities.sort((a, b) => a.deadlineUtc.localeCompare(b.deadlineUtc) || b.fit - a.fit);

const core = { source: SOURCE_PAGE, opportunities, officialAttachments, taiwanCompanySuggestions };
const currentCore = {
  source: current.source,
  opportunities: current.opportunities,
  officialAttachments: current.officialAttachments,
  taiwanCompanySuggestions: current.taiwanCompanySuggestions
};
const changed = JSON.stringify(core) !== JSON.stringify(currentCore);
const output = {
  generatedAt: changed ? new Date().toISOString() : current.generatedAt,
  ...core,
  translationCache: current.translationCache || {}
};

await fs.writeFile(DATA_FILE, `${JSON.stringify(output, null, 2)}\n`);
console.log(`同步完成：${opportunities.length} 筆進行中標案；${changed ? "資料有異動" : "沒有異動"}。`);
