"""session.py - Persist the dashboard login across page refreshes.

Encryption uses ``st.secrets["COOKIE_SECRET"]``. If that secret is not configured
the helpers no-op and the app falls back to its previous behaviour"""

import json
from datetime import datetime, timedelta
from typing import Optional, Tuple

import extra_streamlit_components as stx
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken

from dashboard import logger

# Name of the browser cookie holding the encrypted credentials.
COOKIE_NAME = "vgs_auth"
# How many days a login is remembered for.
COOKIE_DAYS = 10
# Fernet max token age (seconds).
_MAX_AGE = COOKIE_DAYS * 24 * 60 * 60


def get_cookie_manager() -> stx.CookieManager:
    """Return the cookie manager component.

    Returns:
        stx.CookieManager: The cookie manager."""
    return stx.CookieManager(key="vgs_cookies")


def _fernet() -> Optional[Fernet]:
    """Build the Fernet cipher from the configured secret.

    Returns:
        Optional[Fernet]: The cipher, or None if ``COOKIE_SECRET`` is unset."""
    secret = st.secrets.get("COOKIE_SECRET")
    return Fernet(secret.encode()) if secret else None


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
        token is missing, tampered with, expired, or encryption is
        unavailable."""
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
    """Absolute expiry timestamp for a freshly-set auth cookie.

    Returns:
        datetime: ``COOKIE_DAYS`` from now."""
    return datetime.now() + timedelta(days=COOKIE_DAYS)
