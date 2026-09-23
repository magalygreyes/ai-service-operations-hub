# Breezio Service Hub: Requirements

**Version:** 1.0
**Date:** 2026-09-22
**Author:** Magaly Gonzalez
**Phase:** Slice 1, Phase 2 (Requirements and future state)
**Status:** Approved by sponsor (ST-01)
**Related documents:** `discovery.md`, `stakeholders.md`, `process-maps.md`, `user-stories.md`

---

## 1. Purpose

This document states what the Service Hub must do, the rules it must apply, and
the quality bar it must meet. Every requirement traces back to a business
objective (BO), a KPI (K), or a pain point (PP) from Phase 1, and forward to user
stories in `user-stories.md`.

## 2. How to read this document

- **Priority** uses MoSCoW: **M** must have, **S** should have, **C** could have.
- **Slice** says when the requirement is delivered: **S1** (this slice), **S2**
  (webhook, n8n, approvals, accuracy evaluation), or **S3** (RAG, AI summary,
  escalation).
- **Traces to** links each requirement to Phase 1 IDs.
- Decisions D6 to D12 are recorded in `stakeholders.md` §7.

---

## 3. Reference data: categories and service levels

Taxonomy v1.0 replaces the v0.1 draft in `discovery.md` §7. Renata Velez (COO)
owns the list. Team leads request changes and every change gets a new version
(D7). Each team lead proposed the service-level targets (SLAs) for their own
categories (D10).

SLAs are in business days, counted Monday to Friday, 8:00 to 17:00.

| ID | Team | Category | Required fields | Approval | Sensitive | SLA |
|---|---|---|---|---|---|---|
| CAT-IT-01 | IT | Access request | System, access level, business reason | Manager | No | 2 days |
| CAT-IT-02 | IT | Hardware request | Item, business reason, cost center | Manager | No | 5 days |
| CAT-IT-03 | IT | Software request | Software name, number of licenses, cost center | Manager, plus Finance above $2,500 | No | 3 days |
| CAT-IT-04 | IT | Password or account lockout | System or account | None | No | 0.5 day |
| CAT-IT-05 | IT | Something is broken (incident) | System or device, who is affected, asset tag if a device | None | No | 1 day |
| CAT-IT-06 | IT | How-to question | System | None | No | 2 days |
| CAT-HR-01 | HR | Benefits question | Topic | None | Yes | 3 days |
| CAT-HR-02 | HR | Payroll question | Pay period | None | Yes | 2 days |
| CAT-HR-03 | HR | Leave request | Leave type, start date, end date | Manager | Yes | 2 days |
| CAT-HR-04 | HR | Onboarding or offboarding | Employee name, role, start or end date, manager | None | Yes | 5 days, and before the start or end date |
| CAT-HR-05 | HR | Employment letter | Letter type, recipient | None | Yes | 3 days |
| CAT-HR-06 | HR | Policy question | Topic | None | No | 3 days |
| CAT-FAC-01 | Facilities | Maintenance or repair | Building, floor, room, description | None | No | 2 days |
| CAT-FAC-02 | Facilities | Workspace or move | Current location, requested location, move date | Manager | No | 10 days |
| CAT-FAC-03 | Facilities | Badge or building access | Building, access area, start date | Manager | No | 2 days |
| CAT-FIN-01 | Finance | Expense reimbursement | Amount, expense date, receipt, cost center | Manager | No | 5 days |
| CAT-FIN-02 | Finance | Purchase request | Item or service, vendor, amount, cost center | Manager, plus Finance above $2,500 | No | 5 days |
| CAT-FIN-03 | Finance | Vendor or invoice question | Vendor name, invoice number | None | No | 3 days |
| CAT-GEN-00 | None | Unclassified | Not applicable | Not applicable | Not applicable | Set at triage |

SLA proposals came from Priya Raman (IT), Aisha Bello (HR), Tomas Garza
(Facilities), and David Mensah (Finance). Renata Velez approved them as sponsor.

---

## 4. Business rules

The rules layer runs after the AI and always wins. Rules live in one
configuration table, not in code (NFR-10).

