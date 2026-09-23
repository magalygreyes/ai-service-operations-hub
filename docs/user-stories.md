# Breezio Service Hub: User Stories

**Version:** 1.0
**Date:** 2026-09-22
**Author:** Magaly Gonzalez
**Phase:** Slice 1, Phase 2 (Requirements and future state)
**Related documents:** `requirements.md`, `stakeholders.md`, `org-chart.md`

---

## 1. How to read this document

- Stories are grouped into six epics (E1 to E6).
- Each story names a real persona from `org-chart.md`, links to the requirements
  it delivers, and has acceptance criteria in Given, When, Then form.
- Acceptance criteria become UAT test cases in Phase 6, one test per criterion.
- Priority and slice follow `requirements.md`.

## 2. Personas

| Persona | Name | Stakeholder ID |
|---|---|---|
| Employee | Any of the 300 employees | ST-08 |
| Request Coordinator | Jess Park (IT), Luis Moreno (HR), Nora Fitzgerald (Facilities), Sam Whitaker (Finance) | ST-06 |
| Team Lead | Priya Raman (IT), Aisha Bello (HR), Tomas Garza (Facilities) | ST-02, ST-03, ST-04 |
| Finance Manager | David Mensah | ST-05 |
| Approver | Any department manager | ST-07 |
| Sponsor | Renata Velez, COO | ST-01 |
| Security and Privacy Lead | Elena Petrova | ST-09 |

## 3. Story map

| Epic | Stories | Slice |
|---|---|---|
| E1 Intake | US-01, US-02, US-03 | S1, S2 |
| E2 Classification and routing | US-04, US-05, US-06, US-07, US-08 | S1 |
| E3 Approvals | US-09, US-10 | S1, S2 |
| E4 Status | US-11, US-12 | S1, S2 |
| E5 Dashboard | US-13, US-14, US-15 | S1 |
| E6 Governance and evaluation | US-16, US-17 | S1, S2 |

---

## E1. Intake

### US-01. One ID for every request

**As an** employee, **I want** a request ID the moment I submit, **so that** I
can refer to my request without resending it.

**Delivers:** FR-01, FR-02 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-01.1 | A new request | It is saved | It has an ID in the format BRZ-YYYY-NNNNN |
| AC-01.2 | Two requests saved in the same second | Both are saved | Their IDs are different |
| AC-01.3 | Any saved request | It is inspected | Requester, channel, timestamp, and description are all present |

### US-02. One front door

**As an** employee, **I want** one form for every kind of request, **so that** I
do not have to guess which team to email.

**Delivers:** FR-03, FR-05 · **Priority:** M · **Slice:** S2

| # | Given | When | Then |
|---|---|---|---|
| AC-02.1 | The request form | An employee opens it | There is no field asking them to choose a team |
| AC-02.2 | The 30-day overlap period | An employee emails a shared inbox | They receive an auto-reply with the form link |
| AC-02.3 | A submitted form | Submission completes | The employee sees their request ID on screen |

### US-03. Log a walk-up on someone's behalf

**As** Jess Park, IT coordinator, **I want** to log a walk-up request for an
employee, **so that** it is tracked like every other request.

**Delivers:** FR-04, BR-10 · **Priority:** M · **Slice:** S2

| # | Given | When | Then |
|---|---|---|---|
| AC-03.1 | A coordinator submitting on behalf of an employee | The request is saved | The requester is the employee, not the coordinator |
| AC-03.2 | The same request | It is saved | Channel shows "walk-up" or "chat" and the on-behalf flag is true |

---

## E2. Classification and routing

### US-04. AI suggests where a request belongs

**As** Jess Park, coordinator, **I want** each request classified with a
confidence score and a reason, **so that** I only read the ones that need me.

**Delivers:** FR-10, FR-11, FR-13, FR-14 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-04.1 | A new request | It is classified | Team, category, priority, confidence (0 to 1), and a one-sentence reason are stored |
| AC-04.2 | A classification | It is stored | Model name, prompt version, and timestamp are stored with it |
| AC-04.3 | The AI returns a category not in the taxonomy | Output is validated | The request goes to human triage and the failure is logged |

