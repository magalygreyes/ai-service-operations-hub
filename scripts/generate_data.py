"""
Breezio Service Hub: synthetic data generator
Slice 1, Phase 3

Creates one year of fictional service requests for Breezio:
  - Sep 2025 to Feb 2026: current_state era (email, no AI, no SLAs)
  - Mar 2026 to Aug 2026: future_state era (form, simulated AI, rules, SLAs)

Every rate below comes from an assumption ID in docs/process-maps.md
(MA-xx for the current state, MF-xx for the future state) or a KPI target
in docs/discovery.md. The future-state year is simulated AT those targets.
It shows the pipeline and the KPI math working. It does not prove the
targets will be met.

AI predictions in this file are SIMULATED (model_name = "simulator").
Phase 4 adds a real classifier.

Uses only the Python standard library. Same seed, same data (NFR-11).

Run from the repo folder:
    python scripts/generate_data.py
Output: CSV files in the data/ folder.
"""

import csv
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
rng = random.Random(SEED)

# ---------------------------------------------------------------------------
# Calendar. Breezio runs on one fixed time zone (UTC-6) to keep the math
# simple. Business hours: Monday to Friday, 8:00 to 17:00. No holidays.
# ---------------------------------------------------------------------------
TZ = timezone(timedelta(hours=-6))
OPEN_HOUR, CLOSE_HOUR = 8, 17
BH_PER_DAY = CLOSE_HOUR - OPEN_HOUR  # 9

CURRENT_START = datetime(2025, 9, 1, tzinfo=TZ)
FUTURE_START = datetime(2026, 3, 1, tzinfo=TZ)
END = datetime(2026, 9, 1, tzinfo=TZ)
AS_OF = datetime(2026, 8, 31, 17, 0, tzinfo=TZ)  # snapshot moment for open items

OUT_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Assumptions. Each one points at its source.
# ---------------------------------------------------------------------------
REQUESTS_PER_MONTH = 600                     # MA-01
TEAM_MIX = {"IT": 0.45, "HR": 0.25, "FAC": 0.15, "FIN": 0.15}  # discovery.md §2

ERA = {
    "current_state": {
        "misroute_rate": 0.18,               # MA-03
        "missing_info_rate": 0.30,           # MA-04
        "status_inquiries_per_request": 0.6, # MA-06
        "first_routing_median_bh": 8.0,      # tuned so K1 median is about 9 (K1 baseline)
        "reroute_delay_median_bh": 6.0,
        "info_reply_median_bh": 13.5,        # 1.5 business days
        "manager_approval_median_bh": 22.5,  # K6 baseline 2.5 days
        "finance_approval_median_bh": 13.5,
        "work_factor": 0.35,                 # work time as a share of the category SLA
        "work_sigma": 0.9,
        "queue_median_bh": 4.0,              # waiting in a queue with no SLA to prioritise against
    },
    "future_state": {
        "missing_info_rate": 0.10,           # MF-04, at K5 target
        "status_inquiries_per_request": 0.15,# MF-04, at K7 target
        "band_mix": {"auto_route": 0.60, "route_and_flag": 0.25, "human_triage": 0.15},  # MF-03 base
        "correct_rate": {"auto_route": 0.97, "route_and_flag": 0.85, "human_triage": 0.55},
        "flag_review_catch_rate": 0.90,
        "triage_accuracy": 0.98,
        "flag_review_median_bh": 0.5,
        "human_triage_median_bh": 1.5,
        "late_reroute_median_bh": 3.0,
        "info_reply_median_bh": 4.5,
        "manager_approval_median_bh": 9.0,   # K6 target 1 day
        "finance_approval_median_bh": 7.0,
        "work_factor": 0.35,
        "work_sigma": 0.75,
        "queue_median_bh": 0.0,
    },
}
APPROVAL_REJECT_RATE = 0.05
FINANCE_THRESHOLD = 2500                     # BR-05, D9
HIGH_PRIORITY_SLA_CAP_BH = 9                 # BR-07
AUTO_CLOSE_BH = 5 * BH_PER_DAY               # BR-09

