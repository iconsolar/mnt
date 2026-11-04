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
Fill these in when stage 2 and stage 4 create them.

```
# backend
(setup)        to be added in stage 2
(run web)      to be added in stage 2
(run worker)   to be added in stage 2
(migrate)      to be added in stage 2
(tests)        to be added in stage 2

# mobile
(run)          to be added in stage 4
(tests)        to be added in stage 4
(build apk)    to be added in stage 4
```
