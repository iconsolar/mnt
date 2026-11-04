# Avirat

The maintenance app for ICON Solar-En Power Technologies, Unit-2 (Raipur): breakdown and job tickets that record downtime (LoP) as it happens, the maintenance spare-parts store, and the DGM's KPI reports built from both.

*Avirat* (Hindi अविरत, Bangla অবিরত) means "uninterrupted". The app's job is keeping the lines running, so it stays simple: the team fixes the machine, not the ticket.

- Android app (Flutter) for line operators, incharges, technicians and the manager, in English, Hindi and Bangla.
- Web for the manager, the maintenance store PC and IT.
- Runs on the plant LAN first; goes to the internet and the Play Store later, still hosted on-prem.

## Status
Stage 1 (repo and contract docs) is done. Next is stage 2, the backend core. See `BACKLOG.md`.

## Read in this order
1. `PROJECT_OVERVIEW.md`: architecture, stack and rules (the contract)
2. `DECISIONS.md`: decisions with dates, defaults, open questions
3. `DATA_LAYER.md`: tables, event log, time rules
4. `docs/specs/tickets.md`: the ticket flow (stages 2–6)
5. `docs/specs/inventory.md`, `docs/specs/kpi.md`, `docs/specs/imports.md`: later stages
6. `docs/flows/ticket-flows.html` and `docs/flows/inventory-kpi-flows.html`: the diagrams (open in a browser; tap a box for its rules)
7. `BACKLOG.md`: staged work

Coding agents start with `CLAUDE.md`.

## Layout
```
backend/   Flask API, web screens and worker (stage 2)
mobile/    Flutter Android app (stage 4)
docs/      specs, diagrams, data templates
```
