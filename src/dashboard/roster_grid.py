"""roster_grid.py - The squadron grid: its rows, colours and drawing."""

import hashlib
import json
from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode

# Drawn where nobody has answered.
BLANK = "-"
# What a cell can be set to; AM and PM are a Y for half the day.
CHOICES = ["Y", "AM", "PM", "N", "TBC", "C"]
# The three note boxes above the names, in the spreadsheet's order.
NOTE_ROWS = {
    "event": "Visiting / event",
    "accommodation": "Accommodation",
    "gs": "GS Attending",
}
# Times on the page are UK time; the API sends UTC.
UK = ZoneInfo("Europe/London")

# Prototype colours, all checked against WCAG 2.2 AA; keyed by light or dark.
PALETTE = {
    "light": {
        "y": ("#d2eeda", "#135a2a"),
        "n": ("#f6d5d9", "#8b1c27"),
        "tbc": ("#f8eabd", "#684a00"),
        "c": ("#d1e2fa", "#164a8b"),
        "pend": "#a04a06",
        "muted": "#586775",
    },
    "dark": {
        "y": ("#163a22", "#a3e3b5"),
        "n": ("#471b21", "#f5aab2"),
        "tbc": ("#463710", "#f3d57e"),
        "c": ("#15325a", "#a2c7f6"),
        "pend": "#f2a65e",
        "muted": "#94a2ae",
    },
}

# Row heights; notes get two lines, and the grid's height is worked out from them.
HEADER_PX, NOTE_PX, ROW_PX = 40, 44, 32
# Room for the sideways scrollbar when a long course overflows.
SCROLL_PX = 18
ROW_HEIGHT = JsCode(
    f"function(p) {{ return p.data.id.startsWith('note:') ? {NOTE_PX} : {ROW_PX}; }}"
)
# Python works out each cell's classes, so the grid only has to look them up.
CELL_CLASS = JsCode("function(p) { return p.data[p.colDef.field + '|cls']; }")
# Sends the clicked row and column back; the time makes a repeat click new.
CLICK = JsCode(
    "function({eventData}) {"
    " return {row: eventData.data.id, col: eventData.colDef.field, at: Date.now()};"
    " }"
)

# -- Formatting ---------------------------------------------------------------


def parse_day(day: str) -> date:
    """Parse an ISO date from the API.

    Args:
        day (str): e.g. '2026-11-07'.

    Returns:
        date: The date."""
    return date.fromisoformat(day)


def short(day: str) -> str:
    """'Sat 7', for a month's column headings."""
    d = parse_day(day)
    return f"{d:%a} {d.day}"


def day_mon(day: str) -> str:
    """'Sat 7 Nov', where a grid crosses a month end."""
    d = parse_day(day)
    return f"{d:%a} {d.day} {d:%b}"


def long(day: str) -> str:
    """'Saturday 7 November 2026', for dialogs and header tooltips."""
    d = parse_day(day)
    return f"{d:%A} {d.day} {d:%B %Y}"


def fmt_date(day: str) -> str:
    """'7 Nov 2026', for freeze dates."""
    d = parse_day(day)
    return f"{d.day} {d:%b %Y}"


def when(stamp: str | None) -> str:
    """'14 Sep, 19:02' in UK time, from the API's UTC timestamp."""
    if not stamp:
        return ""
    t = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UK)
    return f"{t.day} {t:%b, %H:%M}"


def describe(status: str | None, part: str | None = None) -> str:
    """An answer in words: 'Y, AM only', 'N', or 'blank'."""
    if not status:
        return "blank"
    return f"Y, {part} only" if part else status


def plain(text: str) -> str:
    """A member's words, safe to show on the page as Markdown."""
    # Escaping [ stops links and outside images from rendering.
    return text.replace("[", r"\[")


def choice_of(entry: dict | None) -> str | None:
    """The CHOICES button an answer matches; AM and PM win over Y."""
    if not entry:
        return None
    return entry.get("part") or entry["status"]


def split_choice(choice: str) -> tuple[str, str | None]:
    """Turn a CHOICES button back into the API's status and part."""
    return ("Y", choice) if choice in ("AM", "PM") else (choice, None)


# -- Grids --------------------------------------------------------------------


