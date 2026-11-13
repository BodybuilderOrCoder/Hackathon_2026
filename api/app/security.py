import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240_000)
    return f"pbkdf2_sha256${salt}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, expected = stored.split("$", 2)
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(hash_password(password, salt), stored)
    except ValueError:
        return False


def issue_token(user: User) -> str:
    settings = get_settings()
    payload = {"sub": user.id, "org": user.organization_id,
               "exp": int((datetime.utcnow() + timedelta(seconds=settings.session_ttl_seconds)).timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(settings.fleetmix_secret_key.encode(), body.encode(), hashlib.sha256).digest()
    return body + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")


def decode_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(get_settings().fleetmix_secret_key.encode(), body.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, actual):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if payload["exp"] < int(datetime.utcnow().timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired") from exc


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("fleetmix_session") or request.headers.get("authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required")
    claims = decode_token(token)
    user = db.scalar(select(User).where(User.id == claims["sub"], User.organization_id == claims["org"], User.active.is_(True)))
    if not user:
        raise HTTPException(status_code=401, detail="User session is no longer active")
    return user
