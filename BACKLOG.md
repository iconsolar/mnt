# Backlog

The source of truth for open work. One stage at a time; every stage ends with **Mukesh's checkpoint** before the next starts. Tick items as they land; add discovered work under the right stage with a short note.

Legend: `[ ]` open · `[x]` done · `(O-n)` blocked by an open question in `DECISIONS.md`.

---

## Stage 1 — Repo and contract docs ✅
- [x] PROJECT_OVERVIEW.md, DECISIONS.md, DATA_LAYER.md, BACKLOG.md, CLAUDE.md, AGENTS.md
- [x] Specs: tickets, inventory, KPI, imports
- [x] Diagram pages and data templates

## Stage 2 — Backend core
Done when: an admin can sign in on the web, create people, groups, shifts, a schedule and machines, print QR codes, and a phone-style API client can log in, bind a device and fetch "my profile".

- [ ] Flask app factory, config from `.env`, Waitress entry point, structured logging, health check `/api/v1/health`
- [ ] MySQL + SQLAlchemy 2 + Alembic; first migration; test database for pytest
- [ ] Injectable clock; IST/UTC helpers; shift and work-date helpers (night shift belongs to its start date)
- [ ] i18n: Flask-Babel with en, hi, bn catalogues; language per user
- [ ] Users, role templates, screen registry, per-screen permissions (ICON TRACE pattern); permission check on every route
- [ ] Web login (session + CSRF); TOTP for Admin and Super Admin
- [ ] Mobile login: employee ID + password, first-login password change, device binding, access + refresh tokens, lockout after 5 failures, manager unlock and device reset
- [ ] Audit log for every admin change
- [ ] Groups and members; shifts (O-3); schedules with valid-from; absences
- [ ] On-duty query (group + shift + date, minus absences) with tests
- [ ] Lines, machine types (factor history), machines with parent (stringer → lanes) and feeds (bussing → stringer), places
- [ ] QR tokens; printable QR sheet (code, name, QR); `/m/<qr_token>` landing page
- [ ] Bulk imports from the templates: people, machines, places, shifts, schedule (validation report, idempotent)
- [ ] Parts register import from the 1 Nov Excel, read-only list with search (`imports.md` §2)
- [ ] Settings table with timer defaults (10 min, 5 min, 2 h, 4 h, 4 h)
- [ ] Web screens: people, permissions, groups, shifts, schedule upload, absences, lines, machine types, machines, places, settings, parts list
- [ ] **Checkpoint with Mukesh**

## Stage 3 — Ticket engine
Done when: every transition in `tickets.md` §3 works through the API, every timer fires correctly under the test clock, and alerts land in the outbox.

- [ ] `tickets`, `ticket_events` (append-only trigger), `ticket_members`, `ticket_raisers`, `ticket_timers`, `part_requests`, `notifications`
- [ ] Domain layer: one command per action, each writing its event and the projection in one transaction; idempotency on client UUID
- [ ] Projection rebuild command and its test
- [ ] Raise: machine or place, kind, group, stop time, optional note, open-ticket check and join, "both lanes" (O-5)
- [ ] Routing to the on-duty incharge, else the manager; "nobody on duty" alert
- [ ] Assign (lead rule), accept (lead only), lead change, add or remove people, opt-out request and decision
- [ ] Parts request (pick a part, qty) and store "issued"; waiting-for-material derived
- [ ] Need help; Escalate (1st incharge, 2nd+ manager); group handover with acceptance; shift handover with acceptance (both sides)
- [ ] Now stopped; make it a breakdown; correct the machine; second fault as a linked ticket; notes
- [ ] Claim (lead only, cause required, cause suggestions per machine, temporary-fix follow-up)
- [ ] Observation, confirm window, confirm (raiser, handover person, any production incharge), auto close
- [ ] Reopen with reason; ladder (lead → review → manager decision); "different problem" → new linked ticket
- [ ] Cancel and merge
- [ ] Jobs: target date, overdue alerts, no observation
- [ ] Worker: timers with `FOR UPDATE SKIP LOCKED` (assign 10 min, accept 5 min, observation end 2 h, auto close 4 h, stopped 4 h, job overdue)
- [ ] Notifications: outbox, per-language rendering, alert matrix (`tickets.md` §12), in-app list API
- [ ] Push sender: FCM HTTP v1 behind an interface (O-1); a log-only sender for development
- [ ] Downtime per ticket (derived) with tests for reopen gaps and running-fault stops
- [ ] API: `/api/v1/` endpoints for every phone screen in `tickets.md` §17
- [ ] Tests for every transition, every timer and every alert
- [ ] **Checkpoint with Mukesh**

