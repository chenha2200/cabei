"""Pinned OPUS-MT offline translator: Spanish -> English -> Traditional Chinese."""
import os
import re
from types import SimpleNamespace
import torch
from opencc import OpenCC
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from translation_guard import PROTECTED, restore, cache_key

def protect_identifiers(text):
    mapping = {}
    def replace(match):
        token = f"ZXQ{len(mapping)}QXZ"
        mapping[token] = match.group()
        return token
    return PROTECTED.sub(replace, text), mapping

def terminology(text):
    for source, target in {
        "殺真菌劑":"殺菌劑", "洪都拉斯":"宏都拉斯",
        "第二巡迴工程":"第二迴路工程", "諮詢公司":"顧問公司",
    }.items():
        text = text.replace(source, target)
    return text

MODELS = [
 ("Helsinki-NLP/opus-mt-es-en", "c96e2c5399ebfae4fc43d9669556b9afa74bb69d"),
 ("Helsinki-NLP/opus-mt-en-zh", "408d9bc410a388e1d9aef112a2daba955b945255"),
]
MODEL_ID = "OPUS-MT es-en/en-zh pinned-hans-v2"
CONVERT = OpenCC("s2twp")

class Translator:
    def __init__(self, cache=None):
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        self.tokenizer = SimpleNamespace(src_lang="es")
        self.cache = cache if cache is not None else {}
        self.models = [
            (AutoTokenizer.from_pretrained(name, revision=revision),
             AutoModelForSeq2SeqLM.from_pretrained(name, revision=revision).eval())
            for name, revision in MODELS
        ]

    def stage(self, text, index):
        tokenizer, model = self.models[index]
        # This checkpoint's Hant branch omitted clauses in our procurement test.
        # Use its Hans branch, then OpenCC for Taiwan Traditional Chinese.
        prompt = ">>cmn_Hans<< " + text if index == 1 else text
        encoded = tokenizer(prompt, return_tensors="pt", truncation=False)
        if encoded["input_ids"].shape[-1] > 480:
            raise ValueError("Translation input exceeds validated token limit")
        with torch.inference_mode():
            generated = model.generate(**encoded, num_beams=4, max_new_tokens=480,
                                       early_stopping=True, no_repeat_ngram_size=4)
        return tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

    def infer(self, text):
        if not re.search(r"[a-zA-Z]", text):
            return text
        connector = {"en":"在","y":"與","de":"的","del":"的","para":"用於","a":"至"}
        if self.tokenizer.src_lang == "es" and text.strip().lower() in connector:
            return connector[text.strip().lower()]
        english = self.stage(text, 0) if self.tokenizer.src_lang == "es" else text
        if getattr(self, "engineering", False):
            english = re.sub(r"\bcircuit\b", "electrical transmission circuit", english, flags=re.I)
        return terminology(CONVERT.convert(self.stage(english, 1)))

    def translate_many(self, values):
        output = []
        for source in values:
            self.engineering = bool(re.search(r"SIEPAC|electromec|subestaci[oó]n", str(source), re.I))
            key = cache_key(source, self.tokenizer.src_lang, MODEL_ID)
            if key in self.cache:
                output.append(self.cache[key])
                continue
            # Preserve context for ordinary sentences; keep all chunks below limits.
            chunks = []
            pending = ""
            for word in str(source).split():
                if pending and len(pending) + len(word) > 300:
                    chunks.append(pending)
                    pending = ""
                pending = (pending + " " + word).strip()
            if pending:
                chunks.append(pending)
            translated = []
            for chunk in chunks:
                masked, mapping = protect_identifiers(chunk)
                result = restore(self.infer(masked), mapping)
                if result is None:
                    # No raw prose fallback: translate prose around protected values.
                    fragments = re.split(r"(ZXQ\d+QXZ)", masked)
                    result = " ".join(
                        mapping[fragment] if fragment in mapping else self.infer(fragment)
                        for fragment in fragments if fragment.strip()
                    )
                    result = "【待校訂：分段翻譯】" + result
                if not re.search(r"[\u3400-\u9fff]", result):
                    raise ValueError("Translation did not produce Chinese; retain previous website data")
                translated.append(result)
            result = " ".join(translated)
            self.cache[key] = result
            output.append(result)
        return output
