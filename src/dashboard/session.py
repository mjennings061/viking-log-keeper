"""session.py - Persist the dashboard login across page refreshes.

Encryption uses ``st.secrets["COOKIE_SECRET"]``. If that secret is not configured
the helpers no-op and the app falls back to its previous behaviour"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import extra_streamlit_components as stx
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken

from dashboard import logger

# Name of the browser cookie holding the encrypted credentials.
COOKIE_NAME = "vgs_auth"
# Session-state key caching the browser's cookies; must survive a logout wipe.
COOKIE_MANAGER_KEY = "vgs_cookies"
# How many days a login is remembered for.
COOKIE_DAYS = 10
# Fernet max token age (seconds).
_MAX_AGE = COOKIE_DAYS * 24 * 60 * 60


def get_cookie_manager() -> stx.CookieManager:
    """Return the cookie manager component.

    Returns:
        stx.CookieManager: The cookie manager."""
    return stx.CookieManager(key=COOKIE_MANAGER_KEY)


def _fernet() -> Optional[Fernet]:
    """Build the Fernet cipher from the configured secret.

    Returns:
        Optional[Fernet]: The cipher, or None if ``COOKIE_SECRET`` is unset or
        malformed - persistence then disables itself rather than breaking
        login (Fernet raises ValueError on a non-32-byte base64 key)."""
    secret = st.secrets.get("COOKIE_SECRET")
    if not secret:
        return None
    try:
        return Fernet(secret.encode())
    except (ValueError, TypeError):
        logger.warning("COOKIE_SECRET is malformed; login persistence disabled.")
        return None


def persistence_available() -> bool:
    # Persistence needs COOKIE_SECRET (Streamlit Cloud: Settings -> Secrets).
    return _fernet() is not None


def encrypt_credentials(username: str, password: str) -> Optional[str]:
    """Encrypt login credentials for storage in a cookie.

    Args:
        username (str): The VGS username.
        password (str): The VGS password.

    Returns:
        Optional[str]: The encrypted token, or None if encryption is
        unavailable (no ``COOKIE_SECRET``)."""
    cipher = _fernet()
    if not cipher:
        return None
    payload = json.dumps({"u": username, "p": password}).encode()
    return cipher.encrypt(payload).decode()


def decrypt_credentials(token: str) -> Optional[Tuple[str, str]]:
    """Decrypt a credentials token read from a cookie.

    Args:
        token (str): The encrypted token.

    Returns:
        Optional[Tuple[str, str]]: ``(username, password)``, or None if the
        token is missing, tampered with, expired, or encryption is unavailable."""
    cipher = _fernet()
    if not cipher or not token:
        return None
    try:
        payload = json.loads(cipher.decrypt(token.encode(), ttl=_MAX_AGE))
        return payload["u"], payload["p"]
    except (InvalidToken, ValueError, KeyError):
        logger.warning("Ignoring invalid or expired auth cookie.")
        return None


def cookie_expiry() -> datetime:
    """Absolute (UTC) expiry timestamp for a freshly-set auth cookie.

    Returns:
        datetime: ``COOKIE_DAYS`` from now, in UTC."""
    return datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS)


def clear_auth_cookie(cookie_manager, key: str = "del_auth") -> None:
    """Remove the auth cookie by overwriting it expired, with matching attrs."""
    # delete() uses non-matching attributes and fails.
    cookie_manager.set(
        COOKIE_NAME,
        "",
        key=key,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        same_site="lax",
        secure=True,
    )
