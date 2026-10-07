"""roster.py - Squadron availability: the page that ties the roster together."""

from datetime import date, datetime, timedelta

import streamlit as st

from dashboard import logger
from dashboard.roster_api import RosterError, read
from dashboard.roster_dialogs import (
    answer_dialog,
    course_dialog,
    dates_dialog,
    find_row,
    freeze_dialog,
    note_dialog,
    put_answer,
    remove_dialog,
)
from dashboard.roster_grid import (
    UK,
    choice_of,
    day_mon,
    describe,
    draw_grid,
    fmt_date,
    grid_path,
    long,
    order_grids,
    show_key,
    when,
)
from dashboard.roster_signin import (
    GRID,
    YOUR_DATES,
    flash,
    is_admin,
    restore,
    signed_in,
    sign_in_bar,
    sync_cookie,
    write,
)

# -- Page sections ------------------------------------------------------------


def _load_grids(squadron: str) -> tuple[list[dict], int]:
    """Every month and course, in date order, and which to open on."""
    months = read(squadron, "/roster/months")["months"]
    # Courses are optional; a backend without them still shows the months.
    try:
        courses = read(squadron, "/roster/courses")["courses"]
    except RosterError:
        logger.info("No courses from the roster API.", exc_info=True)
        courses = []
    return order_grids(months, courses, datetime.now(UK).date())


def _grid_picker(grids: list[dict], start: int) -> dict:
    """Show the chosen grid's title with an arrow either side.

    Args:
        grids (list[dict]): Grids in date order.
        start (int): Index to open on the first time.

    Returns:
        dict: The grid to draw."""
    ids = [g["id"] for g in grids]
    chosen = st.session_state.get("roster_grid")
    index = ids.index(chosen) if chosen in ids else start

    back, title, forward = st.columns([1, 6, 1], vertical_alignment="center")
    if back.button("◀", disabled=index <= 0, width="stretch", help="Previous grid"):
        index -= 1
    if forward.button("▶", disabled=index >= len(grids) - 1, width="stretch",
                      help="Next grid"):
        index += 1

    ref = grids[index]
    if ref["kind"] == "month":
        title.caption("Month")
    else:
        title.caption(f"Course, {day_mon(ref['first'].isoformat())} to "
                      f"{day_mon(ref['last'].isoformat())}")
    title.subheader(ref["title"])
    st.session_state["roster_grid"] = ref["id"]
    return ref


def _next_month(grids: list[dict]) -> str:
    """The month after the latest one open, or next month if none are."""
    months = [g["first"] for g in grids if g["kind"] == "month"]
    latest = max(months) if months else datetime.now(UK).date().replace(day=1)
    return f"{(latest + timedelta(days=32)).replace(day=1):%Y-%m}"


def _admin_tools(squadron: str, ref: dict | None, grid: dict | None, grids: list):
    """Buttons for admins to shape the grids.

    Args:
        squadron (str): Database name of the squadron.
        ref (dict | None): The grid on show, None if there are none yet.
        grid (dict | None): Its API body.
        grids (list): Every grid, to work out the next month."""
    cols = st.columns(5)
    if ref and grid and cols[0].button("Edit dates", width="stretch"):
        dates_dialog(squadron, ref, grid)
    if ref and grid and cols[1].button("Move freeze date", width="stretch"):
        freeze_dialog(squadron, ref, grid)
    if cols[2].button("Open next month", width="stretch"):
        month = _next_month(grids)
        try:
            opened = write(squadron, "POST", "/roster/months", {"month": month})
        except RosterError as exc:
            st.error(str(exc))
        else:
            st.session_state["roster_grid"] = month
            title = f"{date.fromisoformat(f'{month}-01'):%B %Y}"
            flash(f"{title} opened with every weekend. "
                   f"It freezes on {fmt_date(opened['freezeAt'])}.")
            st.rerun()
    if cols[3].button("New course", width="stretch"):
        course_dialog(squadron)
    if ref and cols[4].button(f"Remove this {ref['kind']}", width="stretch",
                              disabled=len(grids) <= 1):
        remove_dialog(squadron, ref)


