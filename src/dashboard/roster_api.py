"""roster_api.py - The one place that talks to the vgs-stars roster API."""

import requests
import streamlit as st

# Cloud Run sleeps, so the first call of an evening waits for it to wake.
TIMEOUT = 30
# Long enough that the grid arrows do not wake the API over and over.
CACHE_TTL = "5m"
# FastAPI's own answer for a route the API has not built yet.
MISSING_ROUTE = ("Not Found", "Method Not Allowed")


class RosterError(Exception):
    """A roster call failed, with a message fit to show on the page."""

    def __init__(self, message: str, status: int | None = None):
        """Keep the HTTP status so callers can react to a 401 or a 404.

        Args:
            message (str): What went wrong, in words for the page.
            status (int | None): HTTP status, or None if the API was unreachable."""
        super().__init__(message)
        self.status = status


def roster_config(squadron: str) -> dict | None:
    """Get a squadron's API url and key.

    Args:
        squadron (str): Database name of the squadron, e.g. '661vgs'.

    Returns:
        dict | None: The url and key, or None if it has no roster."""
    # One API serves one squadron, so the squadron is the key of the map.
    return st.secrets.get("roster", {}).get(squadron.lower())


def error_message(detail: object, status: int) -> str:
    """Turn an API error body into one line for the page.

    Args:
        detail (object): The body's `detail`, a string or FastAPI's 422 list.
        status (int): HTTP status of the response.

    Returns:
        str: The message to show."""
    # The backend has not caught up with this feature yet.
    if detail in MISSING_ROUTE:
        return "Not available yet."
    # FastAPI's validation errors are a list of {"msg": ...}.
    if isinstance(detail, list):
        return " ".join(str(error.get("msg", "")) for error in detail).strip()
    return str(detail) if detail else f"The roster API failed ({status})."


def call(
    squadron: str,
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
) -> dict:
    """Make one roster API call with the squadron's key.

    Args:
        squadron (str): Database name of the squadron.
        method (str): HTTP method, e.g. 'GET'.
        path (str): API path, e.g. '/roster/months'.
        token (str | None): Session token for a named person's write.
        body (dict | None): JSON body to send.

    Returns:
        dict: The decoded response body, empty if there is none.

    Raises:
        RosterError: The API was unreachable or refused the call."""
    # Looked up in here, not passed in, so the key stays out of any cache key.
    config = roster_config(squadron)
    if config is None:
        raise RosterError(f"No roster API is configured for {squadron}.")

    headers = {"X-API-Key": config["key"]}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method,
            f"{config['url'].rstrip('/')}{path}",
            headers=headers,
            json=body,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RosterError("Could not reach the roster. Try again shortly.") from exc

    try:
        payload = response.json() if response.content else {}
    except ValueError:
        payload = {}
    if not response.ok:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        status = response.status_code
        raise RosterError(error_message(detail, status), status)
    return payload


@st.cache_data(ttl=CACHE_TTL, show_spinner="Loading roster...")
def read(squadron: str, path: str) -> dict:
    """Read with the squadron's read-only key, cached in memory, never on disk.

    Args:
        squadron (str): Database name of the squadron.
        path (str): API path, e.g. '/roster/months'.

    Returns:
        dict: The decoded response body."""
    return call(squadron, "GET", path)


def send(
    squadron: str,
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
) -> dict:
    """Write to the API, then drop cached reads so the page shows the write.

    Args:
        squadron (str): Database name of the squadron.
        method (str): HTTP method, e.g. 'PUT'.
        path (str): API path.
        token (str | None): Session token of the person writing.
        body (dict | None): JSON body to send.

    Returns:
        dict: The decoded response body."""
    result = call(squadron, method, path, token, body)
    # ponytail: clears every cached read, per-path clearing if it gets slow.
    read.clear()
    return result
