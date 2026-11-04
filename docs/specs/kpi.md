# KPI calculation (stage 8)

How the monthly KPIs are calculated from tickets and the store. Diagrams: `docs/flows/inventory-kpi-flows.html` (Flow A). The formulas reproduce the DGM's KPI Excel (`Maintenance_Breakdown_KPI_Summary_01_October_2026.xlsm`, D-44), with two decided changes: the real month (D-46) and line downtime % as the headline (D-45).

## 1. Inputs

| Input | Source |
|---|---|
| Tickets | Every ticket, including back-filled late entries (D-48) |
| Machine master | Machine → machine type → downtime factor (`machine_type_factors`, with history) |
| Calendar | Planned minutes per day (default 23 h = 1,380 min), minus holidays and planned stops, plant-wide or per machine |
| Excel history | Aug–Sep monthly KPIs as saved, and the 304 rows read-only (`imports.md`) |

## 2. Which tickets count

- **Stopped** tickets only. A running fault counts from the moment it was marked "Now stopped" (default). Jobs never count.
- Running faults and jobs are listed separately with their count and age (default), so they stay visible.

## 3. Downtime of one ticket

From the declared stop time to the **last** claim resolved, including every claim-to-reopen gap (D-39). Vendor and machine-release waits count (D-33). The observation after the final claim does not count.

## 4. Split by day, shift and month (default)

- Each minute of downtime goes to the day, shift and month in which it happened (IST). A stoppage from 31 Aug 22:00 to 1 Sep 03:00 puts 120 minutes in August and 180 in September.
- The **breakdown is counted once**, on the day, shift and month it started.
- This is why the Excel's 1–4 Aug laser cable stoppage (logged as 4 rows of 740, 740, 780 and 545 min) becomes one breakdown here.

## 5. Machine type and factor

- The QR gives the machine (Stringer 8A); the master gives its type and factor.
- Factors from the Excel's Instructions sheet: **0.333** Stringer, Layup, Laminator · **0.9** Auto Bussing, Auto Trimming, Auto Framing, Sealant Dispenser, JB Dispenser, JB Soldering, JB Potting, Sun Simulator, Final EL · **1** for the rest.
- Open: lane factor (O-6) and bussing factor (O-7).
- A factor change applies from its `valid_from`; closed months keep the factor they were calculated with.

## 6. Formulas

Per month, per machine type and for all machines.

| KPI | Formula | Aug 2026 in the Excel |
|---|---|---|
| Breakdowns | Stopped tickets that started in the month | 150 |
| BD minutes | Downtime minutes that fell in the month | 14,403 (240 h) |
| MTTR | BD minutes ÷ breakdowns | 96.02 min |
| Weighted downtime | BD minutes × factor | 6,630.37 min |
| Working minutes | Days in the month × planned minutes per day − planned stops (D-46) | 41,400 (fixed in the Excel) |
| MTBF | (working minutes − weighted downtime) ÷ breakdowns. For all machines: working minutes × number of machine types | 6,303.80 min |
| **Line downtime %** (headline, D-45) | Total weighted downtime ÷ working minutes × 100. This is the Excel's TDH % | 16.02 % |
| Line availability | 100 − line downtime % (default) | 83.98 % |
| DWT % | Average over machine types of (weighted downtime ÷ working minutes × 100). Bands: < 0.59 good, 0.60–0.90 normal, ≥ 0.91 bad | 0.6406 % |

With the real month, August has 31 × 1,380 = **42,780** working minutes, so August's line downtime becomes 6,630 ÷ 42,780 = **15.5 %**.

Per type, August: Stringer 86 breakdowns, 8,448 min, MTTR 98.2, weighted 2,813.18, downtime 6.80 %. Laminator 17, 2,890 min, MTTR 170, weighted 962.37, 2.32 %.

Sep 2026 in the Excel: 154 breakdowns, 11,243 min, MTTR 73.01, MTBF 6,143.54, DWT 0.5888 %, TDH 14.72 %.

## 7. Matching the Excel (acceptance test)

Before trusting the app's own numbers, recompute August and September from the imported 304 rows **with the Excel's own rules** and match the saved values above to two decimals:

- working minutes fixed at 41,400 per type;
- "all machines" working minutes = 23 × 41,400 (the Excel's `COUNTA(Instructions!D2:D24)`);
- DWT % = average over the 25 listed types, including those with no breakdowns;
- factors by machine-type name, defaulting to 1 when a name isn't in the 23-row factor table.

This "Excel mode" exists only for the test. The app's reports use the real month and the machine master.

## 8. Spares cost KPIs

| KPI | Formula | Reference |
|---|---|---|
| Consumption ₹ | Issues × price at the time of issue, minus approved returns in the month they are approved | Per month, machine and category |
| Monthly budget | Annual budget ÷ 12 | FY 2026-27: ₹10 Cr → ₹83.3 lakh a month. FY 2027-28: ₹8 Cr. FY 2028-29: ₹7 Cr |
| Budget status | Consumption ÷ monthly budget | On budget ≤ 100 % · Watch ≤ 105 % · Over budget above |
| ₹ per watt | Consumption ₹ ÷ (produced kW × 1,000) | Target ₹0.057/W (₹10 Cr ÷ 8,000 × 350 × 0.625 kW). April: ₹48.3 lakh ÷ 65,904 kW = ₹0.073/W |

- Produced kW: typed by the manager each month, or later fed from ICON TRACE's sun simulator data (one-way, outbound from ICON TRACE; designed when needed).
- $ prices use the manager's monthly rate, not a fixed 96 (default).

## 9. Month-end snapshot (default)

- At month end the app freezes the month's KPIs into `kpi_month_snapshots`. This replaces the Excel's UpdateHistory macro.
- A back-fill entry in a closed month asks the manager to re-run that month; the re-run is logged.
- Aug and Sep 2026 come in from the Excel as snapshots marked `source = excel`.

## 10. Reports

Dashboard · Monthly report · Machine report (per type and per machine, e.g. Stringer 8A) · Shift report (A/B/C) · Daily analysis · Top problems (from cause texts; a cause list comes later from what technicians write, D-36).

## 11. Excel bugs not to copy

- Formula ranges stop at different rows (row 304 in the Machine Dashboard, 11,003 or 27,709 elsewhere), so sheets disagree (300 vs 304 breakdowns; September 150 vs 154).
- Monthly Summary's MTBF (51.8 min) divides all machines' downtime into one machine's working time.
- Working minutes fixed at 41,400 whatever the month.
- Dates stored as text (`dd.mm.yyyy`).
