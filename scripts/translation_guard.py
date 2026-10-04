"""Deterministic terminology and safety checks; no network or API keys."""
import hashlib
import json
import re
VERSION = "procurement-guard-v1"
GLOSSARY = {
 "Banco Centroamericano de Integración Económica":"CABEI",
 "BCIE":"CABEI", "insecticidas":"殺蟲劑", "fungicidas":"殺菌劑",
 "licitación pública internacional":"國際公開招標",
 "licitación pública nacional":"國內公開招標",
 "términos de referencia":"工作說明書（TOR）",
 "equipos de seguridad personal":"個人防護裝備",
 "cromatografía":"層析分析", "fisicoquímica":"物理化學",
 "data center":"資料中心", "agua potable":"飲用水",
 "estabilización de taludes":"邊坡穩定", "pasos de fauna":"野生動物通道",
 "procurement officer":"採購專員",
 "Honduras":"宏都拉斯", "Nicaragua":"尼加拉瓜", "Costa Rica":"哥斯大黎加",
 "El Salvador":"薩爾瓦多", "Guatemala":"瓜地馬拉",
 "Agua Caliente":"Agua Caliente", "Sandino":"Sandino",
 "La Virgen":"La Virgen", "Fortuna":"Fortuna",
}
PATTERN = re.compile(
 "|".join(re.escape(x) for x in sorted(GLOSSARY,key=len,reverse=True))
 + r"|https?://[^\s<>]+|\b[A-Z][A-Z0-9-]{1,}\b|\d[\d.,:/-]*", re.I)
# Case-sensitive acronym matching is deliberately separate from glossary matching.
TERMS = re.compile("|".join(re.escape(x) for x in sorted(GLOSSARY,key=len,reverse=True)),re.I)
LOWER_GLOSSARY = {key.lower(): value for key, value in GLOSSARY.items()}
PROTECTED = re.compile(r"https?://[^\s<>]+|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|\b[A-Z][A-Z0-9-]{1,}\b|\d[\d.,:/-]*")
def protect(text):
    matches = [(m.start(),m.end(),LOWER_GLOSSARY[m.group().lower()]) for m in TERMS.finditer(text)]
    for m in PROTECTED.finditer(text):
        if not any(a<=m.start()<b for a,b,_ in matches):
            matches.append((m.start(),m.end(),m.group()))
    matches.sort()
    output=[]; mapping={}; last=0
    for i,(a,b,value) in enumerate(matches):
        token=f"ZXQ{i}QXZ"
        output.extend([text[last:a],token]);mapping[token]=value;last=b
    output.append(text[last:])
    return "".join(output),mapping
def restore(text,mapping):
    for token,value in mapping.items():
        # Never accept a translation that lost or duplicated an important token.
        if text.count(token)!=1:
            return None
        text=text.replace(token,value)
    return text
def issues(text):
    flags=[]
    if re.search(r"ZXQ\d|917304",text): flags.append("保護標記殘留")
    if re.search(r"\b(?:adquisici[oó]n|contrataci[oó]n|fungicides|insecticidas|licitaci[oó]n)\b",text,re.I):
        flags.append("採購術語未完成翻譯")
    if not re.search(r"[\u3400-\u9fff]",text): flags.append("未產生中文")
    if re.search(r"(.{6,25})\1\1",text): flags.append("重複文字")
    return flags
def cache_key(text,language,model):
    return hashlib.sha256(json.dumps([VERSION,text,language,model],ensure_ascii=False).encode()).hexdigest()
def apply_revision(item,revisions):
    revision=revisions.get(item.get("process"),{})
    if revision.get("originalTitle")!=item.get("originalTitle"): return False
    old=item.get("title","")
    for field in ("title","summary","documentSummary","qualifications"):
        if field in revision:
            if field in ("summary","documentSummary") and revision.get("originalSummary") and revision["originalSummary"] != item.get("officialSummary"): continue
            item[field]=revision[field]
    if old and revision.get("title"):
        item["summary"]=item.get("summary","").replace(old,revision["title"])
    if revision.get("originalDocumentAccess") == item.get("documentAccess") and "documentAccessZh" in revision:
        item["documentAccessZh"] = revision["documentAccessZh"]
    item["revisionSourceTitle"]=revision["originalTitle"]
    return True
