"""
Program application deadlines for every US state RegenAI serves.

A small, typed, dated table of conservation and disaster-program deadlines
(NRCS EQIP/CSP funding cutoffs, FSA SDRP, state cover-crop insurance
discounts). Every entry records where the date came from (``source_url``)
and when it was last checked (``as_of``) so stale data is easy to spot in
code review.

Coverage: all 50 states, DC, and the territories whose NRCS office page could
be verified (Puerto Rico, US Virgin Islands, Guam). Each of those gets exactly
one NRCS cutoff row -- a ``confirmed`` date where one is published, otherwise a
``not_announced`` row linking to the office that serves it.

Why a Python module instead of the ``csp_application_deadlines`` table:
cutoffs change a handful of times a year, each change should be reviewed
together with its source, and the logic is trivially unit-testable with an
injected "today". The legacy table still holds FY2025 seed data and is not
read by the API.

Rules for editing the table:
    - Only add a ``deadline_date`` you can cite. Never estimate one.
    - ``confirmed``      -> date published by the agency (or reported from it).
    - ``expected``       -> the program runs every year but this year's dates
                            are not out yet. ``deadline_date`` stays None.
    - ``not_announced``  -> no cutoff published yet. ``deadline_date`` is None
                            and ``source_url`` points to the state NRCS office.
    - Bump ``as_of`` whenever you re-check an entry.
    - A state moves from ``not_announced`` to ``confirmed`` by adding a row to
      ``_SOURCED_DEADLINES``; its generated ``not_announced`` row then drops out
      on its own.
"""

from dataclasses import dataclass
from datetime import date, datetime
from functools import cache
from zoneinfo import ZoneInfo

from app.models.schemas import (
    DeadlineUrgency,
    ProgramDeadlineItem,
    ProgramDeadlinesResponse,
    ProgramDeadlineStatus,
)
from app.services.program_rules import CSP_PROGRAM_URL

ALL_STATES = "ALL"

URGENT_DAYS = 14
SOON_DAYS = 45

# US Central time (with daylight saving). A deadline stays visible through the
# end of its day in the middle of the country rather than disappearing in the
# evening when the UTC date rolls over.
_CENTRAL_TZ_KEY = "America/Chicago"


@cache
def _central_tz() -> ZoneInfo:
    """Resolve the Central zone on first use.

    Looked up lazily so a machine without IANA tz data (Windows needs the
    ``tzdata`` package) fails only here, not on application import.
    """
    return ZoneInfo(_CENTRAL_TZ_KEY)


_SERVICE_CENTER_LOCATOR = "https://www.farmers.gov/contact/service-center-locator"

# Dates the table was last reviewed against its sources. A row keeps the date it
# was actually re-checked, so an untouched row never looks fresher than it is.
_CHECKED_2026_09_13 = date(2026, 9, 13)
_CHECKED_2026_09_22 = date(2026, 9, 22)

_FY2026_NOTE = (
    "Last year (FY2026) NRCS used one national cutoff, Jan 15, 2026. "
    "States set their own cutoffs for FY2027."
)

_STATUS_SORT = {
    ProgramDeadlineStatus.confirmed: 0,
    ProgramDeadlineStatus.not_announced: 1,
    ProgramDeadlineStatus.expected: 2,
}


# ---------------------------------------------------------------------------
# States and their NRCS office pages
# ---------------------------------------------------------------------------

# Every jurisdiction RegenAI shows deadlines for. Territories are listed only
# where an NRCS office page was verified; American Samoa, the Northern Mariana
# Islands and the freely associated states share the Pacific Islands Area office
# and are not listed yet.
_STATE_NAMES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "PR": "Puerto Rico",
    "VI": "US Virgin Islands",
    "GU": "Guam",
}

COVERED_STATES: tuple[str, ...] = tuple(sorted(_STATE_NAMES))