| ID | Rule | Source |
|---|---|---|
| BR-01 | Confidence of 0.90 or higher: auto-route to the category's owning team | D3 |
| BR-02 | Confidence from 0.70 to 0.89: route to the owning team and flag for coordinator review | D3 |
| BR-03 | Confidence below 0.70, or category Unclassified: send to the human triage queue | D3 |
| BR-04 | Any sensitive category (Sensitive = Yes in §3) goes to the HR triage queue, whatever the confidence. The AI suggestion is shown, never applied | D6 |
| BR-05 | Software and purchase requests above $2,500 need Finance Manager approval after the manager approves | D9 |
| BR-06 | The SLA clock pauses in "Awaiting information" and "Awaiting approval", and restarts when the request moves on | K2, K3 |
| BR-07 | High priority (the requester cannot work, or there is a safety issue) has an SLA of 1 business day or the category SLA, whichever is shorter | K3 |
| BR-08 | Onboarding and offboarding are owned by HR. HR creates a linked task for IT equipment and access | SR-06 |
| BR-09 | A resolved request closes automatically after 5 business days if the requester does not reopen it | K8 |
| BR-10 | Chat messages and walk-ups are logged by a coordinator through the form, on behalf of the employee, with the channel recorded | D12 |

---

## 5. Functional requirements

### 5.1 Intake

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-01 | Every request receives a unique ID at creation, in the format BRZ-YYYY-NNNNN | M | S1 | BO-01, PP-04, K8 |
| FR-02 | Each request stores requester, channel (form, email, chat, walk-up), submitted-on-behalf flag, timestamp, description, and attachment flag | M | S1 | BO-01, PP-01 |
| FR-03 | A single web form is the front door for every request, with no need to pick a team | M | S2 | BO-01, BO-02, PP-01, PP-02 |
| FR-04 | Coordinators can submit a request on behalf of an employee (BR-10) | M | S2 | PP-09, D12 |
| FR-05 | During a 30-day overlap, the four shared inboxes auto-reply with the form link. After the overlap, they only auto-reply | S | S2 | PP-01, D8 |

### 5.2 AI classification

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-10 | The AI predicts team, category (from the closed list in §3), and priority, with a confidence score from 0 to 1 | M | S1 | BO-02, BO-06, K4, K10 |
| FR-11 | The AI returns a one-sentence reason for its category choice | S | S1 | BO-06 |
| FR-12 | The AI lists which required fields for the predicted category are missing from the description | M | S1 | BO-03, PP-03, K5 |
| FR-13 | Every prediction is stored with model name, prompt version, and timestamp | M | S1 | BO-06, NFR-04 |
| FR-14 | Output that fails schema validation sends the request to human triage and logs the failure | M | S1 | BO-06 |

### 5.3 Routing and rules

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-20 | Routing applies BR-01 to BR-04 to every request | M | S1 | BO-02, BO-06, K1, K4, K10 |
| FR-21 | The human triage queue shows the AI suggestion, confidence, and reason, so a coordinator can accept or change it in one step | M | S1 | BO-06, SR-02 |
| FR-22 | A request with missing required fields moves to "Awaiting information" and the requester is asked for exactly the missing fields | M | S1 status, S2 message | BO-03, K5 |
| FR-23 | Each request gets an SLA due time from its category and priority (BR-06, BR-07) | M | S1 | BO-05, PP-08, K2, K3 |
| FR-24 | Moving a request to a different team logs a reroute event | M | S1 | K4 |

### 5.4 Approvals

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-30 | Categories that need approval wait for manager approval before work starts | M | S1 data, S2 workflow | BO-05, PP-05, K6 |
| FR-31 | BR-05 applies Finance approval above $2,500, in sequence after the manager | M | S1 data, S2 workflow | PP-05, D9 |
| FR-32 | Each decision is recorded with approver, decision, timestamp, and comment | M | S1 | PP-05, NFR-04 |
| FR-33 | Approvers get a notification with one-click approve or reject | M | S2 | K6, SR-05 |
| FR-34 | An approval with no decision after 1 business day sends a reminder | S | S2 | K6, SR-05 |
| FR-35 | An approval with no decision after 3 business days escalates to the approver's leader | C | S3 | K6 |