def order_grids(months: list[str], courses: list[dict], today: date):
    """Put months and courses in date order and pick the one to open on.

    Args:
        months (list[str]): Months as '2026-11', any order.
        courses (list[dict]): Courses as GET /roster/courses lists them.
        today (date): Today, to open on the first grid not yet over.

    Returns:
        tuple[list[dict], int]: The grids, and the index to open on."""
    grids = []
    for month in months:
        first = date.fromisoformat(f"{month}-01")
        last = first.replace(day=monthrange(first.year, first.month)[1])
        title = f"{first:%B %Y}"
        grids.append({"kind": "month", "id": month, "title": title,
                      "first": first, "last": last})
    for course in courses:
        grids.append({
            "kind": "course",
            "id": course["courseId"],
            "title": course["title"],
            "first": parse_day(course["firstDate"]),
            "last": parse_day(course["lastDate"]),
        })
    grids.sort(key=lambda g: g["first"])

    # Past grids stay readable, but the page opens on what is coming up.
    current = [i for i, g in enumerate(grids) if g["last"] >= today]
    return grids, current[0] if current else max(len(grids) - 1, 0)


def grid_path(ref: dict) -> str:
    """API path of a month or course."""
    return f"/roster/{ref['kind']}s/{ref['id']}"


def _answer_tip(entry: dict | None, pend: dict | None) -> str:
    """Hover text for an answer cell: the answer, comment, who and when."""
    if not entry:
        lines = ["Not answered"]
    else:
        lines = [describe(entry["status"], entry.get("part"))]
        if entry.get("comment"):
            lines.append(f'"{entry["comment"]}"')
        lines.append(f"Set by {entry['updatedByName']}, {when(entry['updatedAt'])}")
    if pend:
        lines += [
            "",
            f"Waiting for approval: {describe(pend['toStatus'], pend.get('toPart'))}",
            f'"{pend["reason"]}"',
        ]
    return "\n".join(lines)