# ---------------------------------------------------------------------------
# Taxonomy v1.0 (must match sql/02_reference_data.sql)
# id: (team, weight within team, required fields, approval rule, sensitive, SLA hours)
# ---------------------------------------------------------------------------
CATEGORIES = {
    "CAT-IT-01": ("IT", 0.12, ["system", "access_level", "business_reason"], "manager", False, 18),
    "CAT-IT-02": ("IT", 0.06, ["item", "business_reason", "cost_center"], "manager", False, 45),
    "CAT-IT-03": ("IT", 0.06, ["software_name", "license_count", "cost_center"], "manager_plus_finance_over_threshold", False, 27),
    "CAT-IT-04": ("IT", 0.28, ["system"], "none", False, 4.5),
    "CAT-IT-05": ("IT", 0.30, ["system_or_device", "who_is_affected"], "none", False, 9),
    "CAT-IT-06": ("IT", 0.18, ["system"], "none", False, 18),
    "CAT-HR-01": ("HR", 0.18, ["topic"], "none", True, 27),
    "CAT-HR-02": ("HR", 0.20, ["pay_period"], "none", True, 18),
    "CAT-HR-03": ("HR", 0.12, ["leave_type", "start_date", "end_date"], "manager", True, 18),
    "CAT-HR-04": ("HR", 0.15, ["employee_name", "role", "effective_date", "manager"], "none", True, 45),
    "CAT-HR-05": ("HR", 0.12, ["letter_type", "recipient"], "none", True, 27),
    "CAT-HR-06": ("HR", 0.23, ["topic"], "none", False, 27),
    "CAT-FAC-01": ("FAC", 0.70, ["building", "floor", "room", "description"], "none", False, 18),
    "CAT-FAC-02": ("FAC", 0.08, ["current_location", "requested_location", "move_date"], "manager", False, 90),
    "CAT-FAC-03": ("FAC", 0.22, ["building", "access_area", "start_date"], "manager", False, 18),
    "CAT-FIN-01": ("FIN", 0.30, ["amount", "expense_date", "receipt", "cost_center"], "manager", False, 45),
    "CAT-FIN-02": ("FIN", 0.15, ["item_or_service", "vendor", "amount", "cost_center"], "manager_plus_finance_over_threshold", False, 45),
    "CAT-FIN-03": ("FIN", 0.55, ["vendor_name", "invoice_number"], "none", False, 27),
}
UNCLASSIFIED = "CAT-GEN-00"

# ---------------------------------------------------------------------------
# Request text. "full" templates contain every required field. "vague"
# templates leave some out, and list which ones are missing.
# ---------------------------------------------------------------------------
SYSTEMS = ["Salesforce", "Workday", "Slack", "Jira", "the VPN", "Google Drive", "Zoom", "NetSuite", "GitHub", "Okta"]
SOFTWARE = ["Figma", "Tableau", "Adobe Acrobat Pro", "Miro", "Postman", "Lucidchart"]
HARDWARE = ["a second monitor", "a docking station", "a replacement laptop", "a keyboard and mouse", "a noise-cancelling headset"]
BUILDINGS = ["Main Office", "North Building"]
VENDORS = ["Northwind Supplies", "Contoso Print", "Fabrikam Catering", "Tailspin Logistics", "Globex Office"]
AREAS = ["the server room", "the lab", "the parking garage", "the 4th floor"]
LEAVE = ["vacation", "parental leave", "jury duty", "bereavement leave"]
LETTERS = ["an employment verification letter", "a salary confirmation letter", "a visa support letter"]
TOPICS_BEN = ["dental coverage", "adding a dependent", "the 401k match", "vision benefits"]
TOPICS_POL = ["the remote work policy", "the travel policy", "the holiday schedule", "the equipment policy"]
ISSUES = ["keeps crashing", "won't load", "is showing an error", "is extremely slow"]
ROLES = ["Account Executive", "Software Engineer", "Marketing Coordinator", "Customer Success Manager"]


def slots():
    d = rng.randint(1, 28)
    return {
        "system": rng.choice(SYSTEMS), "software": rng.choice(SOFTWARE), "hw": rng.choice(HARDWARE),
        "cc": f"CC-{rng.randint(1001, 1040)}", "n": rng.randint(1, 5), "bldg": rng.choice(BUILDINGS),
        "floor": rng.randint(1, 4), "room": f"{rng.randint(1, 4)}.{rng.randint(10, 40)}",
        "vendor": rng.choice(VENDORS), "inv": f"INV-{rng.randint(40000, 49999)}",
        "area": rng.choice(AREAS), "leave": rng.choice(LEAVE), "letter": rng.choice(LETTERS),
        "ben": rng.choice(TOPICS_BEN), "pol": rng.choice(TOPICS_POL), "issue": rng.choice(ISSUES),
        "role": rng.choice(ROLES), "d1": f"Oct {d}", "d2": f"Oct {min(d + rng.randint(1, 10), 31)}",
        "period": rng.choice(["last pay period", "the Oct 15 paycheck", "the Sep 30 paycheck"]),
        "people": rng.choice(["just me", "our whole team", "about 10 people"]),
    }


