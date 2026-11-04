# Decisions

Who decided: **M** = Mukesh, **DGM** = the DGM (through Mukesh), **C** = Claude's pick when Mukesh asked for it. Dates are 2026.

Change a decision only by editing this file with a new date and the reason, after Mukesh agrees. Code never changes a decision on its own.

## Platform and delivery

| # | Decision | By | Date |
|---|---|---|---|
| D-01 | Android app for phones, web for Mukesh, the manager and the maintenance-store PC. No iOS. | M, DGM | 31 Oct |
| D-02 | The Android app is built in **Flutter**. | M (C's pick) | 4 Nov |
| D-03 | Backend in **Flask, like ICON TRACE**: Waitress on Windows Server, Jinja2 web screens, per-screen permissions. | M | 4 Nov |
| D-04 | Database **MySQL 8** (not SQLite: many phones write at once and a worker runs timers). MySQL matches ICON TRACE's planned production database. Switch to PostgreSQL only if Mukesh says so before stage 2. | C | 4 Nov |
| D-05 | Phase 1 runs on the **LAN only**. Phase 2 goes to the internet later, **hosted locally (on-prem), never in the cloud**. | M | 4 Nov |
| D-06 | Avirat runs on its **own host**; ICON TRACE stays off the internet. | M | 31 Oct |
| D-07 | **Production first, Play Store later.** Be ready for a hold like ICON TRACE's. | M | 4 Nov |
| D-08 | The company owns the app's domain and the Play developer account. | DGM | 31 Oct |
| D-09 | The product name is **Avirat** (Hindi अविरत, Bangla অবিরত: "uninterrupted"). No "ICON" in the product name. | C, asked by M | 4 Nov |
| D-10 | Languages: **English, Hindi and Bangla** (Bangla last priority). | M | 4 Nov |

## People and login

| # | Decision | By | Date |
|---|---|---|---|
| D-11 | **Every line operator gets their own account**, for tracking and accountability. | M | 4 Nov |
| D-12 | Account **lockout** and **device binding** at login. | M | 31 Oct |
| D-13 | Both line operators and shift incharges raise tickets. | M | 31 Oct |
| D-14 | The manager creates groups, incharges and all settings in the UI, with a per-screen permission table like ICON TRACE's. | M | 1 Nov |

## Groups, schedule and routing

| # | Decision | By | Date |
|---|---|---|---|
| D-15 | Maintenance groups: Automation, Utility, IT, Others (the manager can add more). The raiser picks the group. | M | 31 Oct |
| D-16 | **One incharge per group per shift.** | M | 1 Nov |
| D-17 | An uploaded schedule **stays valid until the next one** is uploaded. | M | 1 Nov |
| D-18 | For daily attendance, the incharge marks **only who is absent**. | M | 3 Nov |
| D-19 | Tickets go to the group's on-duty incharge. With no incharge on duty, the manager gets them. The manager never accepts a ticket; he assigns an incharge or technicians. | M | 31 Oct, 1 Nov |
| D-20 | The incharge assigns one or more people, with or without himself. **Lead = the incharge if he includes himself, else the first person assigned. Only the lead accepts.** | M | 1 Nov |
| D-21 | A helper can ask to opt out with a reason; the incharge or the lead approves; the incharge replaces him. | M | 1 Nov |

## Kinds of ticket

| # | Decision | By | Date |
|---|---|---|---|
| D-22 | Tickets cover breakdowns **and jobs** (installs such as a switchboard or fan, automation work); the IT department is included. | M | 1 Nov |
| D-23 | Jobs need **no manager OK**; the group incharge decides. | M | 3 Nov |

## Timers (values from the DGM; editable in settings)

| # | Decision | By | Date |
|---|---|---|---|
| D-24 | Not assigned within **10 min** → the manager is alerted. | DGM | 3 Nov |
| D-25 | Lead hasn't accepted within **5 min** → the incharge picks a new lead. | DGM | 3 Nov |
| D-26 | **No "no update" reminders** while work is in progress: they would make technicians use the app instead of fixing the machine. | M | 3 Nov |
| D-27 | Machine stopped for **4 h** → the manager gets **one** alert. | M | 3 Nov |
| D-28 | **Observation of 2 h** after claim resolved: the raiser can't close during it, and can after it. The 2 h are **inside** the 4 h auto close. | DGM | 3 Nov |
| D-29 | No answer **4 h** after claim resolved → **auto close**. | M | 31 Oct |

## Work, help and handover

| # | Decision | By | Date |
|---|---|---|---|
| D-30 | Diagnosis is physical. Parts can be requested **any time from accept until claim resolved**. The ticket shows "waiting for material" until the store issues. | M | 31 Oct |
| D-31 | A technician who can't fix it taps **Need help**; the incharge adds or changes people, or hands it to another group. | M | 1 Nov |
| D-32 | The raiser can **Escalate** any time before claim resolved: to the group incharge; a 2nd escalation goes to the manager. No limit on how often. | M | 3 Nov |
| D-33 | Vendor waits and machine-release waits happen. **No hold state, no waiting tag**: the clocks keep counting. | M | 3 Nov |
| D-34 | Handover in two cases: wrong group (to the right group), and shift end (raiser or maintenance to another person). **The receiver must accept.** | M | 31 Oct |

## Claim and close

| # | Decision | By | Date |
|---|---|---|---|
| D-35 | Only the lead claims resolved. **Downtime ends at claim resolved.** | M | 31 Oct, 1 Nov |
| D-36 | The lead **writes the cause in his own words**; no predefined list at first. A cause list is built later from what they write. It counts for KPI. | M | 3 Nov |
| D-37 | The raiser, or whoever it was handed over to, confirms. Not working → reopen back to the lead. | M | 31 Oct |
| D-38 | Reopen ladder: **2nd reopen → incharge reviews; 3rd → manager decides.** | M | 1 Nov |
| D-39 | The gap between a claim and a reopen **counts as downtime**. | M | 31 Oct |

## Store

| # | Decision | By | Date |
|---|---|---|---|
| D-40 | The ERP's store module holds the raw-material store only. **The maintenance store runs fully in Avirat.** | M | 4 Nov |
| D-41 | Stock drops when the store issues a part. | M | 31 Oct |
| D-42 | **The manager approves returns before stock goes back up** (DGM's rule, confirmed). | DGM | 31 Oct, 3 Nov |
| D-43 | No part-value threshold for approvals. | M | 31 Oct |

## KPI

| # | Decision | By | Date |
|---|---|---|---|
| D-44 | KPIs reproduce the KPI Excel's formulas: MTTR, MTBF, DWT %, TDH %, downtime factors, budget status and ₹/W. | M | 4 Nov |
| D-45 | Headline: **line downtime %** (the Excel's TDH %), shown with line availability. DWT % stays for continuity, with its bands. | C, asked by M | 4 Nov |
| D-46 | Working minutes use the **real month**, not a fixed 41,400. | M | 4 Nov |
| D-47 | Every stringer has **lanes A and B with separate QR codes**; one bussing per stringer. | M | 4 Nov |
| D-48 | Import the Aug–Sep Excel history; back-fill older breakdowns. | M | 4 Nov |

---

## Defaults (proposed, not objected to)

These were shown as proposals on the diagram pages and in chat, and Mukesh went ahead without striking them. Build them as described; any of them can still change.

**Tickets**
- Three kinds: Stopped, Running with a fault, Job; the raiser picks the kind with one tap.
- Duplicate check: if the machine already has an open ticket, the app shows it and the raiser joins it instead of raising another.
- The machine's default group is pre-selected where it is obvious (a compressor is Utility); the raiser can change it.
- An optional short note from the raiser (never required).
- Only on-duty people get ticket alerts. A person marked absent gets no tickets or alerts.
- Nobody from the group on duty → the manager is alerted at once.
- The incharge (or manager) can cancel a duplicate or a mistake, with a reason, only before any work or parts.
- Two tickets for the same stoppage: the incharge merges them; the earliest stop time is kept.
- Wrong machine picked: the incharge or technician corrects it; the change is logged.
- A second fault found during work gets its own linked ticket.
- A running fault that stops: the raiser taps "Now stopped"; downtime starts then.
- A job that turns out urgent: the incharge makes it a breakdown; timers start.
- A job past its target date: the incharge is alerted, then the manager.
- Person off duty: the incharge is warned but can still add them, with a reason.
- Lead leaves mid-job: passes the lead to a teammate, who accepts.
- Anyone on the team can request parts; only the lead claims.
- Shift ends with no handover: the ticket stays with them and the incoming incharge reassigns.
- Handed between groups twice: the manager picks the group.
- At claim: cause suggestions from earlier causes on the same machine; the phone's voice typing works.
- "Temporary fix" tick at claim: downtime stops and a follow-up ticket opens for the real repair.
- No parts form at claim: anything issued and not returned counts as used.
- The raiser **can reopen during the 2 h observation**; only closing waits.
- **Jobs skip the observation**: a job can be confirmed straight away.
- Reopen needs a one-tap reason: not working, partly working, or different problem. "Different problem" opens a new linked ticket instead of a reopen.
- Raiser gone and no handover: any production incharge can confirm.
- Auto-closed tickets are shown as unconfirmed, apart from confirmed closes.
- Confirmed by mistake: closed stays closed; a new ticket is raised and flagged as a repeat.
- Someone leaves the company: account blocked; their open tickets go to the incharge.
- The alerts listed in `docs/specs/tickets.md` §12.

**Store and KPI** (from the inventory and KPI page)
- Stock on hand is worked out from movements and never typed.
- Every receipt is its own entry; new parts get the next Icon Code and appear in the manager's daily list.
- Average price from receipts; $ prices converted at the manager's monthly rate.
- Returns are held on the shelf until the manager approves the day's list.
- Exchange items need the old part back.
- Stock counts a few bins at a time; every difference is a manager-approved adjustment.
- Downtime minutes are split by day, shift and month; a breakdown counts once, on its start day.
- A month-end snapshot replaces the Excel's save macro.

---

## Open questions

| # | Question | Needed before | Recommendation |
|---|---|---|---|
| O-1 | **Alerts on the LAN.** FCM needs the phone to have internet and the server to reach FCM. Can the phones' Wi-Fi give internet (plus the Avirat server), and can the server make outbound HTTPS calls to FCM only? | Stage 3 | Yes to both. Fallback: the app keeps its own connection to the server while open, which is weaker on battery and on some phone brands. |
| O-2 | **Android application ID.** Permanent once phones install it. | First APK (stage 4) | Reverse of the company's own domain + `.avirat`, for example `in.iconsolar.avirat` |
| O-3 | **Shift times** for A, B and C. | Stage 3 tests | Fill `docs/templates/shifts.csv` |
| O-4 | **Unit-2 machine list**: lines, machine types, numbers, stringer lanes, bussing per stringer. Mukesh is sending it. | QR printing (stage 5) | Fill `docs/templates/machines.csv` |
| O-5 | **Both lanes stopped.** Raise on one lane with a "both lanes" toggle, which puts the ticket on the whole stringer? | Stage 3 | Yes, one tap only on stringer lanes |
| O-6 | **Lane factor.** One lane stopped: the full stringer factor (0.333, as the Excel does) or half? 105 of 166 stringer rows in Aug–Sep were one lane only. | Stage 8 | Half, so both lanes down equals one full stringer |
| O-7 | **Bussing factor.** The Excel uses 0.9, but one bussing serves one stringer (0.333). | Stage 8 | Check against the machine list |
| O-8 | **Price for valuing issues**: average price of stock in hand, or last purchase price? | Stage 7 | Average |
