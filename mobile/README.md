# mobile

The Flutter Android app. Created in stage 4 (`BACKLOG.md`).

Planned layout:

```
mobile/
  lib/
    main.dart
    app/            router (go_router), theme, flavors (dev / pilot)
    core/           API client (internal CA trusted via SecurityContext), auth and tokens,
                    offline outbox (drift), notifications (FCM + local channels), version check
    l10n/           app_en.arb, app_hi.arb, app_bn.arb
    features/
      raise/        scan or choose, kind, group, raise
      tickets/      ticket screen and timeline, actions by role
      inbox/        group incharge inbox, assign, today's team
      work/         technician list, accept, parts, need help, claim
      manager/      needs-me list, assign, decide
      notifications/
  assets/
    ca/             internal root CA certificate (public, safe to commit)
    fonts/          Noto Sans, Noto Sans Devanagari, Noto Sans Bengali
  android/          signing from key.properties (never in git)
```

Rules for this folder: `PROJECT_OVERVIEW.md` §5 to §9.
