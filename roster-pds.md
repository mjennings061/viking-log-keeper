# Roster — product design specification

Version 1.0. Hand this to both repositories. The API contract sits alongside
it in `roster-api-contract.md`.

## Purpose

Squadron availability moves off the SharePoint spreadsheet and MS Forms.
People say which days they can make, everyone can see the whole month, and
every change is attributed to a named person.

Today two people send a form six weeks out, retype the replies into a
spreadsheet only they can edit, and field texts and emails asking for changes.
That is the job being removed.

## Who builds what

**vgs-stars** owns the data, the logins and the emails. It already holds the
STARS client, Resend, Cloud Scheduler and Firestore, so nothing new is needed
to run this.

**viking-log-keeper** owns the screen. One new Streamlit page called Roster.
It reads through the API and writes through the API. It never touches the
roster store directly.

## Users

Nobody creates an account. STARS is the directory of people; Firestore holds
only a role against a STARS person ID.

| Can | Everyone | Admin |
|---|---|---|
| See the whole grid | Yes | Yes |
| See pending changes, who asked and why | Yes | Yes |
| Set their own availability | Yes | Yes |
| Approve or reject a change | No | Yes |
| Set anyone's availability, any time | No | Yes |
| Add or remove dates, move the freeze | No | Yes |

Three admins at launch: the two current spreadsheet owners and the project
owner. Set by hand, not self-service.

Everyone sees everything. That is deliberate — anyone can answer "where is Joe
on Saturday" without asking the exec.

## Two gates

| Gate | Proves | When |
|---|---|---|
| `661vgs` dashboard password | You are on the squadron, so you may read | Unchanged |
| Six-digit code by email | You are a named person, so you may write | First edit on a device |

Reading needs no code. The code appears inline at the first attempt to change
something, then not again for thirty days on that device.

Codes, not links. Microsoft Defender pre-fetches links in `mod.gov.uk` mail and
would burn a single-use token before the person clicks it. A pre-fetcher cannot
type a code into a browser tab.

## The month

A month holds a list of flying dates. It defaults to every Saturday and Sunday
and an admin can add or remove dates, so camps and midweek evenings appear on
the same grid.

A month freezes two weeks before it starts. Nobody publishes anything and no
admin has to remember a step.

| When | What happens |
|---|---|
| 2 months out | Everyone is emailed and asked to fill it in |
| 6 weeks out | Anyone with blank dates is chased |
| 2 weeks out | Month freezes |

## Rules

These are the rules a build can get wrong. They are numbered so they can be
tested one by one.

1. Before the freeze, a member changing their own date takes effect
   immediately. No approval, no notification.
2. After the freeze, a member changing a date that already has an answer
   creates a pending change. The stored answer does not move until an admin
   approves it.
3. After the freeze, a member answering a date they had left blank takes
   effect immediately. Filling a gap is new information, not a reversal, and
   the exec wants it straight away.
4. Rule 3 also covers a date an admin adds after the freeze. Nobody has
   answered it yet, so the first answer lands.
5. An admin can set any person's date at any time, before or after the
   freeze, without approval.
6. An admin setting someone else's date emails that person. Otherwise silent
   changes come back, pointing the other way.
7. An admin setting a date that has a pending change closes that change as
   superseded and emails the person who asked.
8. Approving a change writes the new answer and emails the person.
   Rejecting leaves the answer alone and emails them the admin's reason.
9. Every write is recorded with who typed it and when, including admin
   writes on someone else's behalf.
10. Nothing is ever deleted. Changes are appended.

## Screens

One page, two layouts over the same data. Which one a person sees is their
choice, defaulting to their own list on a narrow screen and the grid on a wide
one.

### Your dates

The list most people will use, on a phone.

- Month name with back and forward arrows.
- A count: "2 of 6 answered".
- One row per date: the date, then Y / N / TBC as three buttons.
- Picking N or TBC reveals an optional comment box.
- No submit button. Each tap saves.
- On the first tap of a session, an inline strip appears: "Code sent to
  m•••@rafac.mod.gov.uk" with a six-digit box. It disappears once verified.
- After the freeze, a row that already has an answer asks for a reason and
  says the change needs approving.

### Squadron grid

Names down the left, dates across the top, one cell each. This is the read
view and the admin working view.

- Cell shows Y, N or TBC, tinted, or a dash if blank.
- A cell with a pending change carries a marker and the pending value.
- Hovering or tapping a cell shows the comment, who set it and when.
- Instructor category shows next to each name, blank where STARS has none.
- Frozen months show a lock and the date they froze.
- Admins get a panel of changes waiting, each with the person, the date, the
  old and new value, the reason, and approve and reject.

### Moving between months

Back and forward arrows. Past months stay readable, which is how attendance
gets tracked now there is no spreadsheet.

## Phases

**Phase 1 — November 2026.** Admins only, entering availability on everyone's
behalf exactly as they do in the spreadsheet now.

Needs: the grid, month creation and dates, admin write, the change log, and
admin login by code.

Does not need: member self-service, prompt or chase emails, pending changes,
or the on-behalf-of notification. Rule 6 is switched off in this phase, or the
first month emails forty people about changes they never asked for.

**Phase 2.** Members sign in and set their own rows. Pending changes and
approvals switch on with them, because nothing can be pending until people can
submit.

**Phase 3.** The prompt at two months and the chase at six weeks.

## Non-functional

**Hosting.** The dashboard stays on Streamlit Community Cloud. Nothing can
prove to the API that a caller really is the dashboard — only Cloud Run
service-to-service tokens would, and running Streamlit there means paying for
an always-on instance, which is ruled out. What makes that acceptable is that
the read key can only read. Every write needs a code sent to a STARS address,
so a leaked read key changes nothing.

**Cost.** Cloud Run stays scale-to-zero. First load on a quiet evening will be
slow while the service wakes. Cache the grid read on the dashboard so browsing
months does not wake it repeatedly.

**Sessions.** `extra-streamlit-components` and `cryptography` are already
dependencies, and `src/dashboard/session.py` already encrypts a cookie
(Fernet) with `COOKIE_SECRET`. The roster session token uses the same
mechanism under its own cookie name. Do not add a second cookie library.
Note the existing `CookieManager.delete()` does not remove a cookie in the
browser — the current code clears one by overwriting it with a matching,
already-expired `set()`; the roster cookie must follow the same pattern.

**Data protection.** The grid names people including FSCs under 18. It stays
behind the squadron password, is never written to disk on the dashboard, and
personal data never goes in a URL. Firestore needs a scheduled export — the
roster is now the record and losing it loses the attendance history.

**Emails.** Roster prompts are operational, not notifications. They must not
share the unsubscribe list with the authorisation expiry mail, or someone
opting out of one silently stops being asked for their availability.

## Out of scope

Duty assignment. Flying currency. Comparing who said they were coming against
who actually flew. A second squadron — though every record carries a squadron
ID so that stays cheap later.

## Known TODOs

- Reasons on pending changes are visible to the whole squadron. Revisit once
  members are submitting, in case people stop giving a reason rather than say
  it in front of everyone.
- Branch protection on `viking-log-keeper`. Streamlit Community Cloud deploys
  from the public repo, so a merged commit runs with the database credentials.
- `src/dashboard/auth.py` compares the squadron password in plain text against
  a value in MongoDB. Separate problem, worth fixing on its own account.
