"""roster_signin.py - Signing in by emailed code, and writing as that person."""

import re
from datetime import datetime

import streamlit as st

from dashboard import logger
from dashboard.roster_api import RosterError, call, read, send
from dashboard.session import (
    COOKIE_ATTRS,
    clear_auth_cookie,
    decrypt_value,
    encrypt_value,
)

# Browser cookie holding the encrypted roster session token.
ROSTER_COOKIE = "vgs_roster"
GRID, YOUR_DATES = "Squadron grid", "Your dates"

# -- Signing in ---------------------------------------------------------------


def signed_in() -> dict | None:
    """The signed-in person, as GET /roster/auth/me returns them."""
    return st.session_state.get("roster_me")


def is_admin() -> bool:
    """Whether the signed-in person is an admin."""
    me = signed_in()
    return bool(me) and me["role"] == "admin"


def can_edit(person_id: str) -> bool:
    """Admins edit anyone; members only their own row."""
    me = signed_in()
    return bool(me) and (me["role"] == "admin" or me["personId"] == person_id)


def flash(message: str) -> None:
    """Show a toast on the next run, so it survives a dialog closing."""
    st.session_state["roster_flash"] = message


def drop_sign_in() -> None:
    """Forget the roster session and clear its cookie on this run."""
    for key in ("roster_token", "roster_me", "roster_layout"):
        st.session_state.pop(key, None)
    # None means clear it; _sync_cookie does the write.
    st.session_state["roster_cookie"] = None


def sync_cookie(cookie_manager) -> None:
    """Make the roster cookie match what the page wants, one write per run.

    Args:
        cookie_manager: The dashboard's cookie manager component."""
    if "roster_cookie" not in st.session_state:
        return
    want = st.session_state["roster_cookie"]
    have = cookie_manager.get(ROSTER_COOKIE)
    if want is None:
        if have:
            clear_auth_cookie(cookie_manager, key="del_roster", name=ROSTER_COOKIE)
        else:
            st.session_state.pop("roster_cookie")
    elif have != want["value"]:
        # Rewritten on later runs until the browser reports it, so a clash heals.
        cookie_manager.set(
            ROSTER_COOKIE,
            want["value"],
            key="set_roster",
            expires_at=want["expires"],
            **COOKIE_ATTRS,
        )


def restore(squadron: str, cookie_manager) -> None:
    """Sign a remembered device back in, once per session.

    Args:
        squadron (str): Database name of the squadron.
        cookie_manager: The dashboard's cookie manager component."""
    if signed_in() or st.session_state.get("roster_checked"):
        return
    st.session_state["roster_checked"] = True
    token = decrypt_value(cookie_manager.get(ROSTER_COOKIE) or "")
    if not token:
        return
    try:
        me = call(squadron, "GET", "/roster/auth/me", token)
    except RosterError as exc:
        # Expired or a leaver; anything else may be the API asleep, so keep it.
        if exc.status == 401:
            drop_sign_in()
        return
    st.session_state.update(roster_token=token, roster_me=me, roster_layout=_layout())


def _layout() -> str:
    """Phones open on their own dates, wider screens on the grid."""
    # ponytail: user agent, not width; Streamlit cannot see the screen size.
    agent = st.context.headers.get("User-Agent") or ""
    return YOUR_DATES if "Mobi" in agent else GRID


def _request_code(squadron: str) -> None:
    """Email a code to the picked person; a callback of 'Email me a code'."""
    person_id = st.session_state.get("roster_who")
    if not person_id:
        st.session_state["roster_signin_error"] = "Pick your name first."
        return
    try:
        result = call(
            squadron, "POST", "/roster/auth/request-code", body={"personId": person_id}
        )
    except RosterError as exc:
        st.session_state["roster_signin_error"] = str(exc)
        return
    st.session_state.update(roster_nonce=result["nonce"], roster_step="code")


