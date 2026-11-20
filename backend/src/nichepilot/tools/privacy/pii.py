"""Che thông tin cá nhân (PII) – FR-012a…c, SC-016; research R-05; quyết định I2 (2026-11-20 (b)).

- `PiiEngine` là interface thay thế được. Engine mặc định (production): `RegexPhonePiiEngine` = regex + `phonenumbers` +
  bộ phát hiện nguy cơ tên người (heuristic). Regex KHÔNG được coi là đủ: đoạn chỉ `REDACTED` khi không còn nguy cơ.
- `NEEDS_REVIEW`: lưu bản đã che phần xác định được, KHÔNG tính ngưỡng, KHÔNG gửi AI.
- `UNSAFE`: còn mẫu PII sau khi che → đoạn phải bị bỏ (không lưu, không gửi AI).
- Chạy trong handler của tool (`page.fetch`, `source.query`) vì Tool Registry E0 lưu output tool vào `tool_executions`.
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, Literal, NewType, Protocol

import phonenumbers

from nichepilot.core.config import ConfigError
from nichepilot.core.discovery_config import DiscoverySettings, validate_discovery_settings

RedactedText = NewType("RedactedText", str)
RedactionStatus = Literal["REDACTED", "NEEDS_REVIEW", "UNSAFE"]
LABELS = ("EMAIL", "PHONE", "USER", "PERSON")


@dataclass(frozen=True)
class RedactionResult:
    text: RedactedText
    status: RedactionStatus
    engine: str
    counts: dict[str, int] = field(default_factory=dict)
    risks: tuple[str, ...] = ()  # loại nguy cơ (không chứa nội dung): "PERSON_NAME", "RESIDUAL_EMAIL", …


class PiiUnsafeError(Exception):
    """Nội dung chưa an toàn để gửi AI (NEEDS_REVIEW hoặc UNSAFE)."""


class PiiEngine(Protocol):
    name: str

    def supports(self, language: str) -> bool: ...

    def redact(self, text: str, *, language: str, country: str) -> RedactionResult: ...


def ensure_ai_safe(result: RedactionResult) -> RedactedText:
    """Cổng duy nhất để lấy văn bản gửi AI: chỉ `REDACTED` mới qua (FR-012a, FR-012b)."""
    if result.status != "REDACTED":
        raise PiiUnsafeError(result.status)
    return result.text


# --------------------------------------------------------------------------------------------------------------------
# Mẫu xác định
# --------------------------------------------------------------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PROFILE_URL_RE = re.compile(
    r"https?://[^\s]*?/(?:u|user|users|profile|profiles|member|members|people|author|authors)/[^\s/?#]+[^\s]*",
    re.IGNORECASE,
)
REDDIT_USER_RE = re.compile(r"(?<![\w/])/?u/[A-Za-z0-9_-]{3,}")
HANDLE_RE = re.compile(r"(?<![\w@.])@[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?\b")
BYLINE_RE = re.compile(
    r"\b((?i:posted|written|submitted|answered|reviewed|shared|asked|replied)\s+(?i:by))\s+"
    r"([^\W\d_][\w'’-]*(?:\s+[^\W\d_][\w'’-]*){0,2})"
)
# Kiểm tra lại (sau khi che): email bị làm rối, chuỗi số dài kiểu số điện thoại
RESIDUAL_EMAIL_RE = re.compile(
    r"[\w.+-]+\s*@\s*[\w-]+(?:\s*\.\s*[A-Za-z]{2,})+|[\w.+-]+\s*[(\[]\s*at\s*[)\]]\s*[\w-]+", re.IGNORECASE
)
RESIDUAL_DIGITS_RE = re.compile(r"\+?\d(?:[\s().-]*\d){8,}")

# --------------------------------------------------------------------------------------------------------------------
# Nguy cơ tên người (heuristic thận trọng: thà đánh dấu thừa còn hơn gửi tên người cho AI)
# --------------------------------------------------------------------------------------------------------------------
GREETING_RE = re.compile(
    r"\b(?i:thanks|thank\s+you|cheers|regards|best|hi|hello|hey|dear|greetings)\b[,!.:]?\s+[^\W\d_a-z][^\W\d_]*"
)
WORD_RE = re.compile(r"[^\W\d_][\w'’-]*")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?:;])\s+|\n+")
SENTENCE_STARTERS = frozenset(
    """a an the this that these those in on at for from to of by with if when what where which who whom whose why how
    is are was were be been do does did can could should would will may might must i my our we us you your it its they
    their there here last next every many most some several each all any no not please also however but and or so yet
    after before during since while because although though as just only even still then today yesterday tomorrow
    hello hi hey thanks dear review sponsored copyright home menu login sign verify""".split()
)
COMMON_CAPS = frozenset(
    """i monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
    september october november december""".split()
)
CUE_WORDS = frozenset(
    "told asked emailed messaged called met named says said texted thanked contacted mr mrs ms dr miss sir madam"
    " with to from".split()  # "with/to/from": phát hiện qua bộ đo T131 ("I talked with Maria…")
)


def _is_title(word: str) -> bool:
    core = word.replace("'", "").replace("’", "").replace("-", "")
    return len(core) >= 2 and core[0].isupper() and core[1:].islower()


@dataclass
class PersonNameRiskDetector:
    """Trả về danh sách loại nguy cơ (không trả nội dung)."""

    def detect(self, text: str, *, language: str) -> list[str]:
        risks: list[str] = []
        if GREETING_RE.search(text):
            risks.append("GREETING_OR_SIGNATURE")
        for sentence in SENTENCE_SPLIT_RE.split(text):
            words = list(WORD_RE.finditer(sentence))
            for run_start, run in _title_runs(sentence, words):
                tokens = run
                if run_start == 0 and tokens[0].lower() in SENTENCE_STARTERS:
                    tokens = tokens[1:]
                if len([t for t in tokens if t.lower() not in COMMON_CAPS]) >= 2:
                    risks.append("PERSON_NAME")
            for idx in range(1, len(words)):
                token = words[idx].group(0)
                if _is_title(token) and words[idx - 1].group(0).lower() in CUE_WORDS and token.lower() not in COMMON_CAPS:
                    risks.append("PERSON_NAME_AFTER_CUE")
        return risks


def _title_runs(sentence: str, words: list[re.Match[str]]) -> list[tuple[int, list[str]]]:
    """Các cụm từ viết hoa kiểu tên (Title-case) liền nhau, cách nhau đúng một khoảng trắng."""
    runs: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 0
    for idx, m in enumerate(words):
        token = m.group(0)
        joined = bool(current) and sentence[words[idx - 1].end() : m.start()] == " "
        if _is_title(token) and (not current or joined):
            if not current:
                start = idx
            current.append(token)
            continue
        if current:
            runs.append((start, current))
        current, start = ([token], idx) if _is_title(token) else ([], idx)
    if current:
        runs.append((start, current))
    return runs


@dataclass
class RegexPhonePiiEngine:
    name: ClassVar[str] = "regex-phone/1"
    detector: PersonNameRiskDetector = field(default_factory=PersonNameRiskDetector)

    def supports(self, language: str) -> bool:
        return language.split("-")[0] == "en"

    def redact(self, text: str, *, language: str, country: str) -> RedactionResult:
        counts: dict[str, int] = {}

        def sub(pattern: re.Pattern[str], label: str, value: str, repl: Callable[[re.Match[str]], str] | None = None) -> str:
            def _r(m: re.Match[str]) -> str:
                counts[label] = counts.get(label, 0) + 1
                return repl(m) if repl else f"[{label}]"

            return pattern.sub(_r, value)

        out = sub(EMAIL_RE, "EMAIL", text)
        out = sub(PROFILE_URL_RE, "USER", out)
        out = sub(REDDIT_USER_RE, "USER", out)
        out = sub(HANDLE_RE, "USER", out)
        out = sub(BYLINE_RE, "PERSON", out, lambda m: f"{m.group(1)} [PERSON]")
        out = self._phones(out, country, counts)

        risks: list[str] = []
        if RESIDUAL_EMAIL_RE.search(out):
            risks.append("RESIDUAL_EMAIL")
        if RESIDUAL_DIGITS_RE.search(out):
            risks.append("RESIDUAL_PHONE")
        status: RedactionStatus
        if risks:
            status = "UNSAFE"
        else:
            risks = self.detector.detect(out, language=language)
            if not self.supports(language) and _has_title_pair(out):
                risks.append("UNSUPPORTED_LANGUAGE")
            status = "NEEDS_REVIEW" if risks else "REDACTED"
        return RedactionResult(RedactedText(out), status, self.name, counts, tuple(dict.fromkeys(risks)))

    @staticmethod
    def _phones(text: str, country: str, counts: dict[str, int]) -> str:
        region = country.upper() if len(country) == 2 else None
        matches = list(phonenumbers.PhoneNumberMatcher(text, region, leniency=phonenumbers.Leniency.POSSIBLE))
        for m in reversed(matches):
            text = text[: m.start] + "[PHONE]" + text[m.end :]
            counts["PHONE"] = counts.get("PHONE", 0) + 1
        return text


def _has_title_pair(text: str) -> bool:
    words = [m.group(0) for m in WORD_RE.finditer(text)]
    return any(_is_title(a) and _is_title(b) for a, b in zip(words, words[1:], strict=False))


def _spacy_model_available() -> bool:
    return importlib.util.find_spec("spacy") is not None and importlib.util.find_spec("en_core_web_sm") is not None


def select_pii_engine(
    settings: DiscoverySettings, *, model_available: Callable[[], bool] = _spacy_model_available
) -> PiiEngine:
    """Chọn engine theo cấu hình – fail-closed; KHÔNG bao giờ tải model lúc chạy."""
    validate_discovery_settings(settings)
    if settings.pii_engine == "regex-phone":
        return RegexPhonePiiEngine()
    if settings.pii_engine == "spacy-en-sm":
        if not model_available():
            raise ConfigError("PII_ENGINE_NOT_APPROVED", "spacy-en-sm cần model có sẵn trong image (nhóm pii-ner)")
        from nichepilot.tools.privacy.pii_spacy import SpacyEnPiiEngine

        return SpacyEnPiiEngine()
    raise ConfigError("PII_ENGINE_NOT_APPROVED", settings.pii_engine)
