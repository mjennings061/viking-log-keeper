"""roster_dialogs.py - The pop-ups for answers, notes and grid admin."""

from datetime import timedelta

import streamlit as st

from dashboard.roster_api import RosterError
from dashboard.roster_grid import (
    CHOICES,
    NOTE_ROWS,
    choice_of,
    day_mon,
    describe,
    fmt_date,
    grid_path,
    long,
    parse_day,
    plain,
    split_choice,
    when,
)
from dashboard.roster_signin import can_edit, flash, is_admin, signed_in, write

# A course longer than this is probably a mistyped date.
MAX_COURSE_DAYS = 31
# -- Dialogs ------------------------------------------------------------------


def find_row(grid: dict, person_id: str) -> dict:
    """One person's row of the grid, or an empty one."""
    return next((r for r in grid["rows"] if r["personId"] == person_id),
                {"personId": person_id, "name": "", "entries": {}, "pending": {}})


@st.dialog("Availability")
def answer_dialog(squadron: str, grid: dict, person_id: str, day: str,
                   preset: str | None = None) -> None:
    """Show one cell's answer, and let whoever may change it do so.

    Args:
        squadron (str): Database name of the squadron.
        grid (dict): The grid the cell is on.
        person_id (str): Whose row.
        day (str): ISO date of the column.
        preset (str | None): A CHOICES button to start on, from Your dates."""
    row = find_row(grid, person_id)
    entry = (row.get("entries") or {}).get(day)
    pend = (row.get("pending") or {}).get(day)

    st.caption(long(day))
    st.subheader(row["name"])
    if entry:
        comment = f', "{plain(entry["comment"])}"' if entry.get("comment") else ""
        st.write(f"{describe(entry['status'], entry.get('part'))}{comment}. "
                 f"Set by {entry['updatedByName']}, {when(entry['updatedAt'])}.")
    else:
        st.write("Not answered yet.")
    if pend:
        st.markdown(f":orange[Waiting for approval: "
                    f"{describe(pend['toStatus'], pend.get('toPart'))}, "
                    f'"{plain(pend["reason"])}".]')

    if not can_edit(person_id):
        if not signed_in():
            st.info("To change answers, press Update my roster.")
        return

    # Keyed per cell, so a dialog closed unsaved cannot carry over to the next one.
    cell = f"{person_id}_{day}_{preset}"
    choice = st.segmented_control("Answer", CHOICES, key=f"answer_{cell}",
                                  default=preset or choice_of(entry))
    # A member changing a frozen answer asks; a comment-only edit just saves.
    asking = (not is_admin() and grid["frozen"] and entry is not None
              and choice != choice_of(entry))
    if asking:
        label = "Reason for the change (required)"
    elif choice == "C":
        label = "Which course? (required)"
    else:
        label = "Comment (optional)"
    start = "" if asking else (entry or {}).get("comment") or ""
    comment = st.text_input(label, value=start, max_chars=200, key=f"comment_{cell}")

    if asking:
        st.caption("This date has frozen. Your change goes to an admin, and your "
                   "answer stays as it is until they approve it.")
    if is_admin() and pend:
        st.caption("Saving closes the waiting change as superseded and emails them.")
    if is_admin() and person_id != st.session_state["roster_me"]["personId"]:
        st.caption(f"You are setting {row['name'].split()[0]}'s answer. "
                   "It is recorded under your name.")

    if st.button("Send for approval" if asking else "Save", type="primary"):
        if not choice:
            st.error("Pick an answer.")
        elif asking and not comment.strip():
            st.error("Give a reason. An admin reads it before approving.")
        elif choice == "C" and not comment.strip():
            st.error("Say which course. C needs a comment.")
        else:
            try:
                flash(put_answer(squadron, person_id, day, choice, comment))
            except RosterError as exc:
                st.error(str(exc))
            else:
                st.rerun()


@st.dialog("Note")
def note_dialog(squadron: str, grid: dict, key: str, day: str) -> None:
    """Show one note box; admins can change it.

    Args:
        squadron (str): Database name of the squadron.
        grid (dict): The grid the note is on.
        key (str): Which box, a key of NOTE_ROWS.
        day (str): ISO date of the column."""
    note = (grid.get("days") or {}).get(day) or {}
    text = note.get(key) or ""
    st.caption(long(day))
    st.subheader(NOTE_ROWS[key])
    st.caption(f"Updated by {note.get('updatedByName')}, "
               f"{when(note.get('updatedAt'))}." if text else "Empty.")
    if not is_admin():
        st.write(text or "Nothing here yet.")
        return
    # Keyed per box and date, so unsaved text cannot carry over to another note.
    value = st.text_area("Shown above the names for this date. Leave empty to clear.",
                         value=text, max_chars=200, key=f"note_{key}_{day}")
    if st.button("Save", type="primary"):
        save(squadron, "PATCH", f"/roster/days/{day}", {key: value.strip()}, "Saved")


