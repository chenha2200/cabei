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
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "public" / "data" / "opportunities.json"
MODEL_NAME = os.environ.get(
    "CABEI_TRANSLATION_MODEL", "Helsinki-NLP/opus-tatoeba-es-zh"
)
TARGET_PREFIX = ">>cmn_Hant<< "
MAX_SUMMARY_CHARS = 320
MAX_DOCUMENT_SUMMARY_CHARS = 500

SCOPE_KEYWORDS = (
    "objeto", "objetivo", "alcance", "contratar", "contratación",
    "adquisición", "servicio", "consultoría", "suministro", "renovación",
    "plataforma", "implementación", "entregable", "actividades",
)
QUALIFICATION_KEYWORDS = (
    "experiencia", "años", "requisito", "deberá", "debe contar",
    "oferente", "proveedor", "empresa", "certificación", "personal clave",
    "elegible", "capacidad técnica", "capacidad financiera",
)
DETAIL_KEYWORDS = SCOPE_KEYWORDS + QUALIFICATION_KEYWORDS + (
    "plazo", "duración", "cronograma", "pago", "usd", "us$", "dólares",
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def truncate(value: str, limit: int) -> str:
    return normalize(value)[:limit]


def fingerprint(item: dict, attachments: list[dict]) -> str:
    source = {
        "originalTitle": item.get("originalTitle", ""),
        "document": item.get("document", ""),
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


def select_sentences(text: str, keywords: tuple[str, ...], limit: int) -> list[str]:
    candidates = sentences(text)

    def score(value: str) -> tuple[int, int]:
        lowered = value.casefold()
        keyword_score = sum(1 for keyword in keywords if keyword in lowered)
        return keyword_score, min(len(value), 260)

    ranked = sorted(candidates, key=score, reverse=True)
    selected = [value for value in ranked if score(value)[0] > 0][:limit]
    if len(selected) < min(2, limit):
        for value in candidates:
            if value not in selected:
                selected.append(value)
            if len(selected) >= limit:
                break
    return selected[:limit]


class Translator:
    def __init__(self) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        self.model.eval()

    def translate_many(self, values: list[str]) -> list[str]:
        if not values:
            return []
        results: list[str] = []
        for start in range(0, len(values), 6):
            batch = [TARGET_PREFIX + normalize(value) for value in values[start:start + 6]]
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
                    num_beams=4,
                    max_new_tokens=320,
                    early_stopping=True,
                )
            results.extend(
                normalize(value)
                for value in self.tokenizer.batch_decode(generated, skip_special_tokens=True)
            )
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
        scope_parts = select_sentences(document_text, SCOPE_KEYWORDS, 3)
        detail_parts = select_sentences(document_text, DETAIL_KEYWORDS, 7)
        qualification_parts = select_sentences(document_text, QUALIFICATION_KEYWORDS, 5)

        source_values = [title_source]
        if scope_parts:
            source_values.append(" ".join(scope_parts))
        if detail_parts:
            source_values.append(" ".join(detail_parts))
        source_values.extend(qualification_parts)
        translated = translator.translate_many(source_values)

        title_zh = translated.pop(0) if translated else item.get("title", title_source)
        if not re.search(r"[\u3400-\u9fff]", title_zh):
            title_zh = item.get("title", title_source)

        if scope_parts and translated:
            summary_zh = truncate(translated.pop(0), MAX_SUMMARY_CHARS)
        else:
            summary_zh = f"CABEI 公開採購「{title_zh}」。完整工作範圍請以官方 TOR 為準。"

        if detail_parts and translated:
            document_summary_zh = truncate(translated.pop(0), MAX_DOCUMENT_SUMMARY_CHARS)
        elif attachments:
            names = "、".join(file.get("name", "官方附件") for file in attachments)
            document_summary_zh = truncate(
                f"官方案件頁提供：{names}。目前未能擷取可翻譯文字，請直接查看附件。",
                MAX_DOCUMENT_SUMMARY_CHARS,
            )
        else:
            document_summary_zh = "官方案件頁目前沒有可下載附件。"

        qualifications_zh = [truncate(value, 180) for value in translated if value]
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
                "translationModel": f"{MODEL_NAME} (cmn_Hant)",
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
