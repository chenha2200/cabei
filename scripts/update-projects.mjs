import fs from "node:fs/promises";
const SOURCE_PAGE="https://www.bcie.org/adquisiciones-en-proyectos/avisos-de-adquisicion";
const DATA_FILE=new URL("../public/projects/data/opportunities.json",import.meta.url);
const norm=v=>String(v||"").replace(/\s+/g," ").trim();
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


const rules=[
 [/c[oó]mputo|data center|software|gesti[oó]n integral|sistema.*inform/i,"數位與資通訊",["資料中心","系統整合"],88,"ict"],
 [/agua|drenaje|talud|construcci[oó]n|electromec|supervisi[oó]n|ingenieros/i,"基礎設施與工程",["水利工程","土木施工","測量與施工管理"],65,"engineering"],
 [/insecticida|fungicida/i,"農業與化工",["整批供應"],52,null],
 [/laboratorio|cromatograf|fisicoqu[ií]mica/i,"實驗室設備",["整批供應","現場安裝"],72,null],
 [/equipment|equipos|seguridad personal/i,"設備與安全用品",["整批供應","現場安裝"],63,null],
 [/alimento|granos|aceite/i,"食品與農業",["整批供應"],42,null]
];
const countries={"El Salvador":"薩爾瓦多",Guatemala:"瓜地馬拉",Nicaragua:"尼加拉瓜","Costa Rica":"哥斯大黎加",Belice:"貝里斯",Honduras:"宏都拉斯",Argentina:"阿根廷",Panamá:"巴拿馬","República Dominicana":"多明尼加共和國"};
async function get(url){const r=await fetch(url,{signal:AbortSignal.timeout(60000)});if(!r.ok)throw new Error("CABEI HTTP "+r.status);return r.json();}
let current={opportunities:[],officialAttachments:{},taiwanCompanySuggestions:{}};
try{current=JSON.parse(await fs.readFile(DATA_FILE,"utf8"));}catch(e){if(e.code!=="ENOENT")throw e;}
let rows=[],page=1;
do{const p=await get("https://www.bcie.org/api/adquisiciones-en-proyecto?limit=100&page="+page);if(!Array.isArray(p.docs))throw new Error("Invalid CABEI payload");rows.push(...p.docs);if(!p.hasNextPage)break;if(++page>30)throw new Error("Pagination exceeded");}while(true);
if(!rows.length)throw new Error("Empty source: refusing to erase data");
const previous=new Map(current.opportunities.map(x=>[x.id,x]));
const officialAttachments={},taiwanCompanySuggestions={};
const opportunities=rows.filter(r=>r.reception_date&&new Date(r.reception_date)>new Date()).map(r=>{
 const id=String(r.id),old=previous.get(id)||{},text=norm(r.title_project),rule=rules.find(x=>x[0].test(text)),individual=/ConsultoriasIndividuales/i.test(r.category);
 const [,industry,capabilities,fit,group]=rule||[null,"個人／專業顧問",["專案顧問"],28,null];
 const contact=norm(r.website)+" "+norm(r.documentation_place);
 const urls=[...new Set(contact.match(/https?:\/\/[^\s,<>]+/g)||[])].map(u=>u.replace(/[.;]+$/,""));
 officialAttachments[id]=urls.map(url=>({name:/\.pdf(?:$|\?)/i.test(url)||/descarga_archivo/.test(url)?"官方招標文件.pdf":"官方文件取得入口",url}));
 taiwanCompanySuggestions[id]=individual?[]:(group?companyCatalog[group]:[]);
 return {...old,id,document:id,process:norm(r.process_number)||"未載明",originalTitle:text,title:old.title||text,
 sourceUrl:SOURCE_PAGE+"/"+id+"-"+encodeURIComponent(r.process_number),officialSummary:norm(r.object),executor:norm(r.executor),
 sourceLanguage:r.country==="Belice"?"en":"es",country:countries[r.country]||r.country,industry:individual?"個人顧問":industry,
 category:individual?"個人顧問":/Consult/i.test(r.category)?"顧問服務":/-B$/.test(r.process_number)?"貨品":"工程／服務",
 method:norm(r.modality_description)||"未載明",published:(r.start_date_sale||r.createdAt).slice(0,10),
 deadlineUtc:r.reception_date,deadlineDate:r.reception_date.slice(0,10),capabilities,fit:individual?20:fit,
 reason:individual?"本案採購個人顧問，不應以台灣企業名單替代個人資格審查。":group?"台灣相關技術與工程供應鏈可評估；仍須確認在地履約、實績與聯合投標條款。":"可評估台灣設備或產品供應；未核實具本案認證及跨境交付能力的公司，不列具名推薦。",
 noCompanyReason:individual?"個人顧問或行政職務，需由符合官方條件的個人申請；公司不是直接投標候選。":"暫無經逐案核對的具名台灣廠商；可先評估供應鏈及當地合作通路。",
 amount:old.amount||"未載明",amountNote:"僅列文件明示的美元金額；API 數值欄位未標示幣別，不推定為美元。",sourceAmount:norm(r.amount_awarded),
 summary:old.summary||"CABEI 專案公開採購。完整範疇請查官方公告。",
 qualifications:old.qualifications||["官方清單未載明完整資格；請向執行機構取得招標文件，核對經驗、財務、人員、原廠授權與當地登記要求。"],
 documentSummary:old.documentSummary||"尚未擷取文件文字；請開啟官方文件取得入口。",analysisMode:old.analysisMode||"rules",
 documentAccess:contact};
});
opportunities.sort((a,b)=>a.deadlineUtc.localeCompare(b.deadlineUtc));
const core={source:SOURCE_PAGE,opportunities,officialAttachments,taiwanCompanySuggestions};
const before={source:current.source,opportunities:current.opportunities,officialAttachments:current.officialAttachments,taiwanCompanySuggestions:current.taiwanCompanySuggestions};
await fs.mkdir(new URL("../public/projects/data/",import.meta.url),{recursive:true});
await fs.writeFile(DATA_FILE,JSON.stringify({generatedAt:JSON.stringify(core)===JSON.stringify(before)?current.generatedAt:new Date().toISOString(),...core},null,2)+"\n");
console.log("Project procurement synchronized: "+opportunities.length);