### US-05. Route by confidence

**As** Priya Raman, IT lead, **I want** confident predictions routed straight to
my queue and uncertain ones checked first, **so that** my team gets the right
work without waiting on triage.

**Delivers:** FR-20, BR-01, BR-02, BR-03 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-05.1 | A non-sensitive request with confidence 0.93 | Rules run | It is routed to the owning team with no review flag |
| AC-05.2 | A non-sensitive request with confidence 0.82 | Rules run | It is routed to the owning team and flagged for review |
| AC-05.3 | A request with confidence 0.61 | Rules run | It goes to the human triage queue |
| AC-05.4 | A request classified Unclassified | Rules run | It goes to the human triage queue, whatever the confidence |
| AC-05.5 | Confidence exactly 0.90, and exactly 0.70 | Rules run | 0.90 auto-routes. 0.70 routes and flags |

### US-06. Sensitive HR requests always go to HR

**As** Aisha Bello, HR Operations Manager, **I want** every sensitive request to
come to my team's triage queue, **so that** personal information is never
auto-routed.

**Delivers:** BR-04, NFR-09 · **Priority:** M · **Slice:** S1 (routing), S2 (access control)

| # | Given | When | Then |
|---|---|---|---|
| AC-06.1 | A request predicted as Payroll question with confidence 0.97 | Rules run | It goes to the HR triage queue, not auto-routed |
| AC-06.2 | The same request in the HR triage queue | Luis Moreno opens it | The AI suggestion and confidence are visible, but not applied |
| AC-06.3 | A request predicted as Policy question (not sensitive) | Rules run | Normal confidence routing applies |

### US-07. Catch missing information at intake

**As** Tomas Garza, Facilities Manager, **I want** requests missing a location
flagged before they reach my team, **so that** we never start a job we cannot find.

**Delivers:** FR-12, FR-22, BR-06 · **Priority:** M · **Slice:** S1 (status), S2 (message)

| # | Given | When | Then |
|---|---|---|---|
| AC-07.1 | A Maintenance request with no room number | It is classified | "Room" is listed as a missing field |
| AC-07.2 | A request with one or more missing fields | Rules run | Status becomes "Awaiting information" |
| AC-07.3 | A request in "Awaiting information" | Time passes | The SLA clock does not advance |
| AC-07.4 | A request with no missing fields | Rules run | It is not moved to "Awaiting information" |

### US-08. Correct a misroute in one step

**As** Nora Fitzgerald, Facilities coordinator, **I want** to send a misrouted
request to the right team in one step, **so that** it is not forwarded around by email.

**Delivers:** FR-21, FR-24 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-08.1 | A request in the Facilities queue that belongs to IT | The coordinator changes the team | It appears in the IT queue |
| AC-08.2 | The same change | It is saved | A reroute event is logged with old team, new team, who, and when |
| AC-08.3 | Reroute events exist | K4 is calculated | Each rerouted request counts once, however many times it moved |

---

## E3. Approvals

### US-09. Manager approval before work starts

**As** a department manager, **I want** approval requests in one place with one
click to decide, **so that** I do not have to search my inbox.

**Delivers:** FR-30, FR-32, FR-33, FR-34 · **Priority:** M · **Slice:** S1 (data), S2 (workflow)

| # | Given | When | Then |
|---|---|---|---|
| AC-09.1 | A request in a category that needs approval | It is triaged | Status becomes "Awaiting approval" and work cannot start |
| AC-09.2 | A pending approval | The manager approves or rejects | Approver, decision, timestamp, and comment are stored |
| AC-09.3 | A pending approval with no decision after 1 business day | The reminder job runs | The manager receives one reminder |

### US-10. Finance approval above the threshold

**As** David Mensah, Finance Manager, **I want** purchases above $2,500 to come
to me after the manager approves, **so that** the spend policy is applied every time.

**Delivers:** FR-31, BR-05 · **Priority:** M · **Slice:** S1 (data), S2 (workflow)

