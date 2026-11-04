# backend

The Flask application (API for the phone app, web screens for the browser) and the worker process. Created in stage 2 (`BACKLOG.md`).

Planned layout:

```
backend/
  app/
    __init__.py        app factory
    config.py          settings from .env
    clock.py           injectable clock, IST/UTC, shift and work-date helpers
    auth/              web login, TOTP, mobile login, device binding, tokens, lockout
    people/            users, role templates, screen permissions, audit log
    schedule/          groups, shifts, schedules, absences, on-duty query
    machines/          lines, machine types and factors, machines and lanes, places, QR
    parts/             parts register (read-only until stage 7)
    tickets/           commands, events, projections, state rules, downtime
    notifications/     outbox, rendering per language, senders (FCM, log-only)
    web/               Jinja2 screens, local static files (no CDN)
    translations/      en, hi, bn
  worker.py            timers and notification sending, every 30 s
  migrations/          Alembic
  tests/               pytest against a MySQL test database
  wsgi.py              Waitress entry point
```

Stage 7 adds `store/` and `imports/`; stage 8 adds `kpi/`.

Every route must carry a rule (`@requires` or `@signed_in`, in `app/people/access.py`) or be named in `PUBLIC_ENDPOINTS` there. A route with neither is refused, and a test fails on it. Commands are in `../CLAUDE.md`.
