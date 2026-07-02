"""test_session.py - Tests for the login-persistence cookie helpers."""

import json
import time

import pytest
from cryptography.fernet import Fernet

from dashboard import session


@pytest.fixture
def fixed_cipher(monkeypatch):
    """Give the session helpers a fixed, in-memory Fernet cipher.

    Avoids depending on st.secrets so the tests are deterministic."""
    key = Fernet.generate_key()
    monkeypatch.setattr(session, "_fernet", lambda: Fernet(key))
    return Fernet(key)


def test_encrypt_decrypt_round_trip(fixed_cipher):
    """Credentials survive an encrypt -> decrypt round trip."""
    token = session.encrypt_credentials("661vgs", "s3cret")
    assert token
    assert session.decrypt_credentials(token) == ("661vgs", "s3cret")


def test_decrypt_tampered_token_returns_none(fixed_cipher):
    """A tampered token is rejected."""
    token = session.encrypt_credentials("661vgs", "s3cret")
    assert token is not None
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    assert session.decrypt_credentials(tampered) is None


def test_decrypt_expired_token_returns_none(fixed_cipher):
    """A token older than _MAX_AGE is rejected (ttl enforced server-side)."""
    payload = json.dumps({"u": "661vgs", "p": "s3cret"}).encode()
    old_time = int(time.time()) - (session._MAX_AGE + 3600)
    token = fixed_cipher.encrypt_at_time(payload, old_time).decode()
    assert session.decrypt_credentials(token) is None


def test_missing_secret_disables_persistence(monkeypatch):
    """With no COOKIE_SECRET configured the helpers no-op."""
    monkeypatch.setattr(session, "_fernet", lambda: None)
    assert session.encrypt_credentials("661vgs", "s3cret") is None
    assert session.decrypt_credentials("anything") is None


def test_malformed_secret_disables_persistence(monkeypatch):
    """A malformed COOKIE_SECRET disables persistence instead of crashing."""
    # A non-32-byte base64 key makes Fernet() raise; _fernet must swallow it.
    monkeypatch.setattr(session.st, "secrets", {"COOKIE_SECRET": "not-a-valid-key"})
    assert session._fernet() is None
    assert session.encrypt_credentials("661vgs", "s3cret") is None
