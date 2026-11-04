# Avirat — project overview (the contract)

Avirat is the maintenance app for ICON Solar-En Power Technologies, Unit-2 (Raipur). It covers three things, built in this order:

1. **Tickets**: breakdowns and jobs, from raise to close, with downtime (LoP) recorded as it happens.
2. **Maintenance store**: spare parts, receipts, issues against tickets, returns, stock counts.
3. **KPI reports**: the DGM's monthly downtime KPIs and spares cost, worked out from tickets and the store.

*Avirat* (Hindi अविरत, Bangla অবিরত) means "uninterrupted". The app exists to keep the lines running, so it must stay simple: **the team fixes the machine, not the ticket.** Every screen and every step is judged against that.

This file is the contract for anyone (person or coding agent) working in this repo. Read it before writing code. Decisions and their dates live in `DECISIONS.md`; the data model in `DATA_LAYER.md`; behaviour in `docs/specs/`; open work in `BACKLOG.md`.

---

## 1. Phases

| Phase | What | Hosting | Distribution |
|---|---|---|---|
| **1. LAN pilot** (now) | Tickets first, then store, then KPI | Own server on the plant LAN | Signed APK downloaded from the Avirat server |
| **2. Internet** (later) | Same app, reachable from outside | The same on-prem server exposed through the FortiGate. **Never cloud.** | Google Play (company account) |

- **Production first, store publish later.** The pilot must prove itself in production on the LAN before any Play Store work. Prepare for a hold the way ICON TRACE was held: each stage must be usable on its own.
- Phase 2 must need **configuration, not code**: the app always talks to a hostname over HTTPS, and the base URL is configuration.

## 2. Architecture

```
 Android app (Flutter)            Web browser (store PC, manager, admin)
        │  HTTPS (JSON API)               │  HTTPS (server-rendered pages)
        └───────────────┬─────────────────┘
                 Caddy reverse proxy  ── TLS, certificate from the plant's internal CA (step-ca)
                        │
                 Waitress → Flask app  ── /api/v1/* for the app, web pages for the browser
                        │
                    MySQL 8  ◄──── worker process (timers, notification outbox)
                                          │
                                          └── FCM (outbound only, see O-1)
```

- **One Flask application** serves both the JSON API (`/api/v1/...`) for the phone app and the server-rendered web screens (Jinja2), like ICON TRACE.
- **A separate worker process** runs every 30 seconds: it fires due timers and sends queued notifications. The web process never sleeps waiting for a timer.
- **Own host**, separate from ICON TRACE. ICON TRACE stays off the internet; nothing in Avirat may depend on reaching the ICON TRACE server in phase 1. A later link (for example produced kW from sun simulator data) is a one-way, outbound feed designed when needed.

## 3. Stack

| Part | Choice | Notes |
|---|---|---|
| Server OS | Windows Server (like ICON TRACE) | Waitress, not Gunicorn (Unix only) |
| Backend | Python 3.12, Flask 3, SQLAlchemy 2, Alembic, PyMySQL | App factory pattern; migrations only through Alembic |
| Web screens | Jinja2 templates, small vanilla JavaScript | **No CDN**: fonts, CSS and JS are served from the app (LAN has no internet) |
| Database | MySQL 8, InnoDB, `utf8mb4` | Times stored in UTC (`DATETIME(3)`) |
| Passwords / admin 2FA | argon2 (argon2-cffi), PyOTP for TOTP | TOTP for Admin and Super Admin, like ICON TRACE |
| i18n (web + push texts) | Flask-Babel | en, hi, bn |
| Reverse proxy / TLS | Caddy with the internal CA's ACME endpoint (Smallstep step-ca, as planned for ICON TRACE) | Certificate carries the hostname **and** the server IP in SAN |
| Mobile | Flutter (stable), Dart 3 | Android only. Riverpod, go_router, drift (local DB), mobile_scanner (QR), firebase_messaging + flutter_local_notifications, flutter_secure_storage, gen-l10n |
| Push | Firebase Cloud Messaging (HTTP v1) | Sender is pluggable; see open question O-1 |
| Tests | pytest against a MySQL test database; Flutter widget tests | Every ticket transition and every timer has a test |

## 4. Network (phase 1)

- Hostname: `avirat.iconsolar` (internal DNS), following ICON TRACE's `erp.iconsolar` pattern. Users and the app use the **name**, never the IP. The certificate also carries the IP so the app can fall back to it if a phone cannot resolve the internal name (for example when Android "Private DNS" is set to an outside provider).
- Personal phones join a **Wi-Fi network for phones** whose firewall rules allow only the Avirat server on 443 (plus, if O-1 is approved, the internet for push alerts). The plant VLAN and ICON TRACE stay unreachable from it.
- The Avirat server needs outbound HTTPS to FCM only (O-1). No other outbound calls.
- Wi-Fi coverage near the machines is checked before the pilot (`BACKLOG.md`, stage 6). Raising works without signal (offline outbox), but alerts and sync need the network.

## 5. Security rules

