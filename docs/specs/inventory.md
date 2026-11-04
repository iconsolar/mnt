# Maintenance store (stage 7)

How spare parts move. Diagrams: `docs/flows/inventory-kpi-flows.html` (Flow B). The ERP's store holds raw material only, so the maintenance store runs fully in Avirat (D-40). This module is **separate from tickets**: a ticket only supplies a part request (ticket number, part, quantity).

## 1. Every stock change is a movement (default)

Stock on hand is never typed. It is the sum of `stock_movements`:

| Movement | Sign | Who | Approval |
|---|---|---|---|
| Opening | + | Go-live import (§8) | — |
| Receipt | + | Store | — |
| Issue | − | Store, against a ticket number | — (D-41: stock drops at issue) |
| Return | + | Store records; stock changes only after approval | **Manager** (D-42) |
| Count adjustment | ± | Store records the count; app proposes the difference | **Manager** |

Movements are append-only, like ticket events. Outputs: the reorder list, stock value, and consumption value (which feeds `kpi.md` §8).

## 2. Part record

| Group | Fields |
|---|---|
| Identity | **Icon Code** (the key: unique, 20004 onwards; new parts get the next number, 21153 onwards), part name, spec (the Excel "Part ID": text, repeats, never a key), OEM code, photo |
| Where it is used | Machine type, or General spare / Pneumatic spare; bin (252 bins today) |
| Stock rules | Unit (Nos, Sets, Kgs, Litres, Meters, Rolls, Packets); category (Mechanical, Electrical or Pneumatic; Consumable or Critical); minimum level; reorder quantity rule; exchange item (default) |
| Money | Unit price and currency ($ or ₹); supplier |

## 3. Receive parts

1. Order placed outside the app (default); parts arrive with a bill or challan.
2. The store checks count and condition; damaged items are not received.
3. Part not in the master → the store adds it (next Icon Code; photo, bin, machine type, category, unit and minimum level required). The manager sees new parts in a daily list (default).
4. Enter the receipt: quantity, supplier, bill number, unit price, currency. **Every receipt is its own entry** (the Excel had one Receive Qty cell per part, so a second receipt overwrote the first).
5. Stock goes up; the part's average price updates (O-8, default average).
6. Requests that were waiting for this part are matched; the requester is alerted.

## 4. Issue parts

1. A part request arrives from a ticket: ticket number, part, quantity. **No ticket number, no issue** (default); jobs are tickets too, so installs are covered.
2. The store finds the part: search by name or Icon Code, scan the bin label, or pick from photos.
3. Not in stock → the ticket shows waiting for material; the part goes on the reorder list straight away.
4. Exchange item → the old part is handed in and goes to the scrap or repair shelf, never back into stock (default).
5. Issue: stock goes down, valued at the part's average price on the day; an issue number is given (it replaces the Excel's issue slip number). The ticket supplies the machine and the technician automatically.
6. The app blocks an issue larger than stock on hand.
7. At or below the minimum level → the reorder list.

## 5. Return unused parts

1. Unused or wrong part comes back; the store checks it is the same part and in good condition.
2. The store marks it **held**: on the shelf, not yet in stock (default).
3. The manager approves or rejects the day's returns from one list (default; approval itself is D-42, no value threshold, D-43).
4. Approved → stock goes up; consumption is reduced in the month of approval; closed months stay as they were.
5. Rejected → scrap or repair, with a reason; stock does not change.
6. Anything issued and not returned counts as used.

## 6. Stock count (default)

1. On a count day the store counts a few bins at a time; every bin at least once a quarter.
2. The store types what is on the shelf without seeing the app's number first.
3. The app compares part by part. No difference → nothing changes.
4. Difference → an adjustment with a reason (miscount, damage, issued without entry) → the manager approves or asks for a recount → stock corrected, logged with who, when and why.

## 7. Reorder

- Same rule as the Excel: stock at or below the minimum level means reorder.
- Reorder quantity = minimum − stock, or 1 when they are equal (the Excel's formula).
- The list updates itself; a receipt takes the part off it.
- 38 parts have no minimum level and 22 have zero, so they never reorder: they are listed for the store to set.

## 8. Go-live from the Excel register (default)

1. Start from `U2_Spare_Parts_Inventory__November_01_2026.xlsm` (1,149 parts).
2. Clean it (`imports.md` §2): trim spaces, fix drag-fill machine names, map machine names to the machine master.
3. The store checks 7 likely duplicates and the missing prices and minimum levels.
4. Add the Excel issues from 1 Nov until go-live. The result is the **opening stock on go-live day**.
5. Copy the 1,146 part photos from the store PC.
6. Freeze the Excel.

## 9. Edge cases (default)

- Asked for more than in stock → the app blocks it; the store recounts the bin.
- No ticket number → the store doesn't issue.
- Wrong part issued → return it (manager approves) and issue the right one.
- Part kept, never returned → counts as used; shows in the manager's parts report.
- Part not in the master → the store adds it; the manager sees new parts.
- Same part entered twice → the store merges them; history kept.
- Price missing → value shown as "no price"; listed for the store.
- Price in $ → the manager sets the month's rate; the ₹ value follows.
- Returned after month end → reduces consumption in the approval month.
- Count doesn't match → adjustment with a reason; logged.
- Minimum level blank or zero → never reorders; listed for the store to set.
