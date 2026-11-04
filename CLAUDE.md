# Working rules for coding agents

These rules apply to Claude Code and to any other agent working in this repo (see `AGENTS.md`).

## Read first, in this order
1. `PROJECT_OVERVIEW.md`: architecture, stack, security, do and don't. **This is the contract.**
2. `DECISIONS.md`: what is decided, the defaults, and the open questions.
3. `DATA_LAYER.md`: tables, event log, time rules.
4. The spec for your stage in `docs/specs/` (`tickets.md` for stages 2–6).
5. `BACKLOG.md`: pick the next open item of the **current** stage.

## How to work
- **One stage at a time.** Finish the current stage's items, then stop and report for Mukesh's checkpoint. Never start the next stage unasked.
- **Discuss before building** anything the specs don't cover. Propose it in plain words and wait for a yes.
- **Never change a decision** in `DECISIONS.md` inside a code change. If the code seems to need one, stop and ask.
- Use the vocabulary of `docs/specs/` (raiser, group incharge, lead, claim resolved, observation, auto close, reopen, handover, Icon Code, LoP). Don't invent domain concepts or rename existing ones.
- Small commits with clear messages; tick `BACKLOG.md` items as they land and add discovered work there.
- Mukesh also works on this repo with other tools. Check recent commits before assuming the current state.

## Non-negotiable rules
- Events are append-only; the ticket row is a projection written in the same transaction. Never store downtime or any other derived value.
- Every event records the phone's time and the server's time; order and time things by server time only.
- Inject the clock in domain code; no direct `datetime.now()`.
- Every user-facing string is a translation key (en, hi, bn), in the app and on the web.
- Check permissions on the server for every route.
- No CDNs or external calls except FCM. The LAN has no internet.
- Always HTTPS to a hostname. Never disable certificate checks.
- Secrets never go into git: `.env`, the FCM service-account file, the keystore, `key.properties`.
- Every ticket transition, timer and alert has a test.
- No reminders to technicians while work is in progress, no hold state, no waiting tag (decided against).

## Commands
PowerShell, from `backend\`, with the virtual environment active. Stage 4 fills in the mobile ones.

This PC also runs ICON TRACE's Caddy (ports 80, 443, 2019, proxying to 8080). Avirat's dev setup uses 8090 and 8443 to stay clear of it. **Never stop a process by name here**, only by its own handle or ID.

```
# backend
(setup)        py -3.14 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt -r requirements-dev.txt; Copy-Item ..\.env.example ..\.env; pybabel compile -d app\translations
(run web)      python wsgi.py                 # Waitress on 127.0.0.1:AVIRAT_PORT
(run worker)   python worker.py
(migrate)      alembic upgrade head           # new one: alembic revision --autogenerate -m "what changed"
(tests)        pytest                         # needs MySQL and AVIRAT_TEST_DATABASE_URL
(dev https)    caddy run --config Caddyfile.dev --adapter caddyfile    # https://avirat.localhost:8443 -> Waitress
(seed)         flask --app app seed           # role templates and screens; groups and timer defaults join in steps 9-10
(first admin)  flask --app app users create-superadmin <employee_code>
(unlock)       flask --app app users unlock <employee_code>       # the only way for a Super Admin
(reset TOTP)   flask --app app users reset-totp <employee_code>
(import)       flask --app app import people ..\data\people.csv   # step 13; also machines, places, shifts, schedule. data\ is gitignored; docs\templates holds EXAMPLE rows only
(parts)        flask --app app import parts <path to the 1 Nov .xlsm>    # step 14
(translations) pybabel extract -F babel.cfg -o app\translations\messages.pot . ; pybabel update -i app\translations\messages.pot -d app\translations ; pybabel compile -d app\translations

# mobile
(run)          to be added in stage 4
(tests)        to be added in stage 4
(build apk)    to be added in stage 4
```