@st.dialog("Flying dates")
def dates_dialog(squadron: str, ref: dict, grid: dict) -> None:
    """Add or remove a grid's dates; answers on a removed date are kept."""
    st.caption("Removing a date hides it from the grid. Answers and notes stay, so "
               "adding it back brings them back.")
    keep = st.multiselect("Dates", grid["dates"], default=grid["dates"],
                          format_func=day_mon)
    # Keyed per grid, so a date picked but not saved stays with its own grid.
    added = st.date_input("Add a date", value=None, format="DD/MM/YYYY",
                          key=f"add_date_{ref['id']}")
    if st.button("Save", type="primary"):
        add = [added.isoformat()] if added else []
        remove = [d for d in grid["dates"] if d not in keep]
        save(squadron, "PATCH", f"{grid_path(ref)}/dates",
              {"add": add, "remove": remove}, "Dates saved")


@st.dialog("Move the freeze date")
def freeze_dialog(squadron: str, ref: dict, grid: dict) -> None:
    """Move when a grid freezes."""
    st.caption("Normally two weeks before it starts. After it, members need an "
               "admin to change an answer.")
    freeze = st.date_input("Freezes on", value=parse_day(grid["freezeAt"]),
                           format="DD/MM/YYYY")
    if st.button("Save", type="primary"):
        save(squadron, "PATCH", f"{grid_path(ref)}/freeze",
              {"freezeAt": freeze.isoformat()}, "Freeze date moved")


@st.dialog("New course")
def course_dialog(squadron: str) -> None:
    """Create a course with every day from first to last."""
    st.caption("Every day from the first to the last goes on the grid. Remove any "
               "you do not fly afterwards with Edit dates.")
    title = st.text_input("Title", max_chars=60, placeholder="Easter Course")
    first_col, last_col = st.columns(2)
    first = first_col.date_input("First day", value=None, format="DD/MM/YYYY")
    last = last_col.date_input("Last day", value=None, format="DD/MM/YYYY")
    if not st.button("Create course", type="primary"):
        return
    if not title.strip():
        st.error("Give the course a title.")
    elif not first or not last:
        st.error("Pick the first and last day.")
    elif last < first:
        st.error("The last day is before the first.")
    elif (last - first).days >= MAX_COURSE_DAYS:
        st.error("That is over a month. Check the dates.")
    else:
        span = range((last - first).days + 1)
        days = [(first + timedelta(n)).isoformat() for n in span]
        try:
            course = write(squadron, "POST", "/roster/courses",
                            {"title": title.strip(), "dates": days})
        except RosterError as exc:
            st.error(str(exc))
            return
        st.session_state["roster_grid"] = course["courseId"]
        freeze = fmt_date(course["freezeAt"])
        flash(f"{title.strip()} created. It freezes on {freeze}.")
        st.rerun()


@st.dialog("Remove")
def remove_dialog(squadron: str, ref: dict) -> None:
    """Confirm, then remove a month or course; answers and notes stay."""
    again = ("opening the month again" if ref["kind"] == "month"
             else "creating the course again with the same dates")
    st.subheader(f"Remove {ref['title']}?")
    st.caption(f"The grid goes. Answers and notes stay, so {again} brings them back.")
    if st.button(f"Remove {ref['title']}", type="primary"):
        st.session_state.pop("roster_grid", None)
        save(squadron, "DELETE", grid_path(ref), None, f"{ref['title']} removed")


def save(squadron: str, method: str, path: str, body: dict | None, done: str) -> None:
    """Write, then close any dialog and toast; on failure show why, stay open.

    Args:
        squadron (str): Database name of the squadron.
        method (str): HTTP method.
        path (str): API path.
        body (dict | None): JSON body.
        done (str): Toast on success."""
    try:
        write(squadron, method, path, body)
    except RosterError as exc:
        st.error(str(exc))
        return
    flash(done)
    # st.rerun() never returns; it closes the dialog.
    st.rerun()


def put_answer(squadron: str, person_id: str, day: str, choice: str, comment: str):
    """Send one answer; the API decides if it lands or waits for approval.

    Returns:
        str: The toast to show.

    Raises:
        RosterError: The API refused or could not be reached."""
    status, part = split_choice(choice)
    body = {"status": status, "part": part, "comment": comment.strip() or None}
    result = write(squadron, "PUT", f"/roster/people/{person_id}/days/{day}", body)
    if result.get("applied", True):
        return "Saved"
    return "Sent for approval. The grid shows it as waiting."
