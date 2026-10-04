#!/usr/bin/env python3
"""Translate CABEI procurement data inside GitHub Actions without API tokens."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import torch
from opencc import OpenCC
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "public" / "projects" / "data" / "opportunities.json"
MODEL_NAME = os.environ.get(
    "CABEI_TRANSLATION_MODEL", "facebook/m2m100_418M"
)
TRANSLATION_VERSION = "offline-project-v1"
SOURCE_LANG = "es"
TARGET_LANG = "zh"
OPENCC = OpenCC("s2twp")
MAX_SUMMARY_CHARS = 320
MAX_DOCUMENT_SUMMARY_CHARS = 500

SCOPE_WEIGHTS = {
    "objeto": 9, "objetivo": 9, "alcance": 8, "renovación": 5,
    "implementación": 5, "suministro": 4, "plataforma": 4,
    "contratar": 3, "contratación": 3, "adquisición": 3,
    "consultoría": 3, "entregable": 3, "actividades": 2, "servicio": 1,
}
QUALIFICATION_WEIGHTS = {
    "experiencia": 9, "certificación": 9, "personal clave": 8,
    "capacidad técnica": 8, "capacidad financiera": 8, "elegible": 7,
    "años": 6, "requisito": 5, "debe contar": 4, "empresa": 2,
    "oferente": 1, "proveedor": 1, "deberá": 1,
}
DETAIL_WEIGHTS = {
    **SCOPE_WEIGHTS,
    **QUALIFICATION_WEIGHTS,
    "plazo": 6, "duración": 6, "cronograma": 5, "pago": 4,
    "usd": 5, "us$": 5, "dólares": 5,
}
BOILERPLATE_PHRASES = (
    "política para la adquisición", "propiedad del bcie",
    "no podrá ser reproducido", "no podra ser reproducido",
    "medios mecánicos o electrónicos", "medios mecanicos o electronicos",
)
QUALIFICATION_EXCLUDES = (
    "portal de proveedores", "prórroga", "prorroga", "consultas",
    "preguntas", "presentación de ofertas", "presentacion de ofertas",
    "garantía bancaria por el cien", "garantia bancaria por el cien",
    "garantía de anticipo", "garantia de anticipo",
)
SCOPE_EXCLUDES = (
    "evaluación técnica", "evaluacion tecnica",
    "calificación técnica", "calificacion tecnica",
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def truncate(value: str, limit: int) -> str:
    return normalize(value)[:limit]


def fingerprint(item: dict, attachments: list[dict]) -> str:
    source = {
        "translationVersion": TRANSLATION_VERSION,
        "originalTitle": item.get("originalTitle", ""),
        "document": item.get("document", ""),
        "officialSummary": item.get("officialSummary", ""),
        "documentAccess": item.get("documentAccess", ""),
        "attachments": [
            {"name": file.get("name", ""), "url": file.get("url", "")}
            for file in attachments
        ],
    }
    raw = json.dumps(source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def strip_process_number(title: str) -> str:
    value = re.sub(r"^\s*\d{3}\s*/?\s*20\d{2}\s*[–—:.-]?\s*", "", title)
    return value.strip(" \t\r\n\"'“”")


def taiwan_chinese(value: str) -> str:
    converted = OPENCC.convert(normalize(value))
    organization_aliases = (
        "中美洲經濟一體化銀行", "中美洲經濟整合銀行",
        "國際清算銀行", "國際結算銀行", "金融情報室", "金融情報股",
        "舉報機構", "《環境倡議》",
    )
    for alias in organization_aliases:
        converted = converted.replace(alias, "CABEI")
    terminology = {
        "BCIE": "CABEI",
        "指示器": "指標",
        "通信平台": "通訊平台",
        "電信平臺": "電信平台",
        "平臺": "平台",
        "本檔案": "本文件",
        "提供商": "供應商",
        "目的或目的": "目的為",
        "更新、更新或": "升級、汰換或",
        "參考術語檔案": "工作說明書（TOR）",
        "參考術語文件": "工作說明書（TOR）",
        "訂約服務": "擬採購服務",
        "採購服務": "擬採購服務",
        "商貿中心": "CABEI 採購中心",
        "招標程式": "招標程序",
        "正式程式": "正式程序",
        "型別": "類型",
        "起碼": "最低",
        "質量": "品質",
        "裝置": "設備",
        "解決辦法": "解決方案",
        "原始說明函": "原廠證明函",
        "許可證認證水平": "授權認證等級",
        "招聘": "採購",
        "營銷": "行銷",
        "生命表": "履歷",
        "購買命令": "採購單",
        "合同": "契約",
        "合作伙伴": "合作夥伴",
        "可持續性": "永續性",
        "第1步": "第一階段",
        "第 1 步": "第一階段",
        "-- --": "—",
    }
    for source, target in terminology.items():
        converted = converted.replace(source, target)
    converted = re.sub(r"(?<=[\u3400-\u9fff]),", "，", converted)
    converted = re.sub(r",(?=[\u3400-\u9fff])", "，", converted)
    converted = re.sub(r"(?<=[\u3400-\u9fff]);", "；", converted)
    procurement_rewrites = {
        "該平台定期審查，以保持其更新，更新或新增構成該平台的元件。":
            "本案將定期檢視平台，並依需要升級、汰換或新增相關元件。",
        "1.2 採購的目的為 購買和更新通訊設備 CABEI辦公室在 瓜地馬拉， 薩爾瓦多， 宏都拉斯， 哥斯大黎加， 巴拿馬和 多明尼加共和國， 符合本文件中詳細描述的特點和最低要求。":
            "1.2 本案旨在採購並更新 CABEI 位於瓜地馬拉、薩爾瓦多、宏都拉斯、哥斯大黎加、巴拿馬及多明尼加共和國辦事處的通訊設備，並須符合本文件所列最低規格與要求。",
        "1.4 一般和具體的供應商經驗 1.4.1 一般經驗:":
            "1.4 供應商一般與特定經驗：",
        "供應商必須在銷售類似於所需的設備和 Cisco 解決方案方面擁有豐富的經驗。":
            "供應商須具備銷售符合類似需求之 Cisco 設備與解決方案的充分經驗。",
        "這些經驗必須透過客戶發出的參考信(至少5張)來證明，這些客戶已獲得與申請人相似的設備。":
            "相關經驗須以至少 5 封客戶實績證明函佐證，內容應涵蓋類似設備供應。",
        "2.5.4 設備製造商的原始代表性信，指明現行合作伙伴認證水平。":
            "2.5.4 須檢附設備原廠證明函，註明現行合作夥伴認證等級。",
        "由理事會秘書發出的權力書或證書的影印件，可以確定公司的法定代表的任命。":
            "須檢附董事會秘書出具之授權書或證明文件影本，以證明公司法定代表人的任命。",
        "1.3 採購可用於宏都拉斯 ▪ 十四個 (14) C9200L-48P-4G 模型交換機， c/u 與: 一次批准 交換機 - CX Level 1 保證，可替換為 24x7x4，最短期為 3 年。 設備保證 觸控板 - CX Level 1 保證，可替換為 8x5xNBD，最長為 3 年。":
            "1.3 宏都拉斯範圍包含 14 台 C9200L-48P-4G 交換器；交換器須提供 CX Level 1 保固與 24x7x4 更換服務至少 3 年，相關設備另須提供 8x5xNBD 更換服務至少 3 年。",
    }
    for source, target in procurement_rewrites.items():
        converted = converted.replace(source, target)
    return normalize(converted)


def prepare_source(value: str) -> str:
    prepared = normalize(value)
    prepared = re.sub(
        r"Banco\s+Centroamericano\s+de\s+Integraci[oó]n\s+Econ[oó]mica",
        "917304",
        prepared,
        flags=re.I,
    )
    prepared = re.sub(r"\bBCIE\b", "917304", prepared, flags=re.I)
    return prepared


def download_pdf_text(file: dict, index: int) -> str:
    request = urllib.request.Request(
        file["url"], headers={"User-Agent": "CABEI-Taiwan-Opportunity-Radar/1.0"}
    )
    with tempfile.TemporaryDirectory(prefix="cabei-tor-") as temp_dir:
        pdf_path = Path(temp_dir) / f"document-{index}.pdf"
        with urllib.request.urlopen(request, timeout=60) as response:
            pdf_path.write_bytes(response.read())
        result = subprocess.run(
            [
                "pdftotext", "-f", "1", "-l", "20", "-layout",
                str(pdf_path), "-",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
    return normalize(result.stdout)[:30000]


def official_text(attachments: list[dict]) -> str:
    pdfs = [
        file for file in attachments
        if re.search(r"\.pdf(?:$|\?)", file.get("url", ""), re.I)
        or file.get("name", "").lower().endswith(".pdf")
    ]
    pdfs.sort(
        key=lambda file: 0
        if re.search(r"t[eé]rminos|terms of reference|\btor\b", file.get("name", ""), re.I)
        else 1
    )
    sections: list[str] = []
    for index, file in enumerate(pdfs[:2]):
        try:
            text = download_pdf_text(file, index)
            if text:
                sections.append(text)
        except Exception as error:  # Keep the daily sync alive if one PDF is malformed.
            print(f"PDF 文字擷取失敗：{file.get('name', '官方附件')}：{error}")
    return normalize(" ".join(sections))[:45000]


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;:])\s+|\s{2,}", text)
    output: list[str] = []
    seen: set[str] = set()
    for part in parts:
        value = normalize(part)
        if not 35 <= len(value) <= 500:
            continue
        key = value.casefold()
        if key in seen or value.count(".") > 12:
            continue
        seen.add(key)
        output.append(value)
    return output


def select_sentences(
    text: str,
    weights: dict[str, int],
    limit: int,
    *,
    minimum_score: int = 1,
    excludes: tuple[str, ...] = (),
    fallback: bool = True,
) -> list[str]:
    candidates = sentences(text)
    scored: list[tuple[int, int, str]] = []
    for index, value in enumerate(candidates):
        lowered = value.casefold()
        if any(phrase in lowered for phrase in BOILERPLATE_PHRASES + excludes):
            continue
        score = sum(weight for keyword, weight in weights.items() if keyword in lowered)
        if score >= minimum_score:
            scored.append((score, index, value))

    ranked = sorted(scored, key=lambda entry: (-entry[0], entry[1]))[:limit]
    selected = [value for _, _, value in sorted(ranked, key=lambda entry: entry[1])]
    if fallback and len(selected) < min(2, limit):
        for value in candidates:
            lowered = value.casefold()
            if value in selected or any(
                phrase in lowered for phrase in BOILERPLATE_PHRASES
            ):
                continue
            selected.append(value)
            if len(selected) >= limit:
                break
    return selected[:limit]


class Translator:
    def __init__(self) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.tokenizer.src_lang = SOURCE_LANG
        self.target_lang_id = self.tokenizer.get_lang_id(TARGET_LANG)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        self.model.eval()

    def translate_many(self, values: list[str]) -> list[str]:
        if not values:
            return []
        results: list[str] = []
        for start in range(0, len(values), 3):
            source_batch = values[start:start + 3]
            prepared_batch = [prepare_source(value) for value in source_batch]
            protected_org = ["917304" in value for value in prepared_batch]
            batch = prepared_batch
            encoded = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            with torch.inference_mode():
                generated = self.model.generate(
                    **encoded,
                    forced_bos_token_id=self.target_lang_id,
                    num_beams=2,
                    max_new_tokens=320,
                    early_stopping=True,
                )
            decoded = self.tokenizer.batch_decode(generated, skip_special_tokens=True)
            for value, protect_org in zip(decoded, protected_org):
                translated = taiwan_chinese(value)
                if protect_org:
                    translated = re.sub(r"917304\s*年?", "CABEI", translated)
                    translated = re.sub(
                        r"為(.{10,180}?)CABEI辦事處購置和翻新電信設備"
                        r"的目的為[，,]\s*符合",
                        r"本案旨在為 CABEI 位於\1的辦事處採購並更新"
                        r"電信設備，且須符合",
                        translated,
                    )
                    translated = re.sub(
                        r"CABEI\s*\(\s*CABEI\s*\)\s*年?", "CABEI", translated
                    )
                    translated = translated.replace("CABEI個設施", "CABEI 設施")
                    translated = translated.replace("CABEI號大樓", "CABEI 辦公大樓")
                results.append(translated)
        return results


def explicit_usd_amount(text: str) -> str:
    match = re.search(
        r"(?:US\$|USD)\s*\d[\d.,]*(?:\s*(?:millones?|mil))?",
        text,
        re.I,
    )
    return normalize(match.group(0)) if match else "未載明"


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    attachment_map = data.get("officialAttachments", {})
    candidates: list[tuple[dict, list[dict], str]] = []

    for item in data.get("opportunities", []):
        if item.get("analysisMode") == "curated":
            continue
        attachments = attachment_map.get(str(item.get("id")), [])
        current_fingerprint = fingerprint(item, attachments)
        if (
            item.get("analysisMode") == "offline-translation"
            and item.get("translationFingerprint") == current_fingerprint
        ):
            continue
        candidates.append((item, attachments, current_fingerprint))

    if not candidates:
        print("離線翻譯：來源沒有異動，不需重新翻譯。")
        return

    print(f"離線翻譯：載入 {MODEL_NAME}，處理 {len(candidates)} 筆案件。")
    translator = Translator()
    translated_count = 0

    for item, attachments, current_fingerprint in candidates:
        title_source = strip_process_number(item.get("originalTitle", ""))
        document_text = official_text(attachments)
        translator.tokenizer.src_lang = item.get("sourceLanguage", "es")
        scope_parts = select_sentences(
            item.get("officialSummary", "") + " " + document_text,
            SCOPE_WEIGHTS,
            2,
            minimum_score=3,
            excludes=SCOPE_EXCLUDES,
        )
        detail_parts = select_sentences(
            document_text,
            DETAIL_WEIGHTS,
            5,
            minimum_score=4,
            excludes=SCOPE_EXCLUDES,
        )
        qualification_parts = select_sentences(
            document_text,
            QUALIFICATION_WEIGHTS,
            5,
            minimum_score=5,
            excludes=QUALIFICATION_EXCLUDES,
            fallback=False,
        )

        source_values = [title_source, *scope_parts, *detail_parts, *qualification_parts]
        translated = translator.translate_many(source_values)

        machine_title = translated.pop(0) if translated else item.get("title", title_source)
        rule_title = taiwan_chinese(item.get("ruleTitle", ""))
        title_zh = rule_title if re.search(r"[\u3400-\u9fff]", rule_title) else machine_title
        if not re.search(r"[\u3400-\u9fff]", title_zh):
            title_zh = item.get("title", title_source)

        scope_translations = translated[:len(scope_parts)]
        translated = translated[len(scope_parts):]
        detail_translations = translated[:len(detail_parts)]
        translated = translated[len(detail_parts):]
        qualification_translations = translated[:len(qualification_parts)]

        if scope_translations:
            summary_zh = truncate(
                f"CABEI 公開採購「{title_zh}」。"
                + " ".join(scope_translations),
                MAX_SUMMARY_CHARS,
            )
        else:
            summary_zh = f"CABEI 公開採購「{title_zh}」。完整工作範圍請以官方 TOR 為準。"

        document_parts: list[str] = []
        for value in [
            *scope_translations,
            *detail_translations,
            *qualification_translations,
        ]:
            if value and value not in document_parts:
                document_parts.append(value)
        if document_parts:
            document_summary_zh = truncate(
                " ".join(document_parts), MAX_DOCUMENT_SUMMARY_CHARS
            )
            if not document_text:
                document_summary_zh = truncate(
                    "尚未擷取附件文字；以下僅為官方公告範疇摘要：" + document_summary_zh,
                    MAX_DOCUMENT_SUMMARY_CHARS,
                )
        elif attachments:
            names = "、".join(file.get("name", "官方附件") for file in attachments)
            document_summary_zh = truncate(
                f"官方案件頁提供：{names}。目前未能擷取文件文字；這不是文件內容摘要，請直接查看原始文件。",
                MAX_DOCUMENT_SUMMARY_CHARS,
            )
        else:
            document_summary_zh = "官方清單提供文件取得方式：" + item.get("documentAccess", "未載明")

        qualifications_zh = [
            truncate(value, 180) for value in qualification_translations if value
        ]
        if not qualifications_zh:
            qualifications_zh = ["官方文件未擷取到明確的廠商資格條文，請直接核對 TOR。"]

        item.update(
            {
                "title": truncate(title_zh, 140),
                "summary": summary_zh,
                "documentSummary": document_summary_zh,
                "qualifications": qualifications_zh[:5],
                "amount": explicit_usd_amount(document_text),
                "analysisMode": "offline-translation",
                "translationFingerprint": current_fingerprint,
                "translationModel": f"{MODEL_NAME} ({SOURCE_LANG}→{TARGET_LANG}) + OpenCC s2twp",
                "translationVersion": TRANSLATION_VERSION,
                "translationUpdatedAt": datetime.now(timezone.utc).isoformat(),
            }
        )
        translated_count += 1
        print(f"離線翻譯完成：{item.get('process')} {item.get('title')}")

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"離線翻譯完成：共更新 {translated_count} 筆，不使用外部 API Token。")


if __name__ == "__main__":
    main()