TEXT = {
    "CAT-IT-01": {
        "full": ["I need {system} access with editor rights so I can update our team's records for the Q4 project.",
                 "Could I get read-only access to {system}? My manager asked me to pull reports from it for the weekly review."],
        "vague": [("Can I get access to {system}?", ["access_level", "business_reason"]),
                  ("I need access to a new tool for my job.", ["system", "access_level", "business_reason"])],
    },
    "CAT-IT-02": {
        "full": ["Requesting {hw} for my desk. My current one is failing and slowing me down. Cost center {cc}.",
                 "I'd like {hw}, I work with large spreadsheets all day. Please charge cost center {cc}."],
        "vague": [("Can I get {hw}?", ["business_reason", "cost_center"]),
                  ("I need new equipment please.", ["item", "business_reason", "cost_center"])],
    },
    "CAT-IT-03": {
        "full": ["Please buy {n} {software} licenses for our team, cost center {cc}.",
                 "Requesting {n} seat(s) of {software} for the design review work, charge {cc}."],
        "vague": [("We need {software} for the team.", ["license_count", "cost_center"]),
                  ("Can we get some new software licenses?", ["software_name", "license_count", "cost_center"])],
    },
    "CAT-IT-04": {
        "full": ["I'm locked out of {system}. It says my account is disabled after too many attempts.",
                 "Forgot my {system} password and the reset link isn't arriving. Can someone help?"],
        "vague": [("I'm locked out, please help!", ["system"]),
                  ("My password stopped working this morning.", ["system"])],
    },
    "CAT-IT-05": {
        "full": ["{system} {issue} for {people}. Started about an hour ago.",
                 "My laptop (asset tag BRZ-{inv}) {issue} whenever I open {system}. Affects {people}."],
        "vague": [("Something {issue}, can someone look?", ["system_or_device", "who_is_affected"]),
                  ("{system} {issue}.", ["who_is_affected"])],
    },
    "CAT-IT-06": {
        "full": ["How do I share a folder in {system} with someone outside the company?",
                 "Is there a way to set up an out-of-office reply in {system}?"],
        "vague": [("How do I do this? Couldn't find it in the help page.", ["system"])],
    },
    "CAT-HR-01": {
        "full": ["I have a question about {ben}. Where can I see what is covered?",
                 "When is the deadline to change {ben}?"],
        "vague": [("Question about my benefits.", ["topic"])],
    },
    "CAT-HR-02": {
        "full": ["My overtime is missing from {period}. Can someone check?",
                 "The tax withholding on {period} looks wrong."],
        "vague": [("Something is off with my paycheck.", ["pay_period"])],
    },
    "CAT-HR-03": {
        "full": ["I'd like to request {leave} from {d1} to {d2}.",
                 "Submitting a request for {leave}, {d1} through {d2}."],
        "vague": [("I need to take some time off next month.", ["leave_type", "start_date", "end_date"]),
                  ("Requesting {leave}.", ["start_date", "end_date"])],
    },
    "CAT-HR-04": {
        "full": ["New hire starting {d1}: Jordan Lee, {role}, reporting to me. Please start onboarding.",
                 "Please process offboarding for Casey Morgan, {role}, last day {d1}. I'm their manager."],
        "vague": [("We have someone new starting soon, what do I need to do?", ["employee_name", "role", "effective_date", "manager"])],
    },
    "CAT-HR-05": {
        "full": ["Could I get {letter} addressed to my bank?",
                 "I need {letter} for my apartment application, addressed to the leasing office."],
        "vague": [("I need a letter from HR.", ["letter_type", "recipient"])],
    },
    "CAT-HR-06": {
        "full": ["Can you point me to {pol}? I want to check what applies to contractors.",
                 "Has {pol} changed this year?"],
        "vague": [("Where can I find the policy on this?", ["topic"])],
    },
    "CAT-FAC-01": {
        "full": ["The heating isn't working in {bldg}, floor {floor}, room {room}. It's very cold.",
                 "Leaking tap in the kitchen on floor {floor} of {bldg}, near room {room}."],
        "vague": [("The AC is broken again.", ["building", "floor", "room"]),
                  ("Light is flickering in {bldg}.", ["floor", "room"])],
    },
    "CAT-FAC-02": {
        "full": ["Our team is moving from floor {floor} to floor {n} of {bldg} on {d1}. Can Facilities plan desks?",
                 "Could I move from desk {room} to a desk near my team on floor {floor}, starting {d1}?"],
        "vague": [("Can I change desks?", ["current_location", "requested_location", "move_date"])],
    },
    "CAT-FAC-03": {
        "full": ["I need badge access to {area} in {bldg} starting {d1} for the equipment audit.",
                 "Please add {area} in {bldg} to my badge from {d1}."],
        "vague": [("My badge doesn't open a door I need.", ["building", "access_area", "start_date"])],
    },
    "CAT-FIN-01": {
        "full": ["Submitting a ${amount} expense for a client dinner on {d1}, receipt attached, cost center {cc}.",
                 "Reimbursement for ${amount} of travel on {d1}. Receipt attached. Charge {cc}."],
        "vague": [("How do I get reimbursed for a work dinner?", ["amount", "expense_date", "receipt", "cost_center"]),
                  ("Expense for ${amount}, receipt attached.", ["expense_date", "cost_center"])],
    },
    "CAT-FIN-02": {
        "full": ["Please raise a purchase order for ${amount} with {vendor} for event supplies, cost center {cc}.",
                 "Requesting a ${amount} purchase from {vendor}, charge to {cc}."],
        "vague": [("We need to buy some supplies from {vendor}.", ["item_or_service", "amount", "cost_center"])],
    },
    "CAT-FIN-03": {
        "full": ["{vendor} says invoice {inv} is overdue. Can you check the payment status?",
                 "Has invoice {inv} from {vendor} been paid?"],
        "vague": [("A vendor is asking about a late payment.", ["vendor_name", "invoice_number"])],
    },
}