def _open_tapped(squadron: str, grid: dict) -> None:
    """Open the cell tapped on the grid, if any.

    Args:
        squadron (str): Database name of the squadron.
        grid (dict): The grid on show."""
    row, col = st.session_state.pop("roster_open", (None, None))
    # Names, categories and the headcount have nothing to open.
    if not row or col in (None, "name", "cat") or row == "count":
        return
    if row.startswith("note:"):
        note_dialog(squadron, grid, row.removeprefix("note:"), col)
    else:
        answer_dialog(squadron, grid, row, col)


def _tap(squadron: str, grid: dict, day: str) -> None:
    """Save a tap on Your dates; one that needs words opens the dialog instead.

    Args:
        squadron (str): Database name of the squadron.
        grid (dict): The grid on show.
        day (str): ISO date of the row tapped."""
    state = st.session_state
    me = st.session_state["roster_me"]
    entry = (find_row(grid, me["personId"]).get("entries") or {}).get(day)
    status = state.get(f"yd_status_{day}")
    part = state.get(f"yd_part_{day}")
    comment = state.get(f"yd_comment_{day}")
    # Rebuild this row's buttons from the saved answer on the next run.
    for key in ("status", "part", "comment"):
        state.pop(f"yd_{key}_{day}", None)

    # Tapping the answer already picked unpicks it; treat that as no change.
    if not status:
        return
    choice = part if status == "Y" and part in ("AM", "PM") else status
    old = (entry or {}).get("comment") or ""
    # Keep the comment while the status stays the same, else start afresh.
    same = bool(entry) and entry["status"] == status
    text = (old if comment is None else comment) if same else ""
    if choice == choice_of(entry) and text == old:
        return
    if choice == "C" and not text.strip():
        if entry and entry["status"] == "C":
            flash("C needs a comment. Kept the old one.")
            return
        state["roster_dialog"] = (me["personId"], day, choice)
        return
    if not is_admin() and grid["frozen"] and entry and choice != choice_of(entry):
        state["roster_dialog"] = (me["personId"], day, choice)
        return
    try:
        flash(put_answer(squadron, me["personId"], day, choice, text))
    except RosterError as exc:
        flash(str(exc))


def _your_dates(squadron: str, grid: dict) -> None:
    """The signed-in person's own dates, one row each, saving as they tap.

    Args:
        squadron (str): Database name of the squadron.
        grid (dict): The grid on show."""
    me = st.session_state["roster_me"]
    row = find_row(grid, me["personId"])
    entries = row.get("entries") or {}
    pending = row.get("pending") or {}
    days = grid.get("days") or {}
    answered = sum(day in entries for day in grid["dates"])
    st.markdown(f"**{answered} of {len(grid['dates'])}** answered")

    for day in grid["dates"]:
        entry, pend = entries.get(day), pending.get(day)
        status = entry["status"] if entry else None
        with st.container(border=True):
            event = (days.get(day) or {}).get("event")
            line = f"**{day_mon(day)}**"
            line += f" · {event}" if event else ""
            line += " · :orange[🔒 Frozen]" if grid["frozen"] else ""
            st.markdown(line)
            args = (squadron, grid, day)
            st.segmented_control(
                f"Answer for {long(day)}", ["Y", "N", "TBC", "C"], default=status,
                key=f"yd_status_{day}", label_visibility="collapsed",
                on_change=_tap, args=args,
            )
            if status == "Y":
                st.segmented_control(
                    "Coming for", ["All day", "AM", "PM"],
                    default=(entry or {}).get("part") or "All day",
                    key=f"yd_part_{day}", on_change=_tap, args=args,
                )
            if status in ("N", "TBC", "C"):
                st.text_input(
                    "Which course?" if status == "C" else "Comment (optional)",
                    value=(entry or {}).get("comment") or "", max_chars=200,
                    key=f"yd_comment_{day}", on_change=_tap, args=args,
                )
            elif entry and entry.get("comment"):
                st.caption(f'"{entry["comment"]}"')
            if pend:
                st.markdown(f":orange[Waiting for approval: "
                            f"{describe(pend['toStatus'], pend.get('toPart'))}, "
                            f'"{pend["reason"]}".]')

    if opened := st.session_state.pop("roster_dialog", None):
        person_id, day, choice = opened
        answer_dialog(squadron, grid, person_id, day, choice)


