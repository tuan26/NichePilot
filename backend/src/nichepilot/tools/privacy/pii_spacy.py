"""SpacyEnPiiEngine – CHỈ dev/test, nhóm tùy chọn `pii-ner` (quyết định I2: chưa phê duyệt production).

Import spaCy lười (không có trong image production). Không tải model lúc chạy: thiếu model → ConfigError ở select_pii_engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from nichepilot.tools.privacy.pii import RedactedText, RedactionResult, RegexPhonePiiEngine


@dataclass
class SpacyEnPiiEngine:
    name: ClassVar[str] = "spacy-en-sm/1"
    base: RegexPhonePiiEngine = field(default_factory=RegexPhonePiiEngine)
    _nlp: Any = None

    def supports(self, language: str) -> bool:
        return language.split("-")[0] == "en"

    def _model(self) -> Any:
        if self._nlp is None:
            import spacy

            self._nlp = spacy.load("en_core_web_sm", exclude=["parser", "lemmatizer", "tagger", "attribute_ruler"])
        return self._nlp

    def redact(self, text: str, *, language: str, country: str) -> RedactionResult:
        first = self.base.redact(text, language=language, country=country)
        if first.status == "UNSAFE" or not self.supports(language):
            return first
        doc = self._model()(str(first.text))
        out = str(first.text)
        counts = dict(first.counts)
        for ent in reversed([e for e in doc.ents if e.label_ == "PERSON"]):
            out = out[: ent.start_char] + "[PERSON]" + out[ent.end_char :]
            counts["PERSON"] = counts.get("PERSON", 0) + 1
        second = self.base.redact(out, language=language, country=country)  # kiểm tra lại sau NER
        return RedactionResult(RedactedText(out), second.status, self.name, counts, second.risks)
