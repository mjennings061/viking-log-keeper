"""roster.py - Squadron availability grid, read from the vgs-stars API."""

from datetime import date

import pandas as pd
import requests
import streamlit as st

from dashboard import logger

# Translucent, so the tint reads on a light or a dark theme.
STATUS_COLOURS = {
    "Y": "rgba(40, 167, 69, 0.25)",
    "N": "rgba(220, 53, 69, 0.25)",
    "TBC": "rgba(255, 193, 7, 0.25)",
}
# Drawn where nobody has answered.
BLANK = "–"
# Cloud Run sleeps, so the first call of an evening waits for it to wake.
TIMEOUT = 30
# Long enough that the month arrows do not wake the API over and over.
CACHE_TTL = "5m"


def roster_config(squadron: str) -> dict | None:
    """Get a squadron's API url and key.

    Args:
        squadron (str): Database name of the squadron, e.g. '661vgs'.

    Returns:
        dict | None: The url and key, or None if it has no roster."""
    # One API serves one squadron, so the squadron is the key of the map.
    return st.secrets.get("roster", {}).get(squadron.lower())


@st.cache_data(ttl=CACHE_TTL, show_spinner="Loading roster...")
def fetch(squadron: str, path: str) -> dict:
    """Read a path from the roster API with that squadron's read-only key.

    Args:
        squadron (str): Database name of the squadron.
        path (str): API path, e.g. '/roster/months'.

    Returns:
        dict: The decoded response body."""
    # Looked up in here, not passed in, so the key stays out of the cache key.
    config = roster_config(squadron)
    if config is None:
        raise KeyError(f"No roster API is configured for {squadron}.")

    response = requests.get(
        f"{config['url'].rstrip('/')}{path}",
        headers={"X-API-Key": config["key"]},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def grid_to_frame(grid: dict) -> pd.DataFrame:
    """Turn a month of answers into a grid.

    Args:
        grid (dict): The API's grid response.

    Returns:
        pd.DataFrame: A row per person; Name, Cat, then a column per date."""
    # Day numbers are unique in a month, so "Sat 07" is heading enough.
    columns = {
        day: date.fromisoformat(day).strftime("%a %d") for day in grid["dates"]
    }

    rows = []
    for row in grid["rows"]:
        entries = row.get("entries", {})
        rows.append({
            "Name": row["name"],
            "Cat": row.get("instructCat") or "",
            **{
                heading: entries.get(day, {}).get("status", BLANK)
                for day, heading in columns.items()
            },
        })

    # Naming the columns keeps every date on the grid, answered or not.
    return pd.DataFrame(rows, columns=["Name", "Cat", *columns.values()])


def _tint(value: object) -> str:
    """Get the cell background for one answer.

    Args:
        value (object): The answer, or the blank dash, as the styler passes it.

    Returns:
        str: A CSS background rule, or empty to leave the cell alone."""
    colour = STATUS_COLOURS.get(str(value))
    return f"background-color: {colour}" if colour else ""


def _month_picker(months: list[str]) -> str:
    """Show the chosen month with an arrow either side.

    Args:
        months (list[str]): Months as '2026-11', newest first.

    Returns:
        str: The month to draw."""
    chosen = st.session_state.get("roster_month")
    if chosen not in months:
        chosen = months[0]
    index = months.index(chosen)

    # Months come newest first, so going back moves along the list, not against.
    back, title, forward = st.columns([1, 6, 1], vertical_alignment="center")
    if back.button("◀", disabled=index >= len(months) - 1, width="stretch",
                   help="Previous month"):
        index += 1
    if forward.button("▶", disabled=index <= 0, width="stretch",
                      help="Next month"):
        index -= 1

    chosen = months[index]
    title.subheader(date.fromisoformat(f"{chosen}-01").strftime("%B %Y"))
    st.session_state["roster_month"] = chosen
    return chosen


def roster_page(squadron: str) -> None:
    """Display a month of squadron availability.

    Args:
        squadron (str): Database name of the squadron."""
    st.header("Roster")

    # main.py logs the user out on an uncaught error, so nothing escapes here.
    try:
        months = fetch(squadron, "/roster/months")["months"]
        if not months:
            st.info("No months have been set up yet.")
            return

        month = _month_picker(months)
        grid = fetch(squadron, f"/roster/months/{month}/grid")
    except Exception:  # pylint: disable=broad-except
        logger.error("Failed to load the roster.", exc_info=True)
        st.error("Could not load the roster. Try again shortly.")
        return

    if grid["frozen"]:
        st.caption(f"🔒 Frozen since {grid['freezeAt']}. Ask an exec to change an answer.")
    else:
        st.caption(f"Freezes on {grid['freezeAt']}.")

    frame = grid_to_frame(grid)
    if frame.empty:
        st.info("Nobody is on the roster for this month yet.")
        return

    # Pin the name, or it scrolls out of view and the grid answers nothing.
    st.dataframe(
        frame.style.map(_tint, subset=list(frame.columns[2:])),
        column_config={
            "Name": st.column_config.Column(pinned=True),
            "Cat": st.column_config.Column("Cat", pinned=True,
                                           help="Instructor category from STARS."),
        },
        hide_index=True,
        width="stretch",
    )