### 5.5 Status

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-40 | Status follows one lifecycle: New, Triaged, Awaiting information, Awaiting approval, In progress, Resolved, Closed, or Rejected. Every change is logged with a timestamp | M | S1 | BO-04, PP-07, K2, K8 |
| FR-41 | Requesters can look up status by request ID without contacting anyone | S | S2 | BO-04, PP-06, K7 |
| FR-42 | Requesters are notified when status changes | S | S2 | BO-04, K7 |

### 5.6 Dashboard

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-50 | KPI tiles for K1 to K8, each with a red, yellow, or green status and a text label | M | S1 | BO-07, K1 to K8 |
| FR-51 | Volume by team, category, channel, and week | M | S1 | BO-07, PP-10 |
| FR-52 | Confidence band mix (K10) and human triage queue size | M | S1 | BO-06, K10 |
| FR-53 | SLA attainment by team and category, with a list of breached and at-risk requests | M | S1 | BO-05, K3 |
| FR-54 | List of stale open requests (K8) | M | S1 | BO-04, K8 |
| FR-55 | Filters for date range, team, category, channel, priority, and confidence band. Filters apply to every view | M | S1 | BO-07 |
| FR-56 | Approval cycle time by approver (K6) | S | S1 | K6, SR-05 |
| FR-57 | Download any filtered table as CSV | S | S1 | BO-07 |
| FR-58 | Side-by-side view of modeled current-state baselines and future-state results | C | S1 | BO-07 |

### 5.7 Governance and evaluation

| ID | Requirement | Priority | Slice | Traces to |
|---|---|---|---|---|
| FR-60 | The taxonomy is a versioned reference table. Changes need sponsor approval and are logged (D7) | S | S1 | SR-06, D7 |
| FR-70 | About 150 requests are hand-labeled by the coordinators and held out from prompt design | M | S2 | BO-06, K9 |
| FR-71 | Per-category precision and recall, macro F1, and a confusion matrix are published in the repo | M | S2 | BO-06, K9 |
| FR-72 | The auto-route band (BR-01) is only switched on after K9 is met. Until then, every request is at least flagged for review | M | S2 | BO-06, SR-04 |

---

## 6. Non-functional requirements

| ID | Category | Requirement | Priority | Traces to |
|---|---|---|---|---|
| NFR-01 | Privacy | Slice 1 uses synthetic data only. No real names, emails, or request text | M | C-01 |
| NFR-02 | Privacy | No real request text goes to an external AI service until the Security and Privacy Lead approves the provider and its data terms | M | D11, SR-03 |
| NFR-03 | Consistency | Every KPI is defined once, as a SQL view. The dashboard reads only from those views | M | BO-07 |
| NFR-04 | Auditability | AI predictions, rule overrides, reroutes, status changes, and approvals are written to an append-only event log | M | BO-06, PP-05 |
| NFR-05 | Explainability | Confidence and reason are visible to coordinators for every AI-routed request | M | BO-06, SR-02 |
| NFR-06 | Performance | Classification finishes within 10 seconds per request. The dashboard loads within 5 seconds with 12 months of data (about 7,200 requests) | S | BO-07 |
| NFR-07 | Cost | Runs on free tiers. AI cost per request is tracked and reported | S | C-02 |
| NFR-08 | Accessibility | Status is never shown by color alone. Every red, yellow, or green status also has a text label | S | BO-07 |
| NFR-09 | Access control | Sensitive HR requests are visible only to the HR team | M | D6, PP-11, Slice 2 |
| NFR-10 | Maintainability | Thresholds, rules, categories, and SLAs live in configuration tables, not in code | M | D7, D10 |
| NFR-11 | Reproducibility | The synthetic data generator uses a fixed seed, so a rerun produces identical data | M | C-04 |

---

## 7. Out of scope

Unchanged from `discovery.md` §6: Power Automate, full IT service management
replacement, real employee data, and authentication in Slice 1.

## 8. Open items

| # | Item | Owner | Needed by |
|---|---|---|---|
| OI-01 | Confirm the approval chain when the requester's manager is out of office | David Mensah with Renata Velez | Slice 2 |
| OI-02 | Confirm whether High priority can be set by the requester or only by triage | Priya Raman | Phase 4 |
