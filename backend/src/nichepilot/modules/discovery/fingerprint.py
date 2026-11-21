"""Dấu vân tay nội dung (FR-015; research R-06): eTLD+1 (offline), SimHash 64-bit, SHA-256.

tldextract dùng snapshot Public Suffix List đóng gói (`suffix_list_urls=()`) – KHÔNG tải mạng lúc chạy.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from urllib.parse import urlsplit

import tldextract

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


@lru_cache(maxsize=1)
def _extractor() -> tldextract.TLDExtract:
    return tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True)


def registered_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    ext = _extractor()(host)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    labels = [x for x in host.split(".") if x]
    if len(labels) >= 2 and not all(x.isdigit() for x in labels):
        # hậu tố không có trong PSL (vd. `.example`, `.internal`): coi nhãn cuối là hậu tố → eTLD+1 = 2 nhãn cuối
        return ".".join(labels[-2:])
    return host


def normalize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def simhash64(text: str) -> int:
    """SimHash 64-bit (signed – vừa cột BIGINT) trên shingle 2 từ đã chuẩn hóa."""
    tokens = normalize(text)
    shingles = [" ".join(tokens[i : i + 2]) for i in range(max(1, len(tokens) - 1))] if tokens else [""]
    vector = [0] * 64
    for sh in shingles:
        h = int.from_bytes(hashlib.blake2b(sh.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            vector[bit] += 1 if (h >> bit) & 1 else -1
    value = sum(1 << bit for bit in range(64) if vector[bit] > 0)
    return value - (1 << 64) if value >= (1 << 63) else value


def hamming(a: int, b: int) -> int:
    return ((a ^ b) & ((1 << 64) - 1)).bit_count()


def shingles(text: str, k: int = 3) -> set[str]:
    tokens = normalize(text)
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def shingle_containment(a: str, b: str, k: int = 3) -> float:
    """|A∩B| / min(|A|,|B|) trên shingle k từ – phát hiện bản gần giống/trích một phần (bổ sung cho SimHash)."""
    sa, sb = shingles(a, k), shingles(b, k)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
