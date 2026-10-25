"""Local account management and authorization helpers."""

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from fastapi import Depends, HTTPException, Request

USER_STORE_PATH = Path(os.getenv("AUTH_USERS_FILE", Path(__file__).with_name("auth_users.json")))
AUDIT_LOG_PATH = Path(os.getenv("AUTH_AUDIT_LOG", Path(__file__).with_name("auth_audit.jsonl")))
PASSWORD_ITERATIONS = 310_000
VALID_PRACTICE_AREAS = {"Technology", "Strategy", "Operations"}
_user_store_lock = RLock()
_audit_log_lock = RLock()


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@slalom\.com", normalized):
        raise ValueError("Use a valid @slalom.com email address")
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def load_users() -> dict:
    if not USER_STORE_PATH.exists():
        return {}
    try:
        users = json.loads(USER_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("The authentication user store could not be read") from error
    if not isinstance(users, dict):
        raise RuntimeError("The authentication user store must contain a JSON object")
    return users


def save_users(users: dict) -> None:
    USER_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = USER_STORE_PATH.with_name(USER_STORE_PATH.name + ".tmp")
    temporary_path.write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")
    temporary_path.chmod(0o600)
    temporary_path.replace(USER_STORE_PATH)
    USER_STORE_PATH.chmod(0o600)


def public_user(user: dict) -> dict:
    return {
        "email": user["email"],
        "role": user["role"],
        "practice_areas": user["practice_areas"],
    }


def create_user(email: str, password: str, role: str, practice_areas: list[str] | None = None) -> dict:
    normalized_email = normalize_email(email)
    if role not in {"consultant", "practice_lead"}:
        raise ValueError("Role must be consultant or practice_lead")
    areas = sorted(set(practice_areas or []))
    if role == "practice_lead" and not areas:
        raise ValueError("Practice leads must have at least one practice area")
    if role == "practice_lead" and (
        any(area not in VALID_PRACTICE_AREAS and area != "*" for area in areas)
        or ("*" in areas and len(areas) > 1)
    ):
        raise ValueError("Use Technology, Strategy, Operations, or * as the practice area")
    record = {
        "email": normalized_email,
        "password_hash": hash_password(password),
        "role": role,
        "practice_areas": areas,
    }
    with _user_store_lock:
        users = load_users()
        if normalized_email in users:
            raise ValueError("An account already exists for this email")
        users[normalized_email] = record
        save_users(users)
    return public_user(record)


def authenticate_user(email: str, password: str) -> dict | None:
    try:
        normalized_email = normalize_email(email)
    except ValueError:
        return None
    user = load_users().get(normalized_email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        return None
    return public_user(user)


def write_audit_event(actor: str, action: str, capability: str | None = None, target: str | None = None) -> None:
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "actor": actor,
        "action": action,
        "capability": capability,
        "target": target,
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _audit_log_lock:
        descriptor = os.open(
            AUDIT_LOG_PATH,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT,
            0o600,
        )
        try:
            os.write(descriptor, (json.dumps(event) + "\n").encode("utf-8"))
        finally:
            os.close(descriptor)


def get_current_user(request: Request) -> dict:
    email = request.session.get("email")
    user = load_users().get(email) if email else None
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required")
    return public_user(user)


def require_user(user: dict = Depends(get_current_user)) -> dict:
    return user


def require_csrf(request: Request, user: dict = Depends(get_current_user)) -> dict:
    expected = request.session.get("csrf_token", "")
    supplied = request.headers.get("x-csrf-token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    return user


def require_practice_lead(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "practice_lead":
        raise HTTPException(status_code=403, detail="Practice lead access required")
    return user


def user_has_capability_access(user: dict, capability: dict) -> bool:
    return user["role"] != "practice_lead" or "*" in user["practice_areas"] or (
        capability["practice_area"] in user["practice_areas"]
    )