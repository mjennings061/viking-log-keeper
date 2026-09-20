"""test_roster.py - Tests for the roster availability grid."""

from dashboard.roster import BLANK, grid_to_frame

# A month as the API returns it: one person part-answered, one not at all.
GRID = {
    "month": "2026-11",
    "dates": ["2026-11-07", "2026-11-08"],
    "freezeAt": "2026-10-18",
    "frozen": False,
    "rows": [
        {
            "personId": "1",
            "name": "Joe Bloggs",
            "instructCat": "G1",
            "entries": {
                "2026-11-07": {
                    "status": "Y",
                    "comment": None,
                    "updatedBy": "1",
                    "updatedByName": "Joe Bloggs",
                    "updatedAt": "2026-09-01T10:00:00Z",
                },
            },
            "pending": {},
        },
        {
            "personId": "2",
            "name": "Ann Smith",
            "instructCat": None,
            "entries": {},
            "pending": {},
        },
    ],
}


def _row(frame, name: str) -> dict:
    """Get one person's row as a plain dictionary.

    Args:
        frame: The grid as grid_to_frame built it.
        name (str): Whose row to read.

    Returns:
        dict: That person's Cat and every date, keyed by heading."""
    return frame.set_index("Name").loc[name].to_dict()


def test_names_down_the_side_dates_across_the_top():
    """The grid is laid out the way the page draws it."""
    frame = grid_to_frame(GRID)
    assert list(frame["Name"]) == ["Joe Bloggs", "Ann Smith"]
    assert list(frame.columns) == ["Name", "Cat", "Sat 07", "Sun 08"]

    joe = _row(frame, "Joe Bloggs")
    assert joe["Sat 07"] == "Y"
    assert joe["Cat"] == "G1"


def test_unanswered_dates_are_blank_not_missing():
    """A date nobody answered still gets a column, or the month looks shorter."""
    assert _row(grid_to_frame(GRID), "Joe Bloggs")["Sun 08"] == BLANK


def test_someone_who_has_answered_nothing_still_has_a_row():
    """A blank row draws, or the squadron looks smaller than it is."""
    ann = _row(grid_to_frame(GRID), "Ann Smith")
    assert ann["Sat 07"] == ann["Sun 08"] == BLANK
    assert ann["Cat"] == ""