| # | Given | When | Then |
|---|---|---|---|
| AC-10.1 | A purchase request for $2,501 approved by the manager | The approval is saved | A Finance approval step is created |
| AC-10.2 | A purchase request for exactly $2,500 | The manager approves | No Finance step is created |
| AC-10.3 | A request rejected by the manager | The rejection is saved | No Finance step is created and status becomes Rejected |

---

## E4. Status

### US-11. One status lifecycle

**As** Renata Velez, COO, **I want** every team to use the same statuses, **so
that** "open", "late", and "resolved" mean the same thing everywhere.

**Delivers:** FR-40, BR-09 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-11.1 | Any request | Its status changes | The change is logged with old status, new status, and timestamp |
| AC-11.2 | A status value outside the lifecycle | A save is attempted | The save is rejected |
| AC-11.3 | A request Resolved for 5 business days with no reopen | The close job runs | Status becomes Closed |

### US-12. Check status without asking

**As** an employee, **I want** to look up my request by ID, **so that** I never
have to email "any update?"

**Delivers:** FR-41, FR-42 · **Priority:** S · **Slice:** S2

| # | Given | When | Then |
|---|---|---|---|
| AC-12.1 | A valid request ID | The employee looks it up | Current status, owning team, and SLA due date are shown |
| AC-12.2 | A status change | It is saved | The requester is notified |

---

## E5. Dashboard

### US-13. See service health at a glance

**As** Renata Velez, COO, **I want** the KPIs on one screen with traffic-light
status, **so that** I stop waiting for a month-end count.

**Delivers:** FR-50, FR-51, FR-55, NFR-03, NFR-08 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-13.1 | The dashboard | It loads | Tiles for K1 to K8 show a value, a red, yellow, or green status, and a text label |
| AC-13.2 | A filter for team = HR | It is applied | Every tile and chart reflects HR only |
| AC-13.3 | Any KPI tile | Its value is compared with its SQL view | The values match exactly |

### US-14. Watch the AI, not just the work

**As** Elena Petrova, Security and Privacy Lead, **I want** to see how many
requests the AI routes alone versus with review, **so that** I know how much the
model is trusted in practice.

**Delivers:** FR-52 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-14.1 | The dashboard | It loads | The share of requests in each confidence band is shown |
| AC-14.2 | The same view | It loads | Sensitive-rule overrides are counted separately from low-confidence triage |

### US-15. Find what is late or stuck

**As** Priya Raman, IT lead, **I want** a list of breached, at-risk, and stale
requests, **so that** my team works the right things first.

**Delivers:** FR-53, FR-54, FR-56, FR-57 · **Priority:** M · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-15.1 | Open requests past their SLA due time | The list loads | They appear as breached (red) |
| AC-15.2 | Open requests with less than 25% of SLA time left | The list loads | They appear as at risk (yellow) |
| AC-15.3 | Open requests with no status change in 3+ business days | The stale list loads | They appear, and the count matches K8 |
| AC-15.4 | Any filtered list | Download is clicked | A CSV of exactly the rows shown is downloaded |

---

## E6. Governance and evaluation

### US-16. Change the taxonomy safely

**As** Renata Velez, COO, **I want** category changes versioned and approved,
**so that** the AI and the dashboard never disagree on what a category means.

**Delivers:** FR-60, NFR-10 · **Priority:** S · **Slice:** S1

| # | Given | When | Then |
|---|---|---|---|
| AC-16.1 | An approved category change | It is applied | The taxonomy version increases and the change is logged |
| AC-16.2 | Any past request | It is viewed | It shows the taxonomy version it was classified under |

### US-17. Prove the AI's accuracy before trusting it

**As** Elena Petrova, Security and Privacy Lead, **I want** accuracy measured on
a held-out labeled set, **so that** auto-routing is based on evidence.

**Delivers:** FR-70, FR-71, FR-72 · **Priority:** M · **Slice:** S2

| # | Given | When | Then |
|---|---|---|---|
| AC-17.1 | About 150 requests labeled by coordinators | Prompt design happens | None of those requests are used |
| AC-17.2 | The evaluation run | It completes | Per-category precision and recall, macro F1, and a confusion matrix are published |
| AC-17.3 | K9 not yet met | Rules run | No request is auto-routed without a review flag |
