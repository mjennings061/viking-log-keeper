# Roster — design note

Draft for review. Nothing built yet.

## What this is

Squadron availability moves off the SharePoint spreadsheet. People say which
days they can make; the exec sees the whole month; every change is attributed
and nothing happens quietly.

Writes, logins and emails go in **vgs-stars**, because it already holds the
STARS client, Resend, Cloud Scheduler and Firestore. The
**viking-log-keeper** dashboard gains one page that reads the month and posts
changes. No new service, no new bill.

## What it is not

Not duty assignment. Not a currency check. Not a replacement for the `661vgs`
dashboard password. Those are separate jobs and at least one of them
(currency) comes from the launch log rather than STARS.

## Identity

Nobody creates an account. STARS is the directory.

Everyone on the squadron sees the same grid: all names, all dates, all pending
changes. That is the point — anyone can answer "where is Joe on Saturday"
without asking the exec. Admin is not a better view, only more buttons.

| Gate | What it proves | When |
|---|---|---|
| `661vgs` password | You are on the squadron, so you may read | Unchanged |
| Six-digit code | You are a named person, so you may write | First edit on a device |

Reading needs no code. Someone checking the grid on a Thursday evening types
nothing. The code is only asked for at the moment of the first change.

| Can | Everyone | Admin |
|---|---|---|
| See the whole grid | Yes | Yes |
| See pending changes and who asked | Yes | Yes |
| Set their own availability | Yes | Yes |
| Approve or reject a change | No | Yes |
| Edit someone else's row | No | Yes |
| Add dates, publish the month | No | Yes |

The code is sent to the email STARS holds and typed into the tab already open.
Not a link — Microsoft Defender pre-fetches links in `mod.gov.uk` mail and
would burn a single-use token before the person clicks it.

Admin is a role on the person record, not a second login. Seeded once by hand.
Sessions last 30 days on a remembered device, so an admin types a code three or
four times a year and otherwise just opens the page and edits.

## Firestore collections

Every document carries `squadronId`, so a second VGS costs nothing later.

### `roster_people`

Cached copy of the STARS unit list. Refreshed nightly. Document ID
`{squadronId}:{personId}`.

```python
class RosterPerson(BaseModel):
    """A person on the squadron roster, sourced from STARS."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    person_id: str = Field(..., alias="personId")
    squadron_id: str = Field(..., alias="squadronId")
    name: str
    known_as: str | None = Field(default=None, alias="knownAs")
    initials: str | None = None
    rank: str | None = None
    instruct_cat: str | None = Field(default=None, alias="instructCat")
    email: str
    role: str = Field(default="member")
    is_active: bool = Field(default=True, alias="isActive")
    synced_at: datetime = Field(default_factory=datetime.now, alias="syncedAt")
```

The nightly sync only writes the STARS-sourced fields. It must never touch
`role`, or a refresh would silently demote your admins.

`is_active` comes from the STARS `endDate`. Leavers drop off the grid but
their history stays.

### `roster_months`

One per month. Document ID `{squadronId}:2027-01`.

```python
class RosterMonth(BaseModel):
    """A month of flying dates that people can respond to."""

    squadron_id: str = Field(..., alias="squadronId")
    month: str
    dates: list[date]
    freeze_at: date = Field(..., alias="freezeAt")
```

`dates` defaults to every Saturday and Sunday and is editable by an admin, so
camps and weekday evenings go on the same grid.

`freeze_at` is two weeks before the month starts. Nobody publishes anything —
the month freezes itself on a date everyone can predict. An admin can move it
if a month needs longer, but the default should almost always stand.

Before the freeze, people change their own dates freely and the change lands
straight away. After it, a change becomes a request and waits for an admin.

One exception: answering a date you had left blank always lands straight away,
even after the freeze. Filling a gap is new information, not a reversal, and
it is the answer the exec wants soonest. The same applies to a date an admin
adds late.

So the month runs to a fixed clock:

| When | What happens |
|---|---|
| 2 months out | Everyone is asked to fill it in |
| 6 weeks out | Anyone with blank dates is chased |
| 2 weeks out | Month freezes, changes need approval |

### `roster_availability`

One document per person per month, holding the whole row.