# ---------------------------------------------------------------------------
# Employees (fictional). Named stakeholders from docs/org-chart.md are fixed.
# ---------------------------------------------------------------------------
FIRST = ["Alex", "Maya", "Noah", "Zara", "Ethan", "Lina", "Omar", "Chloe", "Diego", "Hana", "Isaac", "Kira",
         "Leo", "Mei", "Nadia", "Oscar", "Paula", "Quinn", "Rafael", "Sana", "Theo", "Uma", "Victor", "Wren",
         "Yusuf", "Ava", "Ben", "Carmen", "Dev", "Elsa", "Felix", "Gia", "Hugo", "Ines", "Jonah", "Keiko",
         "Liam", "Mira", "Nico", "Olivia", "Pedro", "Rosa", "Sami", "Tara", "Ulises", "Vera", "Will", "Ximena"]
LAST = ["Abara", "Brooks", "Castillo", "Duarte", "Eriksen", "Farouk", "Gallo", "Haddad", "Iwata", "Jensen",
        "Kowalski", "Lambert", "Moreau", "Nakamura", "Ortega", "Patel", "Quintero", "Rossi", "Sato", "Tanaka",
        "Urban", "Vance", "Walsh", "Xu", "Young", "Zamora", "Bishop", "Cruz", "Dunn", "Ellis", "Flores", "Grant"]

DEPARTMENTS = [  # (department, headcount excluding named leaders, managers)
    ("IT", 11, 1), ("HR", 6, 0), ("Facilities", 4, 0), ("Finance", 8, 0),
    ("Security and Privacy", 2, 0), ("Engineering and Product", 99, 8),
    ("Sales", 75, 6), ("Customer Success", 55, 5), ("Marketing", 28, 3),
]
DEPT_TEAM = {"IT": "IT", "HR": "HR", "Facilities": "FAC", "Finance": "FIN"}


def build_employees():
    emps = []

    def add(name, dept, title, manager_id, is_manager):
        eid = f"EMP-{len(emps) + 1:04d}"
        emps.append({"employee_id": eid, "full_name": name, "department": dept, "job_title": title,
                     "manager_id": manager_id, "is_manager": is_manager})
        return eid

    ceo = add("Daniel Okafor", "Executive", "Chief Executive Officer", None, True)
    coo = add("Renata Velez", "Executive", "Chief Operating Officer", ceo, True)
    cfo = add("Helen Cho", "Executive", "Chief Financial Officer", ceo, True)
    cto = add("Arjun Mehta", "Executive", "Chief Technology Officer", ceo, True)
    vps = add("Grace Adeyemi", "Executive", "VP Sales", ceo, True)
    vpc = add("Owen Brennan", "Executive", "VP Customer Success", ceo, True)
    vpm = add("Sofia Marchetti", "Executive", "VP Marketing", ceo, True)
    leads = {
        "IT": add("Priya Raman", "IT", "IT Service Desk Lead", coo, True),
        "HR": add("Aisha Bello", "HR", "HR Operations Manager", coo, True),
        "Facilities": add("Tomas Garza", "Facilities", "Facilities Manager", coo, True),
        "Finance": add("David Mensah", "Finance", "Finance Manager", cfo, True),
        "Security and Privacy": add("Elena Petrova", "Security and Privacy", "Security and Privacy Lead", cto, True),
    }
    coords = {
        "IT": add("Jess Park", "IT", "Request Coordinator", leads["IT"], False),
        "HR": add("Luis Moreno", "HR", "Request Coordinator", leads["HR"], False),
        "FAC": add("Nora Fitzgerald", "Facilities", "Request Coordinator", leads["Facilities"], False),
        "FIN": add("Sam Whitaker", "Finance", "Request Coordinator", leads["Finance"], False),
    }
    heads = {"Engineering and Product": cto, "Sales": vps, "Customer Success": vpc, "Marketing": vpm}
    used = {e["full_name"] for e in emps}

    def new_name():
        while True:
            n = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if n not in used:
                used.add(n)
                return n

    for dept, count, n_mgr in DEPARTMENTS:
        if dept in ("IT", "HR", "Facilities", "Finance"):
            count -= 1  # coordinator already added
        top = leads.get(dept) or heads[dept]
        mgrs = [add(new_name(), dept, f"{dept} Manager", top, True) for _ in range(n_mgr)]
        for i in range(count - n_mgr):
            boss = mgrs[i % len(mgrs)] if mgrs else top
            title = "Specialist" if dept in DEPT_TEAM else "Individual Contributor"
            add(new_name(), dept, title, boss, False)
    assert len(emps) == 300, len(emps)
    return emps, leads, coords