# NRCS publishes a landing page per state at /state-offices/<state-name>, with
# the name lower-cased and hyphenated. A few jurisdictions sit elsewhere on the
# site, so they are listed explicitly rather than derived.
_STATE_OFFICE_BASE = "https://www.nrcs.usda.gov/state-offices"
_OFFICE_URL_OVERRIDES: dict[str, str] = {
    "MO": "https://www.nrcs.usda.gov/nrcs/missouri",
    # NRCS lists no separate District of Columbia office, so send the farmer to
    # the locator instead of a page that does not exist.
    "DC": _SERVICE_CENTER_LOCATOR,
    "PR": f"{_STATE_OFFICE_BASE}/caribbean-area",
    "VI": f"{_STATE_OFFICE_BASE}/caribbean-area",
    "GU": (
        "https://www.nrcs.usda.gov/contact/state-office-contacts/"
        "pacific-islands-area-state-office"
    ),
}

# Extra sentence for jurisdictions whose office is not named after the place
# itself, so the link does not look like a mistake.
_OFFICE_NOTES: dict[str, str] = {
    "DC": (
        "NRCS has no separate District of Columbia state office. Use the USDA "
        "Service Center locator to find the office that serves your land."
    ),
    "PR": "Puerto Rico is served by the NRCS Caribbean Area office.",
    "VI": "The US Virgin Islands are served by the NRCS Caribbean Area office.",
    "GU": "Guam is served by the NRCS Pacific Islands Area office.",
}


def _office_url(state: str) -> str:
    """URL of the NRCS office page that serves ``state``."""
    override = _OFFICE_URL_OVERRIDES.get(state)
    if override:
        return override
    slug = _STATE_NAMES[state].lower().replace(" ", "-")
    return f"{_STATE_OFFICE_BASE}/{slug}"


@dataclass(frozen=True)
class ProgramDeadline:
    """One row of the deadline table (static data, no computed fields)."""

    id: str
    program: str
    state: str  # two-letter code or ALL_STATES
    title: str
    description: str
    status: ProgramDeadlineStatus
    source_url: str
    as_of: date
    period_label: str
    fiscal_year: int | None = None
    deadline_date: date | None = None
    notes: str | None = None
    # True for the state's EQIP/CSP ranking-cutoff row; exactly one row per
    # state carries it. get_upcoming_deadlines looks for this flag to decide
    # whether the farmer still needs the generic fallback row.
    is_nrcs_cutoff: bool = False


def _not_announced_nrcs(state: str) -> ProgramDeadline:
    """Row for a covered state with no published FY2027 cutoff."""
    state_name = _STATE_NAMES[state]
    office_note = _OFFICE_NOTES.get(state)
    return ProgramDeadline(
        id=f"{state.lower()}-nrcs-fy2027",
        program="EQIP and CSP",
        state=state,
        title="EQIP and CSP cutoff for 2027 funding",
        description=(
            f"{state_name} NRCS has not announced its cutoff for 2027 funding yet. "
            "You can apply any time. Check with your state NRCS office so your "
            "application makes the first ranking round."
        ),
        status=ProgramDeadlineStatus.not_announced,
        source_url=_office_url(state),
        as_of=_CHECKED_2026_09_22,
        period_label="FY2027 funding",
        fiscal_year=2027,
        notes=f"{_FY2026_NOTE} {office_note}" if office_note else _FY2026_NOTE,
        is_nrcs_cutoff=True,
    )


def _confirmed_nrcs_cutoff(
    state: str,
    programs: str,
    deadline_date: date,
    source_url: str,
    notes: str,
    as_of: date = _CHECKED_2026_09_22,
) -> ProgramDeadline:
    """Row for a state whose FY2027 ranking cutoff has been published."""
    return ProgramDeadline(
        id=f"{state.lower()}-nrcs-fy2027",
        program=programs,
        state=state,
        title="NRCS conservation program applications for 2027 funding",
        description=(
            "Get your application to your local NRCS office by this date to be "
            "considered for 2027 funding. Later applications wait for the next "
            "funding round."
        ),
        status=ProgramDeadlineStatus.confirmed,
        source_url=source_url,
        as_of=as_of,
        period_label="FY2027 funding",
        fiscal_year=2027,
        deadline_date=deadline_date,
        notes=notes,
        is_nrcs_cutoff=True,
    )