```python
class AvailabilityEntry(BaseModel):
    """One person's answer for one date."""

    status: str  # Y, N or TBC
    comment: str | None = None
    updated_at: datetime = Field(..., alias="updatedAt")
    updated_by: str = Field(..., alias="updatedBy")


class AvailabilityRow(BaseModel):
    """A person's availability across one month."""

    person_id: str = Field(..., alias="personId")
    squadron_id: str = Field(..., alias="squadronId")
    month: str
    entries: dict[str, AvailabilityEntry]
```

A row rather than a cell per document, because drawing the grid is then 40
reads instead of 400.

There is no submitted flag. Nobody presses submit, so "have they responded" is
just "are any dates still blank" — which also lets the chase email say how many
are left instead of starting from nothing.

`updated_by` is the person who typed it, which is not always the person the row
belongs to. That is how admin edits and phoned-in changes stay visible.

### `roster_changes`

Append-only. Never updated in place, only added to.

```python
class RosterChange(BaseModel):
    """A requested change to a published month."""

    squadron_id: str = Field(..., alias="squadronId")
    month: str
    person_id: str = Field(..., alias="personId")
    change_date: date = Field(..., alias="changeDate")
    from_status: str | None = Field(default=None, alias="fromStatus")
    to_status: str = Field(..., alias="toStatus")
    reason: str | None = None
    state: str = Field(default="pending")
    requested_by: str = Field(..., alias="requestedBy")
    requested_at: datetime = Field(..., alias="requestedAt")
    decided_by: str | None = Field(default=None, alias="decidedBy")
    decided_at: datetime | None = Field(default=None, alias="decidedAt")
    decision_comment: str | None = Field(default=None, alias="decisionComment")
```

Pending changes show on the grid immediately, marked pending. The exec sees
the Friday dropout the moment it is submitted, even if nobody approves it until
Sunday. Approval controls the record, not the visibility.

Approving copies the new status into `roster_availability` and closes the
change. Rejecting leaves the row alone and emails the person the reason.

### `roster_sessions` and `roster_codes`

Document ID is the SHA-256 of the secret, matching how API keys are already
stored. The plain value exists only in the browser and the email.

```python
class RosterSession(BaseModel):
    """A signed-in person on one device."""

    person_id: str = Field(..., alias="personId")
    squadron_id: str = Field(..., alias="squadronId")
    role: str
    expires_at: datetime = Field(..., alias="expiresAt")
    remembered: bool = Field(default=False)


class LoginCode(BaseModel):
    """A six-digit code waiting to be typed in."""

    person_id: str = Field(..., alias="personId")
    nonce_hash: str = Field(..., alias="nonceHash")
    expires_at: datetime = Field(..., alias="expiresAt")
    attempts: int = Field(default=0)
    used_at: datetime | None = Field(default=None, alias="usedAt")
```

The nonce ties the code to the browser that asked for it, so a forwarded email
is useless on its own.

## Endpoints

New router at `/roster`. Two kinds of caller:

- **Reads** use a read-only API key held by the dashboard in its secrets. It
  proves the request came from behind the squadron password, nothing more.
- **Writes** need a roster session, which names the person.

That means adding a `scopes` field to the existing API key record, so a roster
key cannot reach the STARS routes and a STARS key cannot write the roster.

### Signing in

| Method | Path | Who | Does |
|---|---|---|---|
| POST | `/roster/auth/request-code` | Anyone | Emails a code, returns a nonce |
| POST | `/roster/auth/verify-code` | Anyone | Swaps code for a session |
| GET | `/roster/auth/me` | Session | Who am I, what can I do |
| POST | `/roster/auth/logout` | Session | Ends this device |

`request-code` always answers the same way whether or not the person exists.
Otherwise it becomes a way to test who is on the squadron.

### The month

| Method | Path | Who | Does |
|---|---|---|---|
| GET | `/roster/people` | Read key | Names for the picker, no emails |
| GET | `/roster/months/{month}` | Read key | Dates and status |
| POST | `/roster/months/{month}` | Admin | Creates it, weekends by default |
| PATCH | `/roster/months/{month}/dates` | Admin | Adds or removes a date |
| PATCH | `/roster/months/{month}/freeze` | Admin | Moves the freeze date |

### Availability