# ---------------------------------------------------------------------------
# Business-hour helpers
# ---------------------------------------------------------------------------
def next_open(dt):
    while True:
        if dt.weekday() >= 5:
            dt = (dt + timedelta(days=7 - dt.weekday())).replace(hour=OPEN_HOUR, minute=0, second=0)
        elif dt.hour < OPEN_HOUR:
            dt = dt.replace(hour=OPEN_HOUR, minute=0, second=0)
        elif dt.hour >= CLOSE_HOUR:
            dt = (dt + timedelta(days=1)).replace(hour=OPEN_HOUR, minute=0, second=0)
        else:
            return dt


def add_bh(dt, hours):
    dt = next_open(dt)
    remaining = hours * 3600.0
    while True:
        close = dt.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0)
        left_today = (close - dt).total_seconds()
        if remaining <= left_today:
            return dt + timedelta(seconds=remaining)
        remaining -= left_today
        dt = next_open(close)


def bh_between(a, b):
    if b <= a:
        return 0.0
    total, dt = 0.0, next_open(a)
    while dt < b:
        close = dt.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0)
        total += (min(close, b) - dt).total_seconds()
        dt = next_open(close)
    return total / 3600.0


def lognorm(median, sigma=0.7):
    return median * math.exp(rng.gauss(0, sigma))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def pick(weights):
    r, acc = rng.random(), 0.0
    for k, w in weights.items():
        acc += w
        if r < acc:
            return k
    return k


def submission_times(start, end):
    per_weekday = REQUESTS_PER_MONTH * 12 / 52 / 5
    day, times = start, []
    while day < end:
        wd = day.weekday()
        if wd < 5:
            mult = {0: 1.2, 4: 0.85}.get(wd, 1.0) * (1.1 if day.month == 1 else 1.0)
            n = max(0, round(rng.gauss(per_weekday * mult, 4)))
        else:
            n = rng.choice([0, 1, 1, 2])
        for _ in range(n):
            if wd < 5 and rng.random() < 0.9:
                hour = min(16.99, max(8.0, rng.gauss(11.5, 2.3)))
            else:
                hour = rng.uniform(6, 22)
            times.append(day + timedelta(hours=hour))
        day += timedelta(days=1)
    return sorted(times)


def amount_for(cat):
    if cat == "CAT-IT-03":
        return round(lognorm(900, 1.0), 2)
    if cat == "CAT-FIN-02":
        return round(lognorm(1500, 0.9), 2)
    if cat == "CAT-FIN-01":
        return round(min(lognorm(120, 0.9), 3000), 2)
    return None


def make_text(cat, missing):
    s = slots()
    amt = amount_for(cat)
    s["amount"] = f"{amt:,.0f}" if amt else ""
    if missing:
        tmpl, fields = rng.choice(TEXT[cat]["vague"])
        return tmpl.format(**s), fields, amt
    return rng.choice(TEXT[cat]["full"]).format(**s), [], amt


