"""Real-source smoke tests; thresholds detect missing translation, not human accuracy."""
import json
import re
from opus_backend import Translator

translator = Translator()
samples = [
    "Adquisición de Insecticidas y fungicidas",
    "Contratar una Firma consultora que realice la Supervisión Externa de las Obras del Segundo Circuito SIEPAC en Honduras, Nicaragua y Costa Rica.",
    "Mejoramiento y Ampliación del Sistema de Agua Potable de la ciudad de Camoapa",
]
translated = translator.translate_many(samples)
assert "殺蟲劑" in translated[0] and "殺菌劑" in translated[0]
assert "監督" in translated[1] or "監理" in translated[1]
assert "法院" not in translated[1]
assert all(re.search(r"[\u3400-\u9fff]", text) for text in translated)
assert all("ZXQ" not in text for text in translated)
assert all(not re.search(r"\b(?:contratar|adquisici[oó]n|realice|obras)\b", text, re.I) for text in translated)
translator.tokenizer.src_lang = "en"
protected = translator.translate_many(["Supply 4 devices, USD 1,234.50; contact info@example.com."])[0]
assert "4" in protected and "1,234.50" in protected and "info@example.com" in protected
print(json.dumps(dict(zip(samples, translated)), ensure_ascii=False, indent=2))
print("PASS: OPUS real-source coverage, glossary, Spanish prose and protected values.")