- **Mobile login**: employee ID + password set by the manager (changed at first login), then the account is **bound to that phone**. One bound phone per person; moving to a new phone needs the manager to reset the binding. **Lockout after 5 failed attempts**; the manager unlocks. No SMS OTP.
- Tokens: short-lived access token + long-lived refresh token tied to the bound device; refresh token kept in Android Keystore (flutter_secure_storage); tokens stored only as hashes on the server; revoked on unbind.
- **Web login**: session cookie + CSRF protection. Admin and Super Admin sign in with TOTP (password as backup), like ICON TRACE.
- **Per-screen permissions** (ICON TRACE pattern): every route checks the person's permission on the server. Role templates only pre-fill permissions; each person's permissions can be changed one by one. A denied view closes; it is not just a hidden button.
- TLS everywhere. The Flutter app **bundles the internal root CA certificate** and trusts it through Dart's `SecurityContext` (plus the system roots, for phase 2). **Never** turn off certificate checks (`badCertificateCallback` returning `true` is forbidden).
- Secrets never enter git: `.env`, the FCM service-account file, the Android signing keystore and `key.properties`. The signing keystore is backed up offline; losing it means every phone must uninstall and reinstall.
- Every admin change (settings, permissions, machines, factors, schedules) goes to an audit log with who and when.
- Nightly MySQL backup, copied to the plant NAS.

## 6. Languages

- **English, Hindi and Bangla** (Bangla last). Every user-facing string is a translation key from day one, in the app (ARB files) and on the web (Flask-Babel). No hard-coded text in widgets or templates.
- Each person picks their language. Push notification texts are rendered on the server in the receiver's language.
- Free text (cause, notes, reasons) is stored exactly as typed, in any script.
- Fonts: Noto Sans with Devanagari and Bengali, bundled in the app and served locally on the web.

## 7. Alerts

- Alerts are rows in a **notification outbox**; the worker sends them. Nothing sends a push directly from a web request.
- Android channels per alert type; urgent ones (new breakdown for you, lead must accept) get high priority and their own sound. No full-screen intents.
- The app shows a setup guide for notification permission (Android 13+) and the phone's battery settings. Do **not** use `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` (Play policy risk for phase 2).
- Every alert also appears in the in-app notification list, so a missed push is never a lost alert.
- Only on-duty people get ticket alerts.

## 8. Offline behaviour (phone)

- Actions (raise, accept, claim, confirm, reopen, escalate, request parts…) go into a local outbox with a client-generated UUID and the phone's time, and are sent when the server is reachable. The server treats the UUID as an idempotency key, so a resend never creates a duplicate.
- The server is the authority: if an action is no longer valid when it arrives (for example someone else already accepted), the server refuses it with a reason the app shows.
- Every event records **both the phone's time and the server's time**. Order and timers always use server time; the declared stop time is a separate business field.

## 9. Distribution (phase 1)

- Release APK signed with the company key, downloaded from a page on the Avirat server.
- `GET /api/v1/app/version` returns the latest and the minimum version. Below the minimum, the app shows a blocking "update" screen that opens the download link in the browser (no `REQUEST_INSTALL_PACKAGES`).
- The Android application ID is permanent once phones install the app (open question O-2). Phase 2 publishes the same app, with the same key, through Google Play.

## 10. Do and don't

**Do**
- Use the vocabulary in `docs/specs/` (raiser, group incharge, lead, claim resolved, observation, auto close, reopen, handover, Icon Code, LoP). Ask before inventing a domain concept.
- Store **events**; derive durations, phases and flags in queries. The ticket row is a projection of its events (see `DATA_LAYER.md`).
- Inject the clock (no direct `datetime.now()` in domain code) so timers are testable.
- Keep the ticket module and the store module separate. A ticket only *requests* parts; the store module owns stock.
- Keep each stage shippable; stop at the end of a stage for Mukesh's checkpoint.

**Don't**
- Don't add a "no update" reminder for technicians, a hold state, or a waiting tag. All three were decided against.
- Don't store downtime as a number, or any value that can be recomputed from events (except the frozen monthly KPI snapshot).
- Don't order or time anything by the phone's clock.
- Don't call any external service except FCM. No CDNs.
- Don't edit or delete event rows. Corrections are new events.
- Don't change a decision in `DECISIONS.md` inside a code change. Raise it with Mukesh first.

## 11. Repo layout

```
avirat/
  PROJECT_OVERVIEW.md   this contract
  DECISIONS.md          decisions with dates, defaults, open questions
  DATA_LAYER.md         tables, event log, time rules
  BACKLOG.md            staged work; source of truth for open items
  CLAUDE.md / AGENTS.md working rules for coding agents
  docs/specs/           tickets.md, inventory.md, kpi.md, imports.md
  docs/flows/           the two diagram pages (open in a browser)
  docs/templates/       CSV templates for machines, people, shifts, schedule, places
  backend/              Flask app + worker (stage 2)
  mobile/               Flutter app (stage 4)
```

Backend modules (stage 2 creates them): `auth`, `people`, `schedule`, `machines`, `parts`, `tickets`, `notifications`, `worker`, `web`, later `store`, `kpi`, `imports`.
