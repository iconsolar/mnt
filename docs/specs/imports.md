# Imports

What comes in from Excel, how it is mapped, and what gets cleaned. The source files stay outside the repo (company data). Every import is a command that can run twice without creating duplicates, and prints a report of what it skipped and why.

## 1. Breakdown history (stage 5)

**File**: `Maintenance_Breakdown_KPI_Summary_01_October_2026.xlsm`, sheet **Breakdown Record** (table `BreakdownTable`), header row 4, data rows 5–308: **304 breakdowns, 1 Aug – 29 Sep 2026** (Aug 150 rows / 14,403 min; Sep 154 / 11,243 min).

These rows become `history_breakdowns`: read-only, shown in machine and problem history, **never turned into tickets**. Their minutes stay as typed, because the Excel has no start or end times.

| Excel column | Into | Notes |
|---|---|---|
| A Sl. No. | source_row_no | |
| B Date | work_date | Text `dd.mm.yyyy`, not a date |
| C Shift | shift_code | A / B / C |
| D Machine | machine_type_id | Machine-type name, mapped through §3 |
| E Machine No. | machine_no_raw | 1–3; empty in 200 rows |
| F Breakdown Start, G Breakdown End | — | Empty in all rows |
| H Breakdown Time (min) | minutes | Typed by hand; 5–780 |
| I Failure / Problem Description | description | Multi-line; 60 rows hold 2–3 faults |
| J–Q (category, component, action, status, priority, person, slip, remarks) | extra_json | Filled in 1 row only |
| R–T | — | Helper formulas, not imported |

**Monthly KPIs**: sheet **Saved Data**, B2:F14 (Month, MTTR, MTBF, DWT %, TDH %). Aug and Sep 2026 are filled. They become `kpi_month_snapshots` with `source = excel`, exactly as saved. `kpi.md` §7 is the test that recomputes them from the rows.

Stringer rows by lane, from the descriptions: 44 A only, 61 B only, 53 both, 8 not stated (evidence for O-6).

## 2. Parts register (stage 2) and opening stock (stage 7)

**File**: `U2_Spare_Parts_Inventory__November_01_2026.xlsm`, sheet **Inventory**, header row 3 (B3:V3), data rows 4–1152: **1,149 parts**.

| Excel column | Into | Notes |
|---|---|---|
| B Icon Code | `parts.icon_code` | 20004–21152, unique: the key |
| C Machine/Asset Association | machine_type_id or general_kind | Mapped through §3; "GENERAL SPARE" and "PNEUMATIC SPARE" become general_kind |
| D Part Name | name | Trim (571 names have stray spaces) |
| E Part ID | spec | Text; `NA` → null; repeats across parts (28 rows), never a key; 187 blank |
| F Category | category | Six values (Mechanical / Electrical / "Pnumatic Cyl." × Consumable / Critical). Spell as Pneumatic. 2 blank: 20122, 20277 |
| G OEM Code | oem_code | Number → text; 395 filled |
| H Location / Bin Number | bin | Trim; 252 bins; 4 blank |
| I Unit | unit | `NOS.`→Nos, `Sets.`→Sets, `Kgs.`→Kgs, `Litres.`→Litres, `Meters.`→Meters, `Rolls.`→Rolls, `Packets.`→Packets |
| J Opening Stock Qty. | (stage 7) opening movement source | |
| K Image Ref. | photo_path | Relative path such as `Images\ATW-50K\3000000589.jpeg` on the store PC; 1,146 filled |
| L Stock on Hand | — | Formula: J − issued + M. Not imported; stock is derived |
| M Receive Qty, N Receive Date | — | Empty |
| O Minimum Reorder Level | min_level | 38 blank, 22 zero |
| P Reorder Quantity, R Status | — | Formulas, not imported |
| Q Supplier Name | supplier | Empty |
| S Unit Cost ($) | unit_price, currency = USD | 305 filled |
| T Unit Cost (INR) | — | Empty |
| U, V totals | — | Formulas |

**Cleaning**
- Trim every text field.
- Drag-fill machine names (Excel incremented them): "91 DEGREE VISUAL" and "92 DEGREE VISUAL" → "90 DEGREE VISUAL"; "181 DEGREE" and "182 DEGREE" → "180 DEGREE". Confirm with Mukesh before applying.
- **Likely duplicates** (same machine, name and Part ID). List them for the store; never merge automatically:

| Icon Codes | Machine | Part | Stock | Bin |
|---|---|---|---|---|
| 20115 / 20116 | Stringer (ATW 50K) | T-shaped magnet 5-9-4 | 240 / 240 | BOX-103 |
| 20307 / 20441 | Auto Bussing (ATW 59B) | Cam bearing follower (stud type) | 24 / 8 | BOX-214 |
| 20476 / 20477 | Auto Bussing (ATW 59B) | Rod | 2 / 2 | U4 |
| 20522 / 20523 | EVA & Backsheet Cutting | White rubbe | 1 / 1 | BOX-412-1 |
| 20712 / 20713 | Auto Framing | Framing plate | 4 / 2 | BOX-417 |
| 20880 / 20881 | Conveyor System | Induction motor with gear box (6IK250GU-SFT) | 2 / 2 | BOX-429 / BOX-430 |
| 20973 / 20975 | General Spare | HDMI cable | 1 / 8 | BOX-406 |

**Consumption log** (stage 7): sheet **Breakdown Consumption**, header row 4 (B4:Q4), from row 5. Columns: B date (text `d.m.yyyy`), C Icon Code, I Quantity Consumed, O "Breakdown Description" (actually the machine instance, e.g. `STRINGER 8A`, `BUSSING 3`, `JB SOLDERING LINE-2`), P Technician (trim), Q Issue Slip Number (empty). Entries from 1 Nov until go-live are imported as issues to reach the opening stock (`inventory.md` §8).

**Photos**: copy the `Images\` folder from the store PC; keep the relative path; report any part whose file is missing.

The April–31.8 inventory file (`Spare_Parts_Inventory__April_-_31.8.xlsm`) has an empty register and the same budget dashboard. Nothing to import except the budget plan (`kpi.md` §8).

## 3. Machine names

The machine master (from `docs/templates/machines.csv`, open question O-4) holds the canonical names. Both Excel files map onto it. "Sure" pairs can be applied; "confirm" pairs need Mukesh.

| KPI Excel (machine type) | Inventory Excel (association) | |
|---|---|---|
| STRINGER | STRINGER (ATW 50K) | sure |
| AUTO BUSSING | AUTO BUSSING (ATW 59B) | sure |
| LAMINATOR | LAMINATOR (DS & TS) | sure |
| AUTO FRAMMING | AUTO FRAMING | sure |
| SUN SIMULATOR | SUN SIMULATOR (Gsola) | sure |
| CONVEYOR SYSTEM | CONVEYOR SYSTEM | sure |
| GLASS LOADER | AUTO GLASS LOADER | sure |
| AUTO TAPPING | AUTO TAPING | sure |
| JB SOLDERING | AUTO JB SOLDERING | sure |
| JB POTTING | AUTO JB POTTIING | sure |
| JB DISPENSSOR | JB DISPENSER | sure |
| AUTO CORNER FILLING | AUTO CORNER FILING | sure |
| 90 DEGREE VISUAL | 90 DEGREE VISUAL | sure |
| HI POT TESTER | INLINE HI-POT TESTING (TS); HI-POT TESTING (PDI) | confirm |
| PRE EL, FINAL EL | INLINE EL TESTER | confirm |
| 1ST EVA CUTTING, 2ND EVA CUTTING, BACKSHEET CUTTING | EVA & BACKSHEET CUTTING | confirm |
| AUTO TRIMMING | AUTO EDGE TRIMMING; AUTO CORNER TRIMMING | confirm |
| SELEANT DISPENSSOR | AUTO FRAME DISPENSER | confirm |
| LAYUP | — | confirm |
| AIR COMPRESSOR, ELECTRICAL PDB, UPS | GENERAL SPARE | confirm |
| — | ICB BENDING & TAPPING, EDGE SEELING, AUTO SHORTER, STRIP MACHINE, MODULE CURING SYSTEM, REWORK CONVEYOR, GLASS MIXTURE, AUTOMATED OPTICAL INSPECTION, 180 DEGREE | types to add |

## 4. Data templates

`docs/templates/` holds CSV templates for the data Mukesh provides. Example rows start with `EXAMPLE` and are skipped by the import.

| File | Columns | Notes |
|---|---|---|
| `machines.csv` | code, name, machine_type, line, number, lane, parent_code, feeds_code, default_group | A stringer row, then one row per lane (A, B) with `parent_code` = the stringer. A bussing row has `feeds_code` = its stringer. |
| `people.csv` | employee_code, name, phone, role_template, groups, language | `groups` separated by `;` for technicians. `language` = en / hi / bn. |
| `shifts.csv` | shift, starts, ends | 24-hour `HH:MM`. |
| `schedule.csv` | valid_from, group, shift, employee_code, duty | `duty` = incharge or technician; one incharge per group and shift. |
| `places.csv` | code, name | Places for jobs without a machine. |

## 5. Excel habits not to repeat

- Dates as text; times missing.
- Several faults in one row; one stoppage on several rows.
- Formula ranges that stop at a fixed row (rows 4–51 in the Master Sheet, 4–22 for the consumption cost lookup, 5–304 in the Machine Dashboard).
- An exchange rate typed into formulas (96).
- Sheet passwords stored in plain text inside the macros.