def _decide(squadron: str, change: dict, approve: bool) -> None:
    """Approve or reject a change; a callback, so the panel redraws after."""
    first = change["name"].split()[0]
    if approve:
        path, body = f"/roster/changes/{change['changeId']}/approve", None
        done = f"Approved. {change['name']} is emailed."
    else:
        reason = (st.session_state.get(f"reject_{change['changeId']}") or "").strip()
        if not reason:
            flash("Give a reason. It is emailed to them.")
            return
        path, body = f"/roster/changes/{change['changeId']}/reject", {"comment": reason}
        done = f"Rejected. {first} is emailed your reason."
    try:
        write(squadron, "POST", path, body)
    except RosterError as exc:
        done = str(exc)
    flash(done)


def _changes_panel(squadron: str) -> None:
    """Changes waiting for an admin, for everyone to see."""
    # Optional; a backend without change requests shows no panel.
    try:
        changes = read(squadron, "/roster/changes?state=pending")["changes"]
    except RosterError:
        logger.info("No changes from the roster API.", exc_info=True)
        return
    if not changes:
        return

    st.subheader(f"Changes waiting ({len(changes)})")
    for change in sorted(changes, key=lambda c: c["updatedAt"]):
        with st.container(border=True):
            st.markdown(
                f"**{change['name']}**, {day_mon(change['date'])}: "
                f"{describe(change.get('fromStatus'), change.get('fromPart'))} to "
                f"{describe(change['toStatus'], change.get('toPart'))}."
            )
            st.caption(f'"{change["reason"]}". Asked {when(change["updatedAt"])}.')
            if not is_admin():
                continue
            approve, reject = st.columns([1, 4])
            approve.button("Approve", key=f"approve_{change['changeId']}",
                           type="primary", on_click=_decide,
                           args=(squadron, change, True))
            with reject.popover("Reject"):
                st.text_input("Reason for rejecting", max_chars=200,
                              key=f"reject_{change['changeId']}",
                              placeholder=f"Reason for {change['name'].split()[0]}")
                st.button("Reject", key=f"confirm_reject_{change['changeId']}",
                          on_click=_decide, args=(squadron, change, False))


def roster_page(squadron: str, cookie_manager) -> None:
    """Display squadron availability, and let people sign in to edit it.

    Args:
        squadron (str): Database name of the squadron.
        cookie_manager: The dashboard's cookie manager component."""
    st.header("Roster")
    if flash := st.session_state.pop("roster_flash", None):
        st.toast(flash)

    # main.py logs the user out on an uncaught error, so nothing escapes here.
    try:
        restore(squadron, cookie_manager)
        sync_cookie(cookie_manager)
        sign_in_bar(squadron)
        grids, start = _load_grids(squadron)
        ref = _grid_picker(grids, start) if grids else None
        grid = read(squadron, f"{grid_path(ref)}/grid") if ref else None
    except Exception:  # pylint: disable=broad-except
        logger.error("Failed to load the roster.", exc_info=True)
        st.error("Could not load the roster. Try again shortly.")
        return

    layout = st.session_state.get("roster_layout") or GRID
    if is_admin() and layout == GRID:
        _admin_tools(squadron, ref, grid, grids)
    if ref is None or grid is None:
        st.info("No months have been set up yet.")
        return

    if grid["frozen"]:
        st.caption(f"🔒 Frozen since {fmt_date(grid['freezeAt'])}. "
                   "Changing an answer needs an admin.")
    else:
        st.caption(f"Freezes on {fmt_date(grid['freezeAt'])}. "
                   "Until then, changes land straight away.")

    if signed_in() and layout == YOUR_DATES:
        _your_dates(squadron, grid)
    else:
        show_key()
        draw_grid(ref, grid)
        _open_tapped(squadron, grid)
    _changes_panel(squadron)
