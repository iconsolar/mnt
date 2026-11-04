# Data layer

MySQL 8, InnoDB, `utf8mb4` / `utf8mb4_0900_ai_ci`. All schema changes go through Alembic migrations. This file names the tables and the rules; the migrations hold the exact DDL. Columns marked *(later)* belong to a later stage.

## 1. Rules

1. **Events are the source of truth.** `ticket_events` (and later `stock_movements`) are append-only. A database trigger blocks `UPDATE` and `DELETE` on them. Corrections are new events.
2. **The `tickets` row is a projection** of its events. It is written in the **same transaction** as the event that changes it, so it can never disagree with the log. A command (`flask tickets rebuild`) recomputes every projection from events; a test runs it and compares.
3. **Never store what can be derived**: downtime minutes, observation phase, "waiting for material", on-duty status, stock on hand. Compute them in queries or in the domain layer. The only stored computed values are the frozen monthly KPI snapshots *(table in stage 5, app rows in stage 8)*.
4. **Two clocks.** Every event stores `client_time` (the phone's clock, nullable for web and worker events) and `server_time` (set by the server). Ordering and timers use `server_time` only.
5. **Business times are separate fields.** The declared stop time ("machine stopped at") is a business field on the raise event, defaulting to the raise time. Only the raiser (at raise) or a back-fill entry sets it earlier.
6. **UTC in the database, IST on screen.** Shift and day boundaries are computed in `Asia/Kolkata`.
7. **Masters are deactivated, never deleted**, once anything refers to them.
8. **Idempotency.** Every write from the phone carries a client UUID; a unique index rejects a second copy and the API returns the first result.

## 2. People, access, devices

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, employee_code (unique), name, phone, role_template_id, language (`en`/`hi`/`bn`), status (`active`/`blocked`/`left`), password_hash, must_change_password, failed_logins, locked_at, created_at | One row per person, one role per person (D-50). Every line operator has their own (D-11). |
| `role_templates` | id, code, name | `line_operator`, `production_incharge`, `technician`, `maintenance_incharge`, `manager`, `store`, `viewer`, `admin`, `super_admin`. The role says who someone is in the ticket rules; who is group incharge on a shift comes from the schedule. Template permissions are defined in code and copied when the person is created. |
| `screens` | code (PK), area, name_key | Registry of screens and actions; seeded from code. |
| `user_screen_permissions` | user_id, screen_code, can_view, can_act | The real permission, per person (ICON TRACE pattern). |
| `devices` | id, user_id, install_id (unique), model, os_version, app_version, fcm_token, bound_at, unbound_at, unbound_by, last_seen_at | One active device per user (D-12). |
| `access_tokens` | id, user_id, device_id, token_hash, issued_at, expires_at, revoked_at | Hash only; 15 min (D-53). |
| `refresh_tokens` | id, user_id, device_id, token_hash, issued_at, expires_at, replaced_at, grace_used_at, revoked_at | Hash only; 90 days, rotated on refresh. The token just replaced works once within 2 min; reuse after that revokes all tokens of that device (D-53). |
| `login_attempts` | id, employee_code, device_install_id, ip, at, success | Lockout after 5 failures in a row. |
| `totp_secrets` | user_id, secret_encrypted, enrolled_at | Super Admin, Admin and Manager (D-52). |
| `totp_recovery_codes` | id, user_id, code_hash, created_at, used_at | One-time backup codes, hash only (D-52). |
| `audit_log` | id, actor_user_id, action, entity, entity_id, before_json, after_json, at | Every admin change. |

## 3. Groups, shifts, schedule

| Table | Key columns | Notes |
|---|---|---|
| `groups` | id, code, name_en, name_hi, name_bn, active | Automation, Utility, IT, Others (D-15). Names fall back to English (D-51). |
| `group_members` | group_id, user_id | A technician's home group(s). |
| `shifts` | code (`A`/`B`/`C`), starts_at, ends_at | Local times; C may cross midnight (O-3). |
| `schedules` | id, group_id, valid_from (date), uploaded_by, uploaded_at, source_file | **Valid until the next one** for that group (D-17). |
| `schedule_entries` | schedule_id, shift_code, user_id, duty (`incharge`/`technician`) | At most one incharge per group per shift (D-16), checked on save and on import. |
| `absences` | id, work_date, shift_code (nullable), user_id, marked_by, marked_at | The incharge marks only who is absent (D-18). |

**On duty** (derived): the latest schedule for the group with `valid_from <= work_date`, the entry for the current shift, minus that day's absences. The work date of a night shift is the date it started.

## 4. Machines and places

| Table | Key columns | Notes |
|---|---|---|
| `lines` | id, code, name | |
| `machine_types` | id, code, name_en, name_hi, name_bn, default_group_id | Stringer, Laminator… Names fall back to English (D-51). |
| `machine_type_factors` | machine_type_id, factor, valid_from, set_by | Factor history, so closed months keep their factor *(used in stage 8)*. |
| `machines` | id, code (unique, printed on the QR), name, machine_type_id, line_id, number, lane (`A`/`B`/null), parent_machine_id, feeds_machine_id, default_group_id, qr_token (unique, random), active | A stringer is a parent row; lanes A and B are child rows with their own QR (D-47). A bussing points to the stringer it serves. |
| `places` | id, code, name_en, name_hi, name_bn, active | For jobs without a machine (a new install picks a place). Names fall back to English (D-51). |

QR content: `https://avirat.iconsolar/m/<qr_token>`. The app reads **only the token from a QR, never the host**, so printed labels survive the phase 2 hostname change. A phone camera opens the same URL in a browser, which shows the machine name and a link to the app. The token is random, so codes can't be guessed or edited by hand.

## 5. Parts register (stage 2 import; store tables in stage 7)

| Table | Key columns | Notes |
|---|---|---|
| `parts` | icon_code (PK, the key), name, spec (the Excel "Part ID": kept as text, **not unique**), oem_code, category_type (`mechanical`/`electrical`/`pneumatic`), category_use (`consumable`/`critical`), machine_type_id (nullable), machine_association_raw (the Excel's text, as it was), general_kind (`general`/`pneumatic`/null), bin, unit, min_level, reorder_qty_rule, exchange_item, unit_price, currency, supplier, photo_path, active | Imported from the 1 Nov register in stage 2 so a parts request picks a real part. Stock columns do not exist here: stock is derived from movements *(stage 7)*. |

## 6. Tickets

### 6.1 `tickets` (projection)

| Column | Notes |
|---|---|
| id | UUID from the phone (or server for web/back-fill) |
| number | Human number `T-YYMM-NNNN`, given by the server when the raise arrives |
| kind | `stopped` / `running_fault` / `job` |
| machine_id / place_id | Exactly one of them |
| group_id | Current group (changes on an accepted group handover) |
| raised_by, raised_at | First raise event |
| declared_stop_at | When the machine stopped (business time). Null for running faults until "Now stopped"; null for jobs |
| state | See §6.3 |
| lead_user_id | Current lead |
| reopen_count | Projection of reopen events |
| target_date | Jobs only |
| claimed_at | Latest claim; observation and auto close are derived from it |
| close_type | `confirmed` / `auto` / `manager` / `not_needed` / null |
| closed_at, closed_by | |
| cancelled_reason, merged_into_ticket_id | |
| parent_ticket_id | Follow-up, second fault, "different problem" (D-58), repeat |
| late_entry | True for back-filled tickets (a fact about how it was entered, not a derived flag) |
| last_event_at | For sorting lists |

### 6.2 Other ticket tables

| Table | Key columns | Notes |
|---|---|---|
| `ticket_events` | id, ticket_id, seq, type, actor_user_id (null for the worker), client_uuid (unique), client_time, server_time, payload JSON | Append-only. `seq` increases per ticket. |
| `ticket_members` | ticket_id, user_id, role (`lead`/`helper`), added_at, added_by, removed_at, removed_reason | Projection of assign, add, remove, opt-out and lead-change events. |
| `ticket_raisers` | ticket_id, user_id, joined_at, is_confirmer | The raiser, people who joined a duplicate, and the person a confirm step was handed over to. |
| `ticket_timers` | id, ticket_id, kind, due_at, created_by_event_id, fired_at, cancelled_at | Written by events, fired by the worker (§7). |
| `part_requests` | id, ticket_id, client_uuid, icon_code, qty, requested_by, requested_at, status (`open`/`issued`/`cancelled`), issued_qty, issued_by, issued_at | Stage 3 keeps it minimal; stage 7 turns issues into stock movements. |

### 6.3 States

| State | Meaning |
|---|---|
| `raised` | Waiting for the incharge (or the manager) to assign people |
| `assigned` | People assigned; waiting for the lead to accept |
| `in_progress` | The lead accepted |
| `review` | 2nd reopen: the incharge must keep, add or change people |
| `manager_decision` | 3rd reopen (and later): the manager decides |
| `claimed` | Claim resolved. Observation, confirm window and auto close are derived from `claimed_at` |
| `closed` | Confirmed, auto closed, closed by the manager, or closed as not needed (`close_type`) |
| `cancelled` | Cancelled with a reason, or merged into another ticket |

Allowed transitions and who may make them are in `docs/specs/tickets.md` §3. The domain layer rejects anything else.

### 6.4 Event types

`raised`, `joined`, `routed`, `assigned`, `lead_changed`, `accepted`, `assign_timed_out`, `accept_timed_out`, `member_added`, `member_removed`, `optout_requested`, `optout_decided`, `help_requested`, `escalated`, `group_handover_requested`, `group_handover_decided`, `shift_handover_requested`, `shift_handover_decided`, `part_requested`, `part_issued`, `part_request_cancelled`, `kind_changed`, `machine_corrected`, `note_added`, `claimed`, `observation_ended`, `confirmed`, `reopened`, `review_done`, `manager_decided`, `auto_closed`, `closed_not_needed`, `cancelled`, `merged`, `stopped_4h_alerted`, `job_overdue_alerted`.

Payloads are JSON with a version number. Each type's payload is documented next to its handler and covered by a test.

## 7. Timers and the worker

- An event that starts a clock inserts a `ticket_timers` row: `assign` (10 min, at raise, after an accepted group handover, or when the manager re-routes to an incharge), `accept` (5 min, at assign or lead change), `observation_end` (2 h after claim), `auto_close` (4 h after claim), `stopped_4h` (4 h after the declared stop time, stopped tickets only), `job_overdue` (target date). Jobs get only `job_overdue` and `auto_close` (D-60).
- An event that makes a clock pointless sets `cancelled_at` on it (for example `accepted` cancels `accept`).
- The worker runs every 30 s: `SELECT … WHERE due_at <= now AND fired_at IS NULL AND cancelled_at IS NULL FOR UPDATE SKIP LOCKED`, applies the effect as an event, and marks the timer fired, in one transaction. Two workers can never fire the same timer.
- Durations come from `settings` (defaults from the DGM, D-24 to D-29), read when the timer is created.

## 8. Notifications

| Table | Key columns | Notes |
|---|---|---|
| `notifications` | id, user_id, ticket_id, kind, params JSON, created_at, sent_at, attempts, last_error, read_at | The outbox and the in-app list in one. The text is rendered at send time in the receiver's language. |

Only the worker sends. A failed send is retried with backoff; the row stays in the in-app list either way.

## 9. Settings

| Table | Key columns | Notes |
|---|---|---|
| `settings` | key, value_json, updated_by, updated_at | Timer values, minimum app version, latest APK, cause suggestion on/off, DWT band thresholds… Every change is audited. |

## 10. Later stages

- **Stage 5**: `history_breakdowns` (the 304 Excel rows, read-only, never shown as tickets), `kpi_month_snapshots` (one table, `source` = `excel` or `app`; Aug and Sep come in as saved with `source = excel`, D-64). See `docs/specs/imports.md`.
- **Stage 7, store**: `stock_movements` (append-only: opening, receipt, issue, return, adjustment; a `return` movement is written at the store's confirmation), `receipts`, `returns` (requested → approved/rejected → received, D-61), `stock_counts`, `currency_rates`. See `docs/specs/inventory.md`.
- **Stage 8, KPI**: `calendar_days` (planned minutes per day), `planned_stops`; app rows in `kpi_month_snapshots`. See `docs/specs/kpi.md`.

## 11. Derived values (never stored)

| Value | How |
|---|---|
| Downtime of a ticket | From `declared_stop_at` (or the `kind_changed` "now stopped" time) to the last `claimed`, including gaps between a claim and a reopen (D-39). Open tickets: to now. |
| Downtime of a machine | The **union** of its stopped tickets' intervals, so overlapping tickets don't count the same minutes twice (D-63). |
| Observation phase | `claimed_at` to +2 h: observation (reopen only). +2 h to +4 h: confirm window. Jobs have no observation (D-60). |
| Waiting for material | The ticket has a part request with status `open`. |
| On duty | §3. |
| Escalation level | Count of `escalated` events on the ticket. |
| Stock on hand *(stage 7)* | Sum of `stock_movements` for the part. |