# ---------------------------------------------------------------------------
# Sourced entries. Every date here carries its citation in ``source_url``.
# ---------------------------------------------------------------------------

_SOURCED_DEADLINES: tuple[ProgramDeadline, ...] = (
    # --- All states -------------------------------------------------------
    ProgramDeadline(
        id="all-sdrp-2026",
        program="SDRP",
        state=ALL_STATES,
        title="Supplemental Disaster Relief Program (SDRP)",
        description=(
            "Last day to apply at your FSA county office for SDRP Stage 1 and "
            "Stage 2 payments on 2023 and 2024 disaster crop losses."
        ),
        status=ProgramDeadlineStatus.confirmed,
        source_url=(
            "https://www.fsa.usda.gov/resources/disaster-recovery/"
            "supplemental-disaster-relief-program-sdrp"
        ),
        as_of=_CHECKED_2026_09_13,
        period_label="2023 and 2024 crop losses",
        deadline_date=date(2026, 9, 30),
        notes=(
            "Extended deadline for both stages. If you get an SDRP payment you "
            "must buy crop insurance or NAP coverage for the next two crop years."
        ),
    ),
    # --- Iowa -------------------------------------------------------------
    ProgramDeadline(
        id="ia-nrcs-fy2027",
        program="EQIP and CSP",
        state="IA",
        title="EQIP and CSP applications for 2027 funding",
        description=(
            "Get your EQIP or CSP application to your local NRCS office by this "
            "date to be considered for 2027 funding. Later applications wait for "
            "the next funding round."
        ),
        status=ProgramDeadlineStatus.confirmed,
        source_url=(
            "https://www.tamatoledonews.com/news/local-news/2026/09/11/"
            "iowa-csp-eqip-application-deadline-set-for-sept-25/"
        ),
        as_of=_CHECKED_2026_09_13,
        period_label="FY2027 funding",
        fiscal_year=2027,
        deadline_date=date(2026, 9, 25),
        notes="Reported in local press on Sep 11, 2026. Confirm with your county NRCS office.",
        is_nrcs_cutoff=True,
    ),
    ProgramDeadline(
        id="ia-cover-crop-discount-2027",
        program="Cover crop insurance discount",
        state="IA",
        title="Iowa cover crop insurance discount ($5 per acre)",
        description=(
            "Iowa usually opens sign-up for this $5 per acre crop insurance "
            "discount for fall-planted cover crops in December. This year's dates "
            "are not announced yet. Last sign-up ran Dec 1, 2025 to Jan 23, 2026."
        ),
        status=ProgramDeadlineStatus.expected,
        source_url=(
            "https://iowaagriculture.gov/news/crop-ins-discount-prog-signup-12-25"
        ),
        as_of=_CHECKED_2026_09_13,
        period_label="2027 crop insurance premiums",
        notes=(
            "Cover crop acres enrolled in other state (IDALS) or USDA-NRCS "
            "cost-share programs, such as EQIP, do not qualify."
        ),
    ),
    # --- Illinois ---------------------------------------------------------
    ProgramDeadline(
        id="il-cover-crop-discount-2027",
        program="Cover crop insurance discount",
        state="IL",
        title="Illinois cover crop premium discount ($5 per acre)",
        description=(
            "Illinois usually runs this $5 per acre crop insurance discount for "
            "fall-planted cover crops from mid-December to mid-January. This "
            "year's dates are not announced yet. Last sign-up ran Dec 15, 2025 "
            "to Jan 15, 2026."
        ),
        status=ProgramDeadlineStatus.expected,
        source_url=(
            "https://agr.illinois.gov/resources/landwater/"
            "cover-crops-premium-discount-program.html"
        ),
        as_of=_CHECKED_2026_09_13,
        period_label="2027 crop insurance premiums",
        notes=(
            "Acres that get NRCS cost-share (such as EQIP) for cover crops cannot "
            "also get this discount."
        ),
    ),
    # --- States with a published FY2027 NRCS cutoff -----------------------
    _confirmed_nrcs_cutoff(
        "IN",
        "EQIP, CSP and ACEP",
        date(2026, 12, 18),
        "https://www.nrcs.usda.gov/state-offices/indiana/news/"
        "nrcs-in-indiana-accepting-applications-for-conservation-programs",
        "NRCS Indiana gives the date as December 18 for fiscal year 2027 "
        "funding, which makes it Dec 18, 2026.",
        as_of=_CHECKED_2026_09_13,
    ),
    _confirmed_nrcs_cutoff(
        "WI",
        "EQIP, CSP, ACEP and RCPP",
        date(2026, 9, 18),
        "https://wisconsinagconnection.com/news/"
        "wisconsin-farmers-encouraged-to-apply-for-nrcs-aid",
        "Reported Aug 17, 2026, quoting NRCS Wisconsin. Re-checked Sep 22, 2026: "
        "this cutoff has passed and no later FY2027 cutoff has been published.",
    ),
    _confirmed_nrcs_cutoff(
        "MT",
        "EQIP, CSP, ACEP, RCPP and RPP",
        date(2026, 10, 2),
        "https://www.ekalakaeagle.com/story/2026/08/21/regional/"
        "nrcs-accepting-applications-for-conservation-programs-oct-2-deadline"
        "-for-2027-funding/6858.html",
        "Reported Aug 21, 2026, quoting NRCS Montana. Confirm with your county "
        "NRCS office.",
    ),
    _confirmed_nrcs_cutoff(
        "NH",
        "EQIP, CSP, ACEP and AMA",
        date(2026, 10, 16),
        "https://www.nrcs.usda.gov/NewHampshire/news/"
        "nrcs-in-new-hampshire-accepting-applications-for-conservation-programs",
        "NRCS New Hampshire asks producers to apply by Oct 16, 2026 for fiscal "
        "year 2027 funding.",
    ),
    _confirmed_nrcs_cutoff(
        "SD",
        "EQIP, CSP, ACEP and RCPP",
        date(2026, 9, 29),
        "https://www.farms.com/news/nrcs-announces-fy27-conservation-program"
        "-application-batching-date-for-eqip-csp-acep-and-rcpp-246336.aspx",
        "Reported Aug 31, 2026, quoting NRCS South Dakota. Applications after "
        "this date are considered in the next application period.",
    ),
    _confirmed_nrcs_cutoff(
        "NC",
        "EQIP, CSP, ACEP and RPP",
        date(2026, 10, 30),
        "https://mcdowellnews.com/article_f7204ac0-5deb-5dff-8a29-d497e88bad1b.html",
        "Reported Sep 18, 2026, quoting NRCS North Carolina. Confirm with your "
        "county NRCS office.",
    ),
    _confirmed_nrcs_cutoff(
        "VA",
        "EQIP, CSP, ACEP, RCPP and RPP",
        date(2026, 10, 30),
        "https://henrycountyenterprise.com/"
        "nrcs-application-deadline-set-for-oct-30-2026-09-03/",
        "Reported Sep 2, 2026, quoting NRCS Virginia. Confirm with your county "
        "NRCS office.",
    ),
    _confirmed_nrcs_cutoff(
        "TX",
        "EQIP, CSP, ACEP, RCPP and RPP",
        date(2026, 11, 13),
        "https://www.morningagclips.com/"
        "nrcs-in-texas-accepting-applications-for-conservation-programs/",
        "Reported Sep 16, 2026, quoting NRCS Texas. Confirm with your county "
        "NRCS office.",
    ),
)