def main():
    employees, leads, coords = build_employees()
    emp_by_id = {e["employee_id"]: e for e in employees}
    team_members = defaultdict(list)
    for e in employees:
        if e["department"] in DEPT_TEAM and e["job_title"] == "Specialist":
            team_members[DEPT_TEAM[e["department"]]].append(e["employee_id"])
    finance_approver = leads["Finance"]
    requesters = [e["employee_id"] for e in employees]
    cats_by_team = defaultdict(dict)
    for cid, c in CATEGORIES.items():
        cats_by_team[c[0]][cid] = c[1]
    teams = list(TEAM_MIX)

    requests, predictions, decisions, approvals, events = [], [], [], [], []
    seq_by_year = Counter()

    def ev(rid, etype, when, frm=None, to=None, actor=None):
        events.append({"request_id": rid, "event_type": etype, "from_value": frm, "to_value": to,
                       "actor_id": actor, "occurred_at": when})

    all_times = [(t, "current_state") for t in submission_times(CURRENT_START, FUTURE_START)]
    all_times += [(t, "future_state") for t in submission_times(FUTURE_START, END)]
    all_times = [x for x in all_times if x[0] <= AS_OF]

    for t0, era in all_times:
        p = ERA[era]
        seq_by_year[t0.year] += 1
        rid = f"BRZ-{t0.year}-{seq_by_year[t0.year]:05d}"
        team = pick(TEAM_MIX)
        cat = pick(cats_by_team[team])
        c_team, _, req_fields, approval_rule, sensitive, sla_bh = CATEGORIES[cat]
        missing = rng.random() < p["missing_info_rate"]
        text, missing_fields, amount = make_text(cat, missing)
        requester = rng.choice(requesters)
        if cat == "CAT-HR-04":
            requester = rng.choice([e for e in requesters if emp_by_id[e]["is_manager"]])
        priority = "high" if cat in ("CAT-IT-04", "CAT-IT-05", "CAT-FAC-01") and rng.random() < 0.3 else (
            "low" if rng.random() < 0.1 else "normal")

        # Channel
        on_behalf, submitted_by = False, None
        if era == "current_state":
            channel = pick({"email": 0.80, "chat": 0.12, "walk_up": 0.08})
        else:
            in_overlap = t0 < FUTURE_START + timedelta(days=30)   # D8
            channel = pick({"form": 0.70, "email": 0.20, "chat": 0.06, "walk_up": 0.04} if in_overlap
                           else {"form": 0.88, "chat": 0.08, "walk_up": 0.04})
            if channel in ("chat", "walk_up"):                    # D12, BR-10
                on_behalf, submitted_by = True, coords[team]

        ev(rid, "created", t0, to="new", actor=submitted_by or requester)
        status_log = [(t0, "new")]
        paused_bh = 0.0

        def set_status(when, new):
            if when > AS_OF:
                return
            ev(rid, "status_changed", when, frm=status_log[-1][1], to=new)
            status_log.append((when, new))

        # ---------------- Routing ----------------
        if era == "current_state":
            t = add_bh(t0, lognorm(p["first_routing_median_bh"], 0.8))
            first_team = team
            if rng.random() < p["misroute_rate"]:
                first_team = rng.choice([x for x in teams if x != team])
            ev(rid, "routed", t, to=first_team, actor=coords.get(first_team))
            set_status(t, "triaged")
            cur_team = first_team
            while cur_team != team:
                t = add_bh(t, lognorm(p["reroute_delay_median_bh"], 0.8))
                nxt = team if rng.random() < 0.8 else rng.choice([x for x in teams if x not in (team, cur_team)])
                ev(rid, "rerouted", t, frm=cur_team, to=nxt, actor=coords.get(cur_team))
                cur_team = nxt
            t_routed = t
        else:
            # Simulated classifier (Phase 4 replaces this with a real model)
            t_cls = t0 + timedelta(seconds=rng.randint(3, 9))
            band = pick(p["band_mix"])
            lo, hi = {"auto_route": (0.90, 0.995), "route_and_flag": (0.70, 0.899), "human_triage": (0.30, 0.699)}[band]
            conf = round(rng.uniform(lo, hi), 3)
            correct = rng.random() < p["correct_rate"][band]
            if correct:
                pred_cat = cat
            elif band == "human_triage" and rng.random() < 0.3:
                pred_cat = UNCLASSIFIED
            else:
                same = [x for x in cats_by_team[team] if x != cat]
                pool = same if rng.random() < 0.7 else [x for x in CATEGORIES if CATEGORIES[x][0] != team]
                pred_cat = rng.choice(pool)
            pred_team = CATEGORIES[pred_cat][0] if pred_cat != UNCLASSIFIED else None
            detected = [f for f in missing_fields if rng.random() < 0.9]
            predictions.append({
                "prediction_id": len(predictions) + 1, "request_id": rid,
                "predicted_team_id": pred_team, "predicted_category_id": pred_cat,
                "predicted_priority": priority, "confidence": conf,
                "reason": "Simulated prediction for synthetic data.",
                "missing_fields": detected, "model_name": "simulator", "prompt_version": "n/a",
                "is_valid": True, "created_at": t_cls})
            ev(rid, "classified", t_cls, to=pred_cat)

            # Rules layer (BR-01 to BR-04)
            pred_sensitive = pred_cat != UNCLASSIFIED and CATEGORIES[pred_cat][4]
            if pred_sensitive:
                rule, dband, route_to, flagged = "BR-04", "human_triage", "HR", False
            elif pred_cat == UNCLASSIFIED or conf < 0.70:
                rule, dband, route_to, flagged = "BR-03", "human_triage", None, False
            elif conf < 0.90:
                rule, dband, route_to, flagged = "BR-02", "route_and_flag", pred_team, True
            else:
                rule, dband, route_to, flagged = "BR-01", "auto_route", pred_team, False
            decisions.append({"decision_id": len(decisions) + 1, "request_id": rid,
                              "prediction_id": len(predictions), "band": dband, "rule_applied": rule,
                              "routed_team_id": route_to, "flagged_for_review": flagged,
                              "decided_at": t_cls + timedelta(seconds=1)})

            if dband == "human_triage":
                # A coordinator triages. HR triage queue for sensitive, general queue otherwise.
                queue_owner = coords["HR"] if rule == "BR-04" else coords[rng.choice(teams)]
                t = add_bh(t_cls, lognorm(p["human_triage_median_bh"], 0.7))
                first_team = team if rng.random() < p["triage_accuracy"] else rng.choice([x for x in teams if x != team])
                ev(rid, "routed", t, to=first_team, actor=queue_owner)
            else:
                t = t_cls + timedelta(seconds=2)
                first_team = pred_team
                ev(rid, "routed", t, to=first_team)
            set_status(t, "triaged")
            cur_team = first_team
            if cur_team != team:
                if dband == "route_and_flag" and rng.random() < p["flag_review_catch_rate"]:
                    t = add_bh(t, lognorm(p["flag_review_median_bh"], 0.6))
                else:
                    t = add_bh(t, lognorm(p["late_reroute_median_bh"], 0.8))
                ev(rid, "rerouted", t, frm=cur_team, to=team, actor=coords[cur_team])
                cur_team = team
            t_routed = t

        # ---------------- Missing information ----------------
        t = t_routed
        if missing_fields:
            t = add_bh(t, 0.2 if era == "future_state" else lognorm(2.0, 0.6))
            ev(rid, "info_requested", t, to=",".join(missing_fields), actor=coords[team])
            set_status(t, "awaiting_information")
            t_back = add_bh(t, lognorm(p["info_reply_median_bh"], 0.7))
            paused_bh += bh_between(t, t_back)
            t = t_back
            ev(rid, "info_received", t, actor=requester)
            if t > AS_OF:
                status_log.append((AS_OF, "awaiting_information"))

        # ---------------- Approvals ----------------
        rejected = False
        needs_finance = approval_rule == "manager_plus_finance_over_threshold" and amount and amount > FINANCE_THRESHOLD
        if approval_rule != "none" and t <= AS_OF:
            approver = emp_by_id[requester]["manager_id"] or requester
            steps = [(1, approver, "manager", p["manager_approval_median_bh"])]
            if needs_finance:
                steps.append((2, finance_approver, "finance", p["finance_approval_median_bh"]))
            set_status(t, "awaiting_approval")
            t_start_wait = t
            for step, who, role, med in steps:
                ev(rid, "approval_requested", t, to=role, actor=coords[team])
                t_dec = add_bh(t, lognorm(med, 0.7))
                decided = t_dec <= AS_OF
                decision = ("rejected" if rng.random() < APPROVAL_REJECT_RATE else "approved") if decided else "pending"
                approvals.append({"approval_id": len(approvals) + 1, "request_id": rid, "step": step,
                                  "approver_id": who, "approver_role": role, "requested_at": t,
                                  "decided_at": t_dec if decided else None, "decision": decision,
                                  "comment": "Not within budget this quarter." if decision == "rejected" else None})
                if not decided:
                    t = t_dec
                    break
                ev(rid, "approval_decided", t_dec, to=decision, actor=who)
                t = t_dec
                if decision == "rejected":
                    rejected = True
                    set_status(t, "rejected")
                    break
            paused_bh += bh_between(t_start_wait, min(t, AS_OF))

        # ---------------- Work and resolution ----------------
        cat_sla = min(sla_bh, HIGH_PRIORITY_SLA_CAP_BH) if priority == "high" else sla_bh
        resolved_at = closed_at = None
        if not rejected and t <= AS_OF:
            set_status(t, "in_progress")
            work = lognorm(max(1.0, p["work_factor"] * cat_sla), p["work_sigma"])
            if p["queue_median_bh"]:
                work += lognorm(p["queue_median_bh"], 0.8)
            t_res = add_bh(t, work)
            if t_res <= AS_OF:
                resolved_at = t_res
                actor = rng.choice(team_members[team]) if team_members[team] else coords[team]
                set_status(t_res, "resolved")
                t_close = add_bh(t_res, AUTO_CLOSE_BH)
                if t_close <= AS_OF:
                    closed_at = t_close
                    set_status(t_close, "closed")
        elif rejected:
            closed_at = t

        # ---------------- Status inquiries ----------------
        end_window = resolved_at or AS_OF
        k = sum(1 for _ in range(10) if rng.random() < p["status_inquiries_per_request"] / 10)
        for _ in range(k):
            when = t0 + (end_window - t0) * rng.random()
            ev(rid, "status_inquiry", when, actor=requester)

        sla_due = add_bh(t0, cat_sla + paused_bh) if era == "future_state" else None  # no SLAs before (D10)
        requests.append({
            "request_id": rid, "era": era, "requester_id": requester, "channel": channel,
            "submitted_on_behalf": on_behalf, "submitted_by_id": submitted_by, "submitted_at": t0,
            "description": text, "has_attachment": "attached" in text, "amount": amount,
            "priority": priority, "true_category_id": cat, "current_team_id": team,
            "current_category_id": cat, "status": status_log[-1][1], "sla_due_at": sla_due,
            "resolved_at": resolved_at, "closed_at": closed_at, "taxonomy_version": 1,
        })

    # Keep only events up to the snapshot, then number them in time order
    events = sorted((e for e in events if e["occurred_at"] <= AS_OF), key=lambda e: (e["occurred_at"], e["request_id"]))
    for i, e in enumerate(events, 1):
        e["event_id"] = i

    write_all(employees, requests, predictions, decisions, approvals, events)
    summarize(requests, predictions, decisions, approvals, events)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def fmt(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, list):
        return "{" + ",".join(v) + "}"
    return v


