"""Shared bearer-token authentication for the user and message services."""

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer_scheme = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    secret = os.environ.get("SECRET_INBOX_AUTH_SECRET", "")
    if not secret:
        secret_file = Path(__file__).resolve().parent / ".env.local"
        if secret_file.is_file():
            secret = secret_file.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        raise RuntimeError("SECRET_INBOX_AUTH_SECRET must contain at least 32 characters.")
    return secret.encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: str) -> str:
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps(
        {"sub": user_id, "exp": int(time.time()) + 12 * 60 * 60},
        separators=(",", ":"),
    ).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _encode(hmac.new(_secret(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def verify_access_token(token: str) -> str:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _encode(hmac.new(_secret(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        decoded_header = json.loads(_decode(header))
        claims = json.loads(_decode(payload))
        if decoded_header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError
        user_id = claims["sub"]
        if not isinstance(user_id, str) or not user_id or claims["exp"] <= time.time():
            raise ValueError
        return user_id
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def authenticated_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_access_token(credentials.credentials)
