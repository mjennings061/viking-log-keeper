"""test_logout.py - Tests for clearing per-user state across logins.

Regression cover for the "Database name is required" crash when switching
accounts: a previous user's db_name leaked past logout into the next login."""

from unittest.mock import MagicMock, patch

import pytest

from dashboard import main


@pytest.fixture
def session_state(monkeypatch):
    """Replace st.session_state with a plain dict for the duration of a test."""
    state = {}
    monkeypatch.setattr(main.st, "session_state", state)
    return state


def test_clear_user_data_removes_only_user_keys(session_state):
    """Per-user keys are dropped; unrelated flags are left alone."""
    session_state.update({key: "leaked" for key in main._USER_DATA_KEYS})
    session_state.update({"_logging_out": True, "_cookies_settled": True})

    main._clear_user_data()

    assert session_state == {"_logging_out": True, "_cookies_settled": True}


def test_process_logout_clears_auth_and_user_data(session_state):
    """A pending logout wipes auth and cached data but keeps _logging_out set."""
    session_state.update({
        "_logging_out": True,
        "authenticated": True,
        "client": object(),
        "_auth_token": "tok",
        "db_name": "661vgs",
        "log_sheet_db": object(),
        "df": object(),
    })

    with patch.object(main, "clear_auth_cookie") as clear_cookie:
        main._process_logout(MagicMock())

    clear_cookie.assert_called_once()
    # _logging_out must survive so restore stays suppressed until next login.
    assert session_state == {"_logging_out": True}


def test_process_logout_noop_when_not_pending(session_state):
    """Without a pending logout, nothing is touched."""
    session_state.update({"authenticated": True, "db_name": "661vgs"})

    with patch.object(main, "clear_auth_cookie") as clear_cookie:
        main._process_logout(MagicMock())

    clear_cookie.assert_not_called()
    assert session_state == {"authenticated": True, "db_name": "661vgs"}


def test_set_db_ignores_empty_db_name(session_state):
    """A stale on_change with no selection must not build a Database."""
    session_state.update({"db_name": None, "client": object()})

    with patch.object(main, "Database") as db_cls:
        main.set_db()

    db_cls.assert_not_called()
    assert "log_sheet_db" not in session_state


def test_set_db_builds_database_for_valid_name(session_state):
    """A real selection still constructs and stores the Database."""
    client = object()
    session_state.update({"db_name": "661vgs", "client": client})
    fake_db = object()

    with patch.object(main, "Database", return_value=fake_db) as db_cls, \
            patch.object(main, "refresh_data"):
        main.set_db()

    db_cls.assert_called_once_with(client=client, database_name="661vgs")
    assert session_state["log_sheet_db"] is fake_db