def write_csv(name, rows, cols):
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if fmt(r[c]) is None else fmt(r[c]) for c in cols])


def write_all(employees, requests, predictions, decisions, approvals, events):
    write_csv("employees", employees, ["employee_id", "full_name", "department", "job_title", "manager_id", "is_manager"])
    write_csv("requests", requests, ["request_id", "era", "requester_id", "channel", "submitted_on_behalf",
                                     "submitted_by_id", "submitted_at", "description", "has_attachment", "amount",
                                     "priority", "true_category_id", "current_team_id", "current_category_id",
                                     "status", "sla_due_at", "resolved_at", "closed_at", "taxonomy_version"])
    write_csv("ai_predictions", predictions, ["prediction_id", "request_id", "predicted_team_id",
                                              "predicted_category_id", "predicted_priority", "confidence", "reason",
                                              "missing_fields", "model_name", "prompt_version", "is_valid", "created_at"])
    write_csv("routing_decisions", decisions, ["decision_id", "request_id", "prediction_id", "band", "rule_applied",
                                               "routed_team_id", "flagged_for_review", "decided_at"])
    write_csv("approvals", approvals, ["approval_id", "request_id", "step", "approver_id", "approver_role",
                                       "requested_at", "decided_at", "decision", "comment"])
    write_csv("request_events", events, ["event_id", "request_id", "event_type", "from_value", "to_value",
                                         "actor_id", "occurred_at"])