def _verify(squadron: str) -> None:
    """Swap the emailed code for a session; a callback of 'Sign in'."""
    code = (st.session_state.get("roster_code") or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        st.session_state["roster_signin_error"] = "Enter the six digits from the email."
        return
    remember = st.session_state.get("roster_remember", True)
    body = {
        "nonce": st.session_state.get("roster_nonce"),
        "code": code,
        "rememberDevice": remember,
    }
    try:
        me = call(squadron, "POST", "/roster/auth/verify-code", body=body)
    except RosterError as exc:
        st.session_state["roster_signin_error"] = str(exc)
        return

    token = me.pop("token")
    st.session_state.update(roster_token=token, roster_me=me, roster_layout=_layout())
    for key in ("roster_step", "roster_nonce", "roster_code", "roster_who"):
        st.session_state.pop(key, None)
    # Not remembered, the token lives only as long as this browser tab.
    value = encrypt_value(token) if remember else None
    if value:
        expires = datetime.fromisoformat(me["expiresAt"].replace("Z", "+00:00"))
        st.session_state["roster_cookie"] = {"value": value, "expires": expires}
    flash(f"Signed in as {me['name']}{', admin' if me['role'] == 'admin' else ''}.")


def _sign_out(squadron: str) -> None:
    """End this device's session; a callback of 'Sign out'."""
    try:
        token = st.session_state.get("roster_token")
        call(squadron, "POST", "/roster/auth/logout", token)
    except RosterError:
        # Signing out here still works if the API cannot be told.
        logger.warning("Roster logout call failed.", exc_info=True)
    name = (signed_in() or {}).get("name", "You")
    drop_sign_in()
    flash(f"Signed out. {name} is asked for a code next time.")


def sign_in_bar(squadron: str) -> None:
    """The 'Update my roster' button, its two steps, or who is signed in.

    Args:
        squadron (str): Database name of the squadron."""
    state = st.session_state
    me = signed_in()
    if me:
        left, middle, right = st.columns([3, 2, 1], vertical_alignment="center")
        badge = " :blue-badge[Admin]" if is_admin() else ""
        left.markdown(f"Signed in as **{me['name']}**{badge}")
        middle.segmented_control(
            "Layout", [GRID, YOUR_DATES], key="roster_layout",
            label_visibility="collapsed",
        )
        right.button("Sign out", type="tertiary", on_click=_sign_out, args=(squadron,))
        return

    step = state.get("roster_step")
    if step is None:
        st.button("Update my roster", type="primary",
                  on_click=lambda: state.update(roster_step="who"))
        st.caption("Submit or edit your availability.")
        return

    with st.container(border=True):
        if step == "who":
            people = read(squadron, "/roster/people")["people"]
            names = {p["personId"]: p["name"] for p in people}
            st.selectbox("Who are you?", list(names), index=None,
                         placeholder="Pick your name",
                         format_func=lambda pid: names[pid], key="roster_who")
            send_col, cancel_col = st.columns([1, 4])
            send_col.button("Email me a code", type="primary",
                            on_click=_request_code, args=(squadron,))
            cancel_col.button("Cancel", type="tertiary",
                              on_click=lambda: state.pop("roster_step", None))
            st.caption("The code goes to the email STARS holds for that person.")
        else:
            names = {p["personId"]: p["name"]
                     for p in read(squadron, "/roster/people")["people"]}
            name = names.get(state.get("roster_who"), "you")
            with st.form("roster_code_form", border=False):
                st.markdown(f"Code sent to {name}'s email.")
                st.text_input("Six-digit code", max_chars=6, key="roster_code",
                              autocomplete="one-time-code")
                st.checkbox("Remember this device for 30 days", value=True,
                            key="roster_remember")
                st.form_submit_button("Sign in", type="primary",
                                      on_click=_verify, args=(squadron,))
            st.button(f"Not {name.split()[0]}?", type="tertiary",
                      on_click=lambda: state.update(roster_step="who"))
        if error := state.pop("roster_signin_error", None):
            st.error(error)


# -- Writing ------------------------------------------------------------------


def write(squadron: str, method: str, path: str, body: dict | None = None) -> dict:
    """Write as the signed-in person; a lapsed session signs them out.

    Args:
        squadron (str): Database name of the squadron.
        method (str): HTTP method.
        path (str): API path.
        body (dict | None): JSON body.

    Returns:
        dict: The API's response body.

    Raises:
        RosterError: The API refused or could not be reached."""
    try:
        return send(squadron, method, path, st.session_state.get("roster_token"), body)
    except RosterError as exc:
        if exc.status == 401:
            drop_sign_in()
        raise