_STATES_WITH_SOURCED_CUTOFF = frozenset(
    entry.state for entry in _SOURCED_DEADLINES if entry.is_nrcs_cutoff
)

PROGRAM_DEADLINES: tuple[ProgramDeadline, ...] = _SOURCED_DEADLINES + tuple(
    _not_announced_nrcs(state)
    for state in COVERED_STATES
    if state not in _STATES_WITH_SOURCED_CUTOFF
)


def today_central() -> date:
    """Today's date in US Central time. Used as a FastAPI dependency."""
    return datetime.now(tz=_central_tz()).date()


def compute_urgency(days_remaining: int) -> DeadlineUrgency:
    """Classify how soon a deadline is: <=14 urgent, <=45 soon, else later."""
    if days_remaining <= URGENT_DAYS:
        return DeadlineUrgency.urgent
    if days_remaining <= SOON_DAYS:
        return DeadlineUrgency.soon
    return DeadlineUrgency.later


def _generic_entry(state: str) -> ProgramDeadline:
    """Fallback row for a state with no upcoming NRCS cutoff.

    Covers both a state outside the table and a covered state whose published
    cutoff has already passed, so the farmer always gets a next step.
    """
    return ProgramDeadline(
        id=f"{(state or 'national').lower()}-nrcs-generic",
        program="EQIP and CSP",
        state=state or ALL_STATES,
        title="EQIP and CSP cutoff for your state",
        description=(
            "RegenAI does not have an upcoming NRCS cutoff for this state. NRCS "
            "takes applications all year; ask your local USDA Service Center for "
            "the next ranking cutoff."
        ),
        status=ProgramDeadlineStatus.not_announced,
        source_url=_SERVICE_CENTER_LOCATOR,
        as_of=_CHECKED_2026_09_22,
        period_label="Next funding round",
        is_nrcs_cutoff=True,
    )