## Stage 4 — Android app (Flutter)
Done when: on a real phone on the plant Wi-Fi, one operator, one incharge and one technician can run a breakdown from raise to close in all three languages.

- [ ] Project setup: application ID (O-2), flavors (dev / pilot), signing config from `key.properties` outside git, minSdk 24
- [ ] Trust the bundled internal root CA via `SecurityContext`; hostname with IP fallback
- [ ] gen-l10n with en, hi, bn ARB files; Noto Sans Devanagari and Bengali fonts
- [ ] Login, first-login password change, device binding, token refresh, lockout message
- [ ] Offline outbox (drift) with client UUIDs, retry, "waiting to send" indicator
- [ ] Raiser: home, raise (QR scan, choose machine or place, kind, group), ticket screen (escalate, now stopped, confirm or reopen, hand over the confirm step)
- [ ] Group incharge: inbox, assign, ticket actions, today's team and absences
- [ ] Technician: my tickets, accept, request parts, need help, opt out, shift handover, claim with cause
- [ ] Manager: needs-me list, assign, decide
- [ ] Notifications: FCM, channels with their own sounds, in-app list, setup guide for notification permission and battery settings
- [ ] Version check and blocking update screen (opens the APK link in the browser)
- [ ] Widget tests for raise, assign, accept, claim, confirm
- [ ] **Checkpoint with Mukesh**

## Stage 5 — Web screens and history
- [ ] Ticket board (filters: state, group, machine, kind, date) and ticket detail with the event timeline
- [ ] Store: part requests list and issue
- [ ] Back-fill form for past breakdowns (late entries)
- [ ] Import the Excel breakdown history (304 rows) and the Aug–Sep KPI values (`imports.md` §1)
- [ ] APK download page and app-version settings
- [ ] **Checkpoint with Mukesh**

## Stage 6 — LAN pilot in production
- [ ] Own Windows Server host; MySQL; Waitress and the worker as Windows services
- [ ] Caddy with the internal CA (step-ca); certificate with hostname and IP; internal DNS for `avirat.iconsolar`
- [ ] Phones' Wi-Fi: firewall rules (Avirat server only, plus internet for push if O-1 is approved); server outbound to FCM only
- [ ] Wi-Fi coverage check near every machine
- [ ] Nightly MySQL backup copied to the plant NAS; restore tested once
- [ ] Release keystore created, backed up offline, never in git
- [ ] Data loaded: people, groups, shifts, schedule, machines and lanes, places; QR labels printed and fixed on machines
- [ ] Training (raisers, incharges, technicians, manager, store) in their language
- [ ] Go-live checklist and rollback plan (the Excel keeps running in parallel for the first weeks)
- [ ] **Checkpoint with Mukesh and the DGM**

## Stage 7 — Maintenance store (`docs/specs/inventory.md`)
- [ ] Stock movements (append-only), receipts, issues from part requests, held returns and the manager's daily approval list, stock counts and adjustments
- [ ] Average price (O-8), currency rates, reorder list
- [ ] Go-live: clean the register, likely duplicates checked by the store, Excel issues since 1 Nov, opening stock, photos
- [ ] Store screens on the web; parts screens in the app use the real stock
- [ ] **Checkpoint with Mukesh**

## Stage 8 — KPI reports (`docs/specs/kpi.md`)
- [ ] Calendar (planned minutes per day, holidays, planned stops)
- [ ] Downtime split by day, shift and month; breakdown counted on its start day
- [ ] KPI calculations; "Excel mode" acceptance test against Aug–Sep (`kpi.md` §7)
- [ ] Factors: lane (O-6), bussing (O-7)
- [ ] Spares cost KPIs, budget status, ₹/W; produced kW entry
- [ ] Month-end snapshot and re-run
- [ ] Reports: dashboard, monthly, machine, shift, daily, top problems
- [ ] **Checkpoint with Mukesh and the DGM**

## Stage 9 — Internet and Play Store (later)
- [ ] Public domain with DNS under company control; public certificate
- [ ] FortiGate: expose 443 only, from a separate network zone; rate limits; hardening review
- [ ] Play Console company account (needs a D-U-N-S number, up to 30 days; Google Payments name and address must match it)
- [ ] Play App Signing with the existing key, so installed phones update from Play
- [ ] Privacy policy and the Play data safety form
- [ ] **Checkpoint with Mukesh and the DGM**