| Method | Path | Who | Does |
|---|---|---|---|
| GET | `/roster/months/{month}/grid` | Read key | Whole grid, pending marked |
| PUT | `/roster/months/{month}/me/{date}` | Session | Sets one of your own dates |
| PUT | `/roster/months/{month}/{personId}/{date}` | Admin | Sets someone else's |

One date at a time, because the page saves as you tap rather than asking
anyone to press submit. The server merges it into that person's row.

After the freeze, the same call writes a pending change instead of the answer,
unless the date was blank.

An admin setting someone else's row emails that person. Otherwise you have
rebuilt silent changes, only pointing the other way.

### Changes

| Method | Path | Who | Does |
|---|---|---|---|
| GET | `/roster/months/{month}/changes` | Read key | Pending list |
| POST | `/roster/changes/{id}/approve` | Admin | Applies it, emails the person |
| POST | `/roster/changes/{id}/reject` | Admin | Emails the reason |

### Scheduled

Cloud Scheduler, API key as now.

| Path | When | Does |
|---|---|---|
| `/roster/jobs/sync-people` | Nightly | Refreshes the STARS list |
| `/roster/jobs/prompt` | 2 months out | Asks everyone to submit |
| `/roster/jobs/chase` | 6 weeks out | Chases whoever has not |

## The dashboard page

One page. Names down the left, dates across the top, a cell each.

The grid loads for everyone straight away, pending changes marked in the cell
they affect. Clicking a cell you can change asks for a code the first time,
then stops asking for thirty days.

Back and forward arrows move between months, and old months stay readable.
That is how attendance gets tracked without a spreadsheet: last November is
still there, and the launch log already knows who actually turned up.

Nobody should need telling how to use it.

## Hosting

The dashboard stays on Streamlit Community Cloud for now.

Nothing can prove to the API that a caller really is the dashboard. Only Cloud
Run service-to-service tokens would, and running Streamlit there means paying
for an always-on instance because it holds a websocket. Not worth it to
protect a roster the whole squadron can already read.

What makes that acceptable is that the read key can only read. Every write
needs a code sent to a STARS email, so a leaked key changes nothing.

**TODO:** branch protection on `viking-log-keeper`. Community Cloud deploys
from the public repo, so a merged commit runs with the database credentials.

## Security decisions

- Codes are six digits, valid ten minutes, one use, five attempts, three
  requests an hour per person. Hashed at rest.
- Session tokens are 32 random bytes, hashed at rest, 12 hours by default and
  30 days on a remembered device.
- The squadron comes from the session, never from the request body. A browser
  must not be able to name a squadron it is writing to.
- A roster session must not open the STARS routes. That service holds the
  STARS API key and this is a new door on the same building.
- The grid names people, including FSCs under 18. It stays behind the squadron
  password and is never cached to disk on the dashboard.

## Settled

- Reasons on pending changes are visible to everyone. **TODO:** revisit once
  members are submitting their own, in case people stop giving a reason at all
  rather than say it in front of the squadron.
- Some FSCs on the roster are under 18. Emailing them is agreed.
- Cutover is November 2026, admins only to begin with.
- No spreadsheet export. The roster becomes the record, so Firestore needs a
  scheduled export somewhere — losing it loses the attendance history.
- Three admins: the two current spreadsheet owners and the project owner.

## Rollout

**Phase 1, November.** Admins only, entering availability on everyone's behalf
exactly as they do in the spreadsheet now. Needs the grid, the month, admin
edit and the change log. Does not need codes, prompts, pending changes or any
member-facing anything. That is a small build and it proves the data model
before anyone else depends on it.

The on-behalf-of email must be off in this phase, or the first month mails
forty people about changes they did not ask for.

**Phase 2.** Members sign in with a code and set their own rows. Pending
changes and approvals switch on with them, because they have nothing to do
until people can submit.

**Phase 3.** The prompt at two months and the chase at six weeks.

These are operational emails, not notifications. They must not share the
unsubscribe list with the authorisation expiry mail, or someone opting out of
one silently stops being asked for their availability.

## Later

One-click approve from the notification email. Flying currency from the launch
log rather than STARS. Who said they were coming against who actually flew.
Duty assignment. A second squadron.

## Separate problem

`src/dashboard/auth.py` compares the `661vgs` password in plain text against a
value stored in MongoDB. That is worth fixing on its own account, before this
page gives people a reason to look at it.