def _to_item(entry: ProgramDeadline, today: date) -> ProgramDeadlineItem:
    days: int | None = None
    urgency: DeadlineUrgency | None = None
    if entry.deadline_date is not None:
        days = (entry.deadline_date - today).days
        urgency = compute_urgency(days)
    return ProgramDeadlineItem(
        id=entry.id,
        program=entry.program,
        state=entry.state,
        title=entry.title,
        description=entry.description,
        status=entry.status,
        source_url=entry.source_url,
        as_of=entry.as_of,
        period_label=entry.period_label,
        fiscal_year=entry.fiscal_year,
        deadline_date=entry.deadline_date,
        notes=entry.notes,
        days_remaining=days,
        urgency=urgency,
        cutoff_date=entry.deadline_date,
        signup_period=entry.period_label,
    )


def get_upcoming_deadlines(
    state: str | None,
    today: date,
    table: tuple[ProgramDeadline, ...] = PROGRAM_DEADLINES,
) -> list[ProgramDeadlineItem]:
    """Return deadlines for ``state`` plus all-state entries, soonest first.

    Dated entries before ``today`` are dropped (a deadline on ``today`` is kept
    with 0 days remaining). Undated entries (``not_announced`` / ``expected``)
    are always kept and sorted after dated ones, NRCS cutoffs first. When no
    upcoming entry carries the state's NRCS cutoff, a generic fallback is added
    so the farmer is never left without a next step.
    """
    key = (state or "").strip().upper()
    entries = [e for e in table if e.state == ALL_STATES or (key and e.state == key)]

    upcoming = [e for e in entries if e.deadline_date is None or e.deadline_date >= today]
    if not any(e.is_nrcs_cutoff and e.state == key for e in upcoming):
        upcoming.append(_generic_entry(key))

    upcoming.sort(
        key=lambda e: (
            e.deadline_date is None,
            e.deadline_date or date.max,
            _STATUS_SORT[e.status],
            e.id,
        )
    )
    return [_to_item(e, today) for e in upcoming]


def build_deadlines_response(state: str | None, today: date) -> ProgramDeadlinesResponse:
    """Assemble the GET /csp/deadlines payload."""
    key = (state or "").strip().upper()
    return ProgramDeadlinesResponse(
        state=key or "NATIONAL",
        today=today,
        deadlines=get_upcoming_deadlines(key, today),
        advisory=(
            "NRCS takes applications all year, but each state sets a cutoff for "
            "each funding round. Applications in by the cutoff are ranked "
            "together. Dates can change, so confirm with your local USDA Service "
            "Center before you rely on them."
        ),
        program_url=CSP_PROGRAM_URL,
    )