def summarize(requests, predictions, decisions, approvals, events):
    by_req = defaultdict(list)
    for e in events:
        by_req[e["request_id"]].append(e)
    appr_by_req = defaultdict(list)
    for a in approvals:
        appr_by_req[a["request_id"]].append(a)
    open_status = {"new", "triaged", "awaiting_information", "awaiting_approval", "in_progress"}

    print(f"\nBreezio synthetic data, seed {SEED}, snapshot {AS_OF:%Y-%m-%d %H:%M}")
    print(f"Written to: {OUT_DIR}\n")
    header = f"{'KPI':<34}{'current_state':>16}{'future_state':>16}"
    print(header)
    print("-" * len(header))

    rows = defaultdict(dict)
    for era in ("current_state", "future_state"):
        reqs = [r for r in requests if r["era"] == era]
        n = len(reqs)
        k1, k2, k6, k3_hit, k3_n, rer, info, inq, stale = [], [], [], 0, 0, 0, 0, 0, 0
        for r in reqs:
            evs = by_req[r["request_id"]]
            routes = [e for e in evs if e["event_type"] in ("routed", "rerouted") and e["to_value"] == r["current_team_id"]]
            if routes:
                k1.append(bh_between(r["submitted_at"], routes[0]["occurred_at"]))
            if r["resolved_at"]:
                k2.append(bh_between(r["submitted_at"], r["resolved_at"]) / BH_PER_DAY)
                if r["sla_due_at"]:
                    k3_n += 1
                    k3_hit += r["resolved_at"] <= r["sla_due_at"]
            rer += any(e["event_type"] == "rerouted" for e in evs)
            info += any(e["event_type"] == "info_requested" for e in evs)
            inq += sum(e["event_type"] == "status_inquiry" for e in evs)
            if r["status"] in open_status:
                last = max(e["occurred_at"] for e in evs if e["event_type"] in ("status_changed", "created"))
                stale += bh_between(last, AS_OF) >= 3 * BH_PER_DAY
            for a in appr_by_req[r["request_id"]]:
                if a["decided_at"]:
                    k6.append(bh_between(a["requested_at"], a["decided_at"]) / BH_PER_DAY)
        rows["Requests"][era] = f"{n:,}"
        rows["K1 time to assignment (median bh)"][era] = f"{statistics.median(k1):.1f}"
        rows["K2 resolution (median bus. days)"][era] = f"{statistics.median(k2):.1f}"
        rows["K3 SLA attainment"][era] = f"{k3_hit / k3_n:.0%}" if k3_n else "no SLAs"
        rows["K4 misroute rate"][era] = f"{rer / n:.1%}"
        rows["K5 missing-information rate"][era] = f"{info / n:.1%}"
        rows["K6 approval cycle (median days)"][era] = f"{statistics.median(k6):.1f}"
        rows["K7 status inquiries per request"][era] = f"{inq / n:.2f}"
        rows["K8 stale open requests (snapshot)"][era] = f"{stale}"
    for k, v in rows.items():
        print(f"{k:<34}{v.get('current_state', ''):>16}{v.get('future_state', ''):>16}")

    bands = Counter(d["band"] for d in decisions)
    total = sum(bands.values())
    nonsens = Counter(d["band"] for d in decisions if d["rule_applied"] != "BR-04")
    ns_total = sum(nonsens.values())
    print("\nK10 confidence band mix (future_state, simulated):")
    print(f"  {'band':<16}{'all':>6}{'non-sensitive':>15}")
    for b in ("auto_route", "route_and_flag", "human_triage"):
        print(f"  {b:<16}{bands[b] / total:>6.0%}{nonsens[b] / ns_total:>15.0%}")
    rules = Counter(d["rule_applied"] for d in decisions)
    print("  rules applied: " + ", ".join(f"{k} {v:,}" for k, v in sorted(rules.items())))
    print(f"\nRows: employees 300, requests {len(requests):,}, ai_predictions {len(predictions):,}, "
          f"routing_decisions {len(decisions):,}, approvals {len(approvals):,}, request_events {len(events):,}")


if __name__ == "__main__":
    main()
