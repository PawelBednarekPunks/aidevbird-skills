---
name: invoice-processing
description: Extract invoice data (PDF, image, text) into structured JSON, validate totals, NIP and IBAN, and export to a spreadsheet. Use when processing, checking or booking invoices or receipts.
---

# Invoice Processing

1. Read each document (PDF text, image, email). One invoice per JSON object, in this shape:

```json
{"number":"FV/12/2026","type":"invoice","issue_date":"2026-11-03","sale_date":"2026-11-03",
 "due_date":"2026-11-17","currency":"PLN",
 "seller":{"name":"Acme sp. z o.o.","tax_id":"1234560007","country":"PL"},
 "buyer":{"name":"Jan Kowalski IT","tax_id":"PL9876540016","country":"PL"},
 "lines":[{"description":"Hosting 11/2026","qty":1,"unit_net":100.00,"net":100.00,"vat_rate":"23","vat":23.00}],
 "totals":{"net":100.00,"vat":23.00,"gross":123.00},
 "iban":"PL61109010140000071219812874","category":null,"notes":[]}
```

- `type`: `invoice` | `correction` | `proforma` | `receipt`. Corrections keep negative amounts.
- `vat_rate`: a number as text, or `zw` / `np` / `oo` (exempt, not taxable, reverse charge).
- Copy values exactly as printed. Never guess a missing field — set `null` and add a note.
- Dates `YYYY-MM-DD`, amounts as numbers with a dot.

2. Run `python scripts/validate_invoice.py invoices.json` (path relative to this skill). It checks line math, totals, gross = net + VAT, Polish NIP checksum, IBAN checksum, due date, and duplicates (same seller + number). Fix extraction mistakes and re-run; issues that are really on the document stay as notes for the user — never "fix" the invoice's numbers.

3. Category: use the user's list or chart of accounts if given; otherwise propose short categories (e.g. software, hosting, hardware, travel, marketing, services) and mark them as proposals.

4. Export: one row per invoice (or per line if asked) to CSV or to .xlsx with the `xlsx-toolkit` skill — columns: number, issue_date, due_date, seller, seller_tax_id, net, vat, gross, currency, category, status, notes.

Hard rules:
- Foreign-currency invoices: keep the original currency. Convert only if the user asks, and then state the rate, its date and source.
- Never pay, send or upload anything. Tax treatment is a hint for the accountant, not advice.
- Report: count processed, count with issues, and each issue in one line.