def grid_rows(grid: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Build the grid's rows, with each cell's text, classes and hover text.

    Args:
        grid (dict): The API's month or course grid.

    Returns:
        tuple: Person rows, the three note rows on top, the headcount below."""
    dates = grid["dates"]
    # A 1.0 API sends no `days`, so the note rows stay empty.
    days = grid.get("days") or {}

    top = []
    for key, label in NOTE_ROWS.items():
        row = {"id": f"note:{key}", "name": label, "name|cls": "note-label", "cat": ""}
        for day in dates:
            note = days.get(day) or {}
            # AgGrid runs ::JSCODE:: text outside rowData as code, so strip it.
            text = (note.get(key) or "").replace("::JSCODE::", "")
            row[day] = text
            row[f"{day}|cls"] = "note-cell"
            row[f"{day}|tip"] = (
                f"{text}\nUpdated by {note.get('updatedByName')}, "
                f"{when(note.get('updatedAt'))}" if text else ""
            )
        top.append(row)

    rows = []
    coming = dict.fromkeys(dates, 0)
    for person in grid["rows"]:
        entries = person.get("entries") or {}
        pending = person.get("pending") or {}
        left = person.get("isActive") is False
        row = {
            "id": person["personId"],
            "name": person["name"],
            "name|cls": "left" if left else "",
            "cat": person.get("instructCat") or "",
        }
        for day in dates:
            entry, pend = entries.get(day), pending.get(day)
            classes = ["ans", f"s-{entry['status'].lower()}" if entry else "s-blank"]
            if entry and entry.get("comment"):
                classes.append("has-comment")
            if pend:
                # The badge shows the answer asked for, beside the current one.
                asked = pend.get("toPart") or pend["toStatus"]
                classes += ["has-pending", f"to-{asked}"]
            # A half day is still a Y, so it counts.
            if entry and entry["status"] == "Y":
                coming[day] += 1
            row[day] = choice_of(entry) or BLANK
            row[f"{day}|cls"] = " ".join(classes)
            row[f"{day}|tip"] = _answer_tip(entry, pend)
        rows.append(row)

    bottom = {"id": "count", "name": "Coming", "name|cls": "count-label", "cat": ""}
    for day in dates:
        bottom[day] = str(coming[day])
        bottom[f"{day}|cls"] = "count-cell"
        bottom[f"{day}|tip"] = "Ys for this date, half days included"
    return rows, top, [bottom]


def _css(theme: str) -> dict:
    """Cell styles for the grid, in the prototype's colours.

    Args:
        theme (str): 'light' or 'dark', as Streamlit is drawing.

    Returns:
        dict: CSS rules keyed by selector, as streamlit-aggrid takes them."""
    p = PALETTE[theme]
    centred = {"text-align": "center", "justify-content": "center"}
    css = {
        # Tighter side padding lets a month of dates fit without scrolling.
        ".ag-root-wrapper": {"--ag-cell-horizontal-padding": "6px"},
        ".ag-cell.ans":{**centred, "font-weight": "600"},
        ".ag-cell.s-blank": {"color": p["muted"], "font-weight": "500"},
        # Two lines of note at most; hovering shows the rest.
        ".ag-cell.note-cell": {
            "display": "-webkit-box !important",
            "-webkit-line-clamp": "2",
            "-webkit-box-orient": "vertical",
            "overflow": "hidden",
            "text-align": "center",
            "font-size": "12px",
            "line-height": "1.3",
            "padding-top": "6px",
            "max-height": "calc(2.6em + 6px)",
        },
        ".ag-cell.note-label": {"font-size": "12px", "font-weight": "600"},
        ".ag-cell.count-cell, .ag-cell.count-label": {"font-weight": "600"},
        ".ag-cell.count-cell": centred,
        # A small corner triangle marks a comment.
        ".ag-cell.has-comment::before": {
            "content": '""',
            "position": "absolute",
            "top": "0",
            "right": "0",
            "border-style": "solid",
            "border-width": "0 7px 7px 0",
            "border-color": f"transparent {p['muted']} transparent transparent",
        },
        ".ag-cell.has-pending": {
            "outline": f"2px dashed {p['pend']}",
            "outline-offset": "-3px",
        },
        ".ag-cell.has-pending::after": {
            "font-size": "12px",
            "color": p["pend"],
            "vertical-align": "super",
            "margin-left": "3px",
        },
        ".ag-cell.left::after": {
            "content": '"left"',
            "font-size": "12px",
            "color": p["muted"],
            "border": f"1px solid {p['muted']}",
            "border-radius": "3px",
            "padding": "0 4px",
            "margin-left": "6px",
        },
        ".ag-tooltip": {"white-space": "pre-line", "max-width": "280px"},
    }
    for status in ("y", "n", "tbc", "c"):
        bg, ink = p[status]
        css[f".ag-cell.s-{status}"] = {"background-color": bg, "color": ink}
    # The badge's text is the answer asked for.
    for choice in CHOICES:
        css[f".ag-cell.to-{choice}::after"] = {"content": f'"{choice}"'}
    return css


def show_key() -> None:
    """What the colours and marks on the grid mean."""
    st.caption(
        ":green-badge[Y] Coming · :green-badge[AM] :green-badge[PM] Half day · "
        ":red-badge[N] Not coming · :orange-badge[TBC] Not sure yet · "
        ":blue-badge[C] On a course · :gray-badge[-] Not answered · "
        "Corner mark: has a comment · Dashed outline: change waiting"
    )


def clicked(response) -> None:
    """Remember which cell was tapped; the page opens it after the grid."""
    st.session_state["roster_open"] = response.get("row"), response.get("col")


def draw_grid(ref: dict, grid: dict) -> None:
    """The squadron grid, laid out like the spreadsheet.

    Args:
        ref (dict): Which grid this is.
        grid (dict): The API's grid body."""
    rows, top, bottom = grid_rows(grid)
    dates = grid["dates"]
    # Day numbers repeat across a month end, so show the month there.
    spans = ref["kind"] == "course" or len({d[:7] for d in dates}) > 1
    columns = [
        {"field": "name", "headerName": "Name", "pinned": "left", "width": 150},
        {"field": "cat", "headerName": "Cat", "pinned": "left", "width": 44,
         "headerTooltip": "Instructor category from STARS"},
    ] + [
        {"field": d, "headerName": day_mon(d) if spans else short(d),
         "headerTooltip": long(d), "tooltipField": f"{d}|tip",
         "flex": 1, "minWidth": 56, "wrapText": True}
        for d in dates
    ]
    options = {
        "columnDefs": columns,
        "defaultColDef": {"sortable": False, "resizable": False,
                          "suppressMovable": True, "suppressHeaderMenuButton": True,
                          "cellClass": CELL_CLASS},
        "pinnedTopRowData": top,
        "pinnedBottomRowData": bottom,
        # Without our ids the library uses its own, which pinned rows lack.
        "getRowId": JsCode("function(p) { return p.data.id; }"),
        "tooltipShowDelay": 250,
        "tooltipHideDelay": 10000,
        "headerHeight": HEADER_PX,
        "getRowHeight": ROW_HEIGHT,
    }
    frame = pd.DataFrame(rows, columns=list(top[0]))
    version = hashlib.md5(json.dumps(grid, sort_keys=True).encode()).hexdigest()
    AgGrid(
        frame,
        gridOptions=options,
        # Fixed rows give an exact height, so every name shows without scrolling.
        height=HEADER_PX + NOTE_PX * len(top) + ROW_PX * (len(rows) + 1) + SCROLL_PX,
        theme="streamlit",
        custom_css=_css(st.context.theme.type or "light"),
        allow_unsafe_jscode=True,
        data_return_mode="CUSTOM",
        custom_jscode_for_grid_return=CLICK,
        update_on=["cellClicked"],
        # New data, new grid; updating in place leaves stale classes and rows.
        key=f"roster_grid_{ref['id']}_{version}",
        callback=clicked,
    )
    st.caption("Hover a cell for its comment and who set it. Tap a cell to open it.")
