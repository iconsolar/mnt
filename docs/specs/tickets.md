# Tickets

The ticket flow from raise to close. Diagrams: `docs/flows/ticket-flows.html` (Flow 2). Decisions are cited as D-xx (`DECISIONS.md`); "default" means a proposal Mukesh did not object to.

Target: a normal breakdown takes **about ten taps in total, plus the cause the lead writes**. Helpers tap nothing. Everything else is automatic or appears only when needed.

## 1. Who does what

| Person | In the ticket flow |
|---|---|
| **Raiser** | Line operator or shift (production) incharge (D-13). Raises, escalates, confirms or reopens. |
| **Group incharge** | The one on-duty incharge of a maintenance group for this shift (D-16). Assigns, handles help, opt-outs, handovers, reviews the 2nd reopen. |
| **Lead** | The incharge if he put himself on the ticket, else the first person assigned (D-20). Accepts and claims. |
| **Helper** | Other assigned technicians. Can request parts and ask to opt out. Otherwise taps nothing. |
| **Manager** | Gets tickets when no incharge is on duty; never accepts one (D-19). Gets the 10-min, 2nd-escalation, 3rd-reopen and 4-h alerts. |
| **Store** | Issues parts against a part request. (The store's own flow is `inventory.md`.) |
| **App** | Routes, runs timers, sends alerts, counts downtime. |

"Incharge" alone always means the group incharge. "Production incharge" means the shift incharge on the production side.

## 2. Kinds (default)

| Kind | Downtime | Timers | Observation |
|---|---|---|---|
| **Stopped** | Runs from the declared stop time | All | Yes |
| **Running with a fault** | None, until someone taps "Now stopped" | All | Yes |
| **Job**: installs, changes, IT work (D-22) | Never | None; the incharge sets a target date (D-23) | Skipped (default) |

## 3. States and transitions

| From | To | Action | Who |
|---|---|---|---|
| — | `raised` | Raise | Raiser |
| `raised` | `assigned` | Assign people (lead picked by rule) | Group incharge, or the manager when no incharge is on duty |
| `raised` | `raised` (new group) | Group handover, after the receiving incharge accepts | Group incharge |
| `raised`, `assigned` | `cancelled` | Cancel with a reason, only before any accept or part request (default) | Group incharge, manager |
| `raised`, `assigned` | `cancelled` | Merge into another open ticket (default) | Group incharge |
| `assigned` | `in_progress` | Accept | Lead only |
| `assigned` | `assigned` | Lead changed after the 5-min timeout | Group incharge |
| `in_progress` | `assigned` | Lead leaves mid-job and passes the lead; the new lead accepts (default) | Lead |
| `in_progress` | `in_progress` | Parts, help, escalation, team changes, shift handover, notes | See §7–§8 |
| `in_progress`, `assigned` | `raised` (new group) | Group handover, after the receiving incharge accepts | Group incharge |
| `in_progress` | `claimed` | Claim resolved, with the cause | Lead only |
| `claimed` | `closed` (`confirmed`) | Working: close (after observation) | Raiser, the confirm handover person, or any production incharge if the raiser is gone (default) |
| `claimed` | `closed` (`auto`) | 4 h after the claim with no answer | App |
| `claimed` | `assigned` | 1st reopen: back to the same lead to accept | Raiser |
| `claimed` | `review` | 2nd reopen | Raiser |
| `claimed` | `manager_decision` | 3rd and later reopens | Raiser |
| `review` | `assigned` | Keep, add or change people | Group incharge |
| `manager_decision` | `assigned` | Carry on, or change people | Manager |
| `manager_decision` | `closed` (`manager`) | Close as not fixed, with a reason and a follow-up ticket | Manager |

Nothing leaves `closed` or `cancelled`. A problem after close is a new ticket (§16).

## 4. Raise

Screen: scan the QR **or** choose the machine or place → open-ticket check → kind → group → Raise.

| Field | Rule |
|---|---|
| Machine or place | QR scan (`/m/<qr_token>`) or a search list. A new install picks a place (default). |
| Both lanes | On a stringer lane, a "both lanes stopped" toggle puts the ticket on the whole stringer (open question O-5). |
| Open-ticket check | If the machine (or its parent stringer) already has an open ticket, show it; the raiser joins it instead of raising (default). |
| Kind | One tap: Stopped, Running with a fault, Job. |
| Group | Pre-selected from the machine's default group where obvious; the raiser can change it (D-15). |
| Stop time | Stopped only. Defaults to now; can be set earlier. |
| Note | Optional, short, any language (default). Never required. |
| Late entry | Raised after the repair, from the web back-fill (stage 5): stop and claim times typed in; marked as a late entry (D-48). |

The phone gives the ticket a UUID, so a raise made without signal is sent later without duplicates (`PROJECT_OVERVIEW.md` §8). The server gives the number `T-YYMM-NNNN` on arrival.

## 5. Routing

1. Find the group's **on-duty incharge** for the current shift: latest schedule for the group, minus today's absences (`DATA_LAYER.md` §3).
2. Found → alert him. Not found → the ticket goes to the **manager** (D-19).
3. Nobody from the group on duty at all → the manager is alerted at once (default).
4. Start the **assign timer: 10 min** (D-24). Jobs: no timer.

## 6. Assign and accept

- The incharge picks one or more people, with or without himself (D-20). The app shows the lead as it will be: himself if he is on the ticket, otherwise the first person picked.
- Assigning someone off duty or marked absent shows a warning; the incharge can still add them, with a reason (default).
- The **accept timer: 5 min** starts (D-25). Only the lead accepts. On timeout the incharge is alerted to pick a new lead; the timer restarts for the new lead.
- The manager assigns either an incharge (who then assigns people) or technicians directly. He never accepts.

## 7. Team changes

| Case | Flow |
|---|---|
| Helper wants out | Asks with a reason → incharge or lead approves → the incharge replaces him if needed (D-21). |
| More hands needed | Through Need help (§8), or the incharge adds people. |
| Lead leaves mid-job | Passes the lead to a teammate, who accepts (default). |
| Someone leaves the company | Account blocked; their open tickets go to the incharge (default). |

## 8. During the work

| Action | Who | Rule |
|---|---|---|
| **Request parts** | Anyone on the team (default) | Any time from accept until claim (D-30): pick the part (Icon Code, search or photo) and quantity. While a request is open the ticket shows "waiting for material" (derived). The store marks it issued. |
| **Need help** | Lead or helper | Picks why: more hands, another skill, parts, vendor, machine stop, other. The incharge adds or changes people, hands over to another group, or gets parts (D-31). |
| **Escalate** | Raiser | Any time before claim; one tap and a reason: too slow, nobody here, not fixing it. 1st → group incharge; 2nd and later → manager. No limit. Doesn't change who owns the ticket (D-32). |
| **Group handover** | Group incharge | To another group; the receiving incharge must accept (D-34). After acceptance the ticket is `raised` in the new group and the 10-min assign timer restarts. Handed between groups twice → the manager picks the group (default). |
| **Shift handover** | Lead (maintenance side) or raiser (confirm side) | To a named person, who must accept (D-34). Shift ends with no handover: the ticket stays with them and the incoming incharge reassigns (default). |
| **Now stopped** | Raiser | A running fault that stops: kind becomes Stopped; downtime starts at that time (default). |
| **Make it a breakdown** | Group incharge | A job that turns out urgent: kind changes; timers start (default). |
| **Correct the machine** | Group incharge or technician | Logged as an event (default). |
| **Second fault found** | Lead | A new linked ticket with its own clocks (default). |
| **Vendor or planned stop** | — | No hold state and no tag; the clock keeps counting (D-33). |

There are **no reminders to technicians while work is in progress** (D-26). After accept, only the raiser's Escalate and the 4-h manager alert move a stuck ticket.

## 9. Claim resolved

- Only the lead claims (D-35). **Downtime ends here.**
- The lead writes the **cause in his own words** (D-36). The text box suggests causes written before on the same machine; the phone's voice typing works (default). A cause is required, in any language.
- After a reopen, the lead writes the cause again at the next claim.
- "Temporary fix" tick: downtime stops and a follow-up ticket opens for the real repair (default).
- No parts form: the store records returns; anything issued and not returned counts as used (default).
- The raiser (and any confirm handover person) is alerted.

## 10. Observation, confirm, auto close

| Time after the claim | The raiser can | App |
|---|---|---|
| 0 – 2 h (observation, D-28) | Reopen (default); **not** close | — |
| at 2 h | — | Alerts the raiser: "you can confirm now" |
| 2 – 4 h | Close (working) or reopen | — |
| at 4 h | — | **Auto close**, shown as unconfirmed (D-29, default) |

Jobs skip the observation: they can be confirmed straight away; auto close still applies at 4 h (default).

## 11. Reopen

- One-tap reason: **not working**, **partly working**, or **different problem** (default). "Different problem" opens a new linked ticket instead of reopening this one.
- **1st reopen** → back to the same lead, who accepts again (accept timer starts).
- **2nd reopen** → `review`: the incharge keeps, adds or changes people (D-38).
- **3rd and later** → `manager_decision`: the manager carries on, changes people, or closes it as not fixed with a follow-up (D-38).
- The gap from the claim to the reopen **counts as downtime** (D-39).

## 12. Alerts (default)

Only on-duty people get ticket alerts. Every alert also lands in the in-app list.

| When | Raiser | Incharge | Technician | Store | Manager |
|---|---|---|---|---|---|
| Ticket raised | | ● | | | ○ no incharge on duty |
| Ticket assigned | | | ● assigned people | | |
| Not assigned in 10 min | | | | | ● |
| Not accepted in 5 min | | ● | | | |
| Help needed | | ● | | | |
| Raiser escalates | | ● 1st | | | ○ 2nd and later |
| Opt-out request | | ● | ○ lead | | |
| Parts requested | | | | ● | |
| Parts issued | | | ● requester | | |
| Group handover | | ● receiving incharge | | | |
| Shift handover | ○ confirm side | | ● receiving person | | |
| Claim resolved | ● | | | | |
| Observation over (2 h) | ● | | | | |
| Reopened | | ○ 2nd | ● lead (1st) | | ○ 3rd and later |
| Machine stopped 4 h | | | | | ● once (D-27) |
| Job past target date | | ● | | | ○ still open the next day (setting) |

● always · ○ only in the case named

## 13. Cancel and merge (default)

- Cancel: the incharge or manager, with a reason, only before any accept or part request.
- Merge: two tickets for the same stoppage → the incharge merges them; the earliest stop time is kept; raisers of both stay on the surviving ticket.

## 14. Jobs

- Kind Job; no downtime; no assign, accept or 4-h timers; the incharge sets a target date (D-23).
- Past the target date: the incharge is alerted, then the manager (default).
- The rest of the flow (assign, accept, parts, claim, confirm, reopen) is the same.

## 15. Downtime (summary)

Downtime of a ticket runs from the declared stop time to the last claim resolved, including claim-to-reopen gaps. Waits keep counting. Running faults count only from "Now stopped"; jobs never count. How it becomes the monthly KPIs is in `kpi.md`.

## 16. Edge cases

**Raise**
- Same breakdown raised twice → the app shows the open ticket; the second person joins it.
- Both got in anyway (no signal) → the incharge merges them; the earliest stop time is kept.
- Wrong machine picked → corrected by the incharge or technician; logged.
- Raised by mistake → cancelled with a reason, only before work or parts.
- Raised after the repair → web back-fill, marked as a late entry.
- No signal at the machine → the phone keeps it and sends later; both times are saved.
- Power cut stops everything → one parent ticket; stopped machines link to it.

**Assign and accept**
- No incharge on duty → the manager gets it and assigns an incharge or technicians.
- Nobody from the group on duty → the manager is alerted at once.
- Not assigned in 10 min → the manager is alerted and can assign directly.
- Lead doesn't accept in 5 min → the incharge is alerted and picks a new lead.
- Helper busy elsewhere → asks to opt out with a reason; incharge or lead approves; incharge replaces.
- Person is off duty → the incharge is warned; can still add them, with a reason.

**Work**
- Raiser unhappy with the work → Escalate with a reason; incharge steps in; 2nd time the manager.
- Technician can't fix it → Need help with a reason; the incharge adds people or hands over.
- Accepted, then stuck → no reminders to the technician; the raiser escalates.
- Machine stopped for 4 h → the manager is alerted once.
- Shift ends with no handover → the ticket stays; the incoming incharge reassigns.
- Lead leaves mid-job → passes the lead; the new lead accepts.
- Part not in stock → waiting for material; the manager sees it ageing.
- Wrong part issued → returned unused; new request; both logged.
- A second fault found → new linked ticket with its own clocks.
- Needs a vendor or a planned stop → no hold; the clock keeps counting.

**Claim and close**
- Raiser tries to close early → close unlocks 2 h after the claim.
- Fails during the observation → the raiser reopens; the gap counts as downtime.
- Claimed and reopened again and again → 2nd reopen the incharge reviews; 3rd the manager decides.
- Reopened for a different fault → "different problem" opens a new linked ticket.
- Raiser gone when it's claimed → the handover person confirms, or it auto closes at 4 h.
- Raiser gone, no handover → any production incharge confirms.
- Confirmed by mistake → closed stays closed; a new ticket, flagged as a repeat.
- Same fault again after close → new ticket, flagged as a repeat.

**Parts** (the store side is in `inventory.md`)
- Part kept, never returned → counts as used; shows in the manager's parts report.
- Part taken without a ticket → the store doesn't issue it.
- Cancelled after parts were issued → can't cancel; close as not needed and return the parts.

**System**
- No new schedule uploaded → the last schedule stays in use.
- Someone absent today → marked by the incharge; no tickets or alerts go to them.
- Someone leaves the company → account blocked; their open tickets go to the incharge.

## 17. Screens

**Phone app (all roles)**: login, first-login password change, language, notification list, app update screen, notification and battery setup guide.

| Role | Screens |
|---|---|
| Raiser | Home (Raise button, my open tickets) · Raise · Ticket (timeline, Escalate, Now stopped, confirm or reopen, hand over the confirm step) |
| Group incharge | Inbox (new and unassigned, with timers) · Assign · Ticket (help, escalations, opt-outs, team changes, group handover, cancel or merge, review) · Today's team (on duty, mark absent) |
| Technician | My tickets · Ticket (accept, request parts, need help, opt out, shift handover, claim with cause) |
| Manager | Needs me (no incharge, 10-min timeouts, 2nd escalations, 3rd reopens, 4-h stoppages) · Assign · Decide |

**Web**

| Who | Screens |
|---|---|
| Admin, manager | People (bulk import, permissions, unlock, reset device) · Groups · Shifts · Schedule upload · Absences · Lines, machine types, machines and lanes, QR sheet printing · Places · Settings (timers, app version) · Parts register (read-only until stage 7) · Ticket board and ticket detail · Back-fill · Imports |
| Store | Part requests (issue) |
| Viewer (DGM) | Ticket board (read-only); KPI reports in stage 8 |

## 18. Tap budget (default)

| Person | Taps | Steps |
|---|---|---|
| Raiser | 5 | Scan machine → Stopped → Pick group → Raise → (after 2 h) Working? Yes |
| Group incharge | 3 | Open alert → Pick people → Assign |
| Lead | 2 + cause | Accept → (fixes the machine) → Claim → writes the cause |
| Helpers | 0 | — |

Only when needed: request parts, need help, escalate, opt out, hand over, not working + reason.
