"""Tiện ích bảo mật dùng chung (T049 – FR-052, FR-053): băm mật khẩu Argon2id, token phiên, CSRF.

Dependency xác thực theo request nằm ở `nichepilot.api.deps` để giữ phân tầng (core không import modules).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

SESSION_COOKIE = "np_session"
CSRF_COOKIE = "np_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_hasher = PasswordHasher()  # Argon2id, tham số mặc định khuyến nghị của argon2-cffi
# Hash giả để thời gian xử lý tên đăng nhập không tồn tại tương đương tên tồn tại (chống dò tài khoản).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_valid(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def key_hint(secret: str | None) -> str | None:
    """Gợi ý tối đa 4 ký tự cuối – không bao giờ trả về giá trị key."""
    if not secret or len(secret) < 12:
        return None
    return "…" + secret[-4:]
