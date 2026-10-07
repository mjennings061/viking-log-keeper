"""test_roster.py - Behaviour of the roster grid and its API errors."""

from datetime import date

from dashboard.roster_grid import BLANK, grid_rows, order_grids
from dashboard.roster_api import error_message

# Who set an answer, as every entry carries it.
BY = {"updatedBy": "1", "updatedByName": "Joe Bloggs",
      "updatedAt": "2026-09-01T10:00:00Z"}

# A month as API 1.1 returns it: a full day, a half day, a leaver and a blank.
GRID = {
    "month": "2026-11",
    "dates": ["2026-11-07", "2026-11-08"],
    "freezeAt": "2026-10-18",
    "frozen": True,
    "days": {"2026-11-07": {"event": "QVS", "updatedByName": "Sam Reid",
                            "updatedAt": "2026-10-02T19:00:00Z"}},
    "rows": [
        {
            "personId": "1",
            "name": "Joe Bloggs",
            "instructCat": "G1",
            "entries": {
                "2026-11-07": {"status": "Y", "comment": "Late in", **BY},
                "2026-11-08": {"status": "Y", "part": "PM", **BY},
            },
            "pending": {"2026-11-08": {"changeId": "c-1", "toStatus": "N",
                                       "toPart": None, "reason": "Work"}},
        },
        {"personId": "2", "name": "Ann Smith", "instructCat": None,
         "entries": {"2026-11-07": {"status": "C", "comment": "SYE", **BY}}},
        {"personId": "3", "name": "Chris Doyle", "isActive": False,
         "entries": {}, "pending": {}},
    ],
}


def _by_name(rows: list[dict]) -> dict:
    """Index the grid's rows by the name drawn down the side."""
    return {row["name"]: row for row in rows}


def test_coming_counts_every_y_including_half_days():
    """The headcount is what the exec plans the day around."""
    _, _, (coming,) = grid_rows(GRID)
    assert coming["name"] == "Coming"
    # Joe's Y counts on the 7th; Ann's course does not.
    assert coming["2026-11-07"] == "1"
    # Joe's afternoon is still a Y.
    assert coming["2026-11-08"] == "1"


def test_cells_show_the_answer_and_mark_comments_and_waiting_changes():
    """Half days read AM or PM, blanks a dash, and a waiting change is marked."""
    rows = _by_name(grid_rows(GRID)[0])
    joe, ann = rows["Joe Bloggs"], rows["Ann Smith"]

    assert joe["2026-11-07"] == "Y"
    assert "has-comment" in joe["2026-11-07|cls"]
    assert "Late in" in joe["2026-11-07|tip"]

    # The cell keeps today's answer and flags the one asked for.
    assert joe["2026-11-08"] == "PM"
    assert "has-pending to-N" in joe["2026-11-08|cls"]
    assert "Waiting for approval: N" in joe["2026-11-08|tip"]

    assert ann["2026-11-07|cls"].split()[:2] == ["ans", "s-c"]
    assert ann["2026-11-08"] == BLANK


def test_note_rows_sit_on_top_and_leavers_are_tagged():
    """The three note boxes head the grid, and a leaver still draws, tagged."""
    rows, top, _ = grid_rows(GRID)
    assert [r["name"] for r in top] == [
        "Visiting / event", "Accommodation in use", "GS"]
    assert top[0]["2026-11-07"] == "QVS"
    assert _by_name(rows)["Chris Doyle"]["name|cls"] == "left"


def test_grid_without_newer_fields_still_draws():
    """A backend without note rows or change requests still gives a grid."""
    old = {**GRID, "rows": [{"personId": "1", "name": "Joe Bloggs",
                             "entries": {}}]}
    del old["days"]
    rows, top, _ = grid_rows(old)
    assert rows[0]["2026-11-07"] == BLANK
    assert top[0]["2026-11-07"] == ""


def test_grids_run_in_date_order_and_open_on_the_current_one():
    """A course across a month end sits between months, and old ones stay."""
    course = {"courseId": "k1", "title": "Summer Course 1",
              "firstDate": "2026-07-27", "lastDate": "2026-08-05"}
    grids, start = order_grids(["2026-08", "2026-06", "2026-07"], [course],
                               today=date(2026, 7, 30))
    assert [g["title"] for g in grids] == [
        "June 2026", "July 2026", "Summer Course 1", "August 2026"]
    # July is still running on the 30th, so the page opens there.
    assert grids[start]["title"] == "July 2026"


def test_api_errors_read_as_plain_words():
    """A missing backend route or a validation list never reaches the page raw."""
    assert error_message("Not Found", 404) == "Not available yet."
    assert error_message("Method Not Allowed", 405) == "Not available yet."
    assert error_message("No such month", 404) == "No such month"
    assert error_message([{"msg": "C needs a comment"}], 422) == "C needs a comment"
