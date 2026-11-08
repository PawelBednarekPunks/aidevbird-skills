---
name: ksef-invoice
description: Build, validate and read Polish KSeF e-invoices (FA(3) XML) — invoices, corrections, advances and final settlements — against the official schema. Use for e-faktura, KSeF, korekta, zaliczka or a rejected invoice.
---

# KSeF Invoice (FA(3))

Script: `python scripts/ksef_fa3.py build|validate|read ...` (relative to this skill). Needs `pip install lxml`; the official XSD is fetched once from crd.gov.pl. Answer in Polish unless the user writes otherwise.

Seller data: if `ksef-firma.json` exists in the working folder, take `seller` and `iban` from it. If not, ask once and offer to save it there. Invoice number: propose the next one from existing XML files in the folder (`read` them), let the user confirm.

Pick `type` — examples in `examples/<type>.json`:
- `invoice` — normal invoice: `lines[]`.
- `correction` — korekta: `corrects` {number, issue_date, ksef_number if it was in KSeF}, `lines_before` (original lines), `lines` (correct state; `[]` = full cancel), `reason`, `correction_effect` (1 original date, 2 correction date — default, 3 other). Easiest: `read` the original XML, copy its lines to `lines_before`, edit `lines`.
- `advance` — zaliczka: `order_lines` (whole order), `paid` (gross received), `paid_date`. The script splits the payment over VAT rates.
- `final` — rozliczenie after advances: `lines` (whole order), `advances[]` {number, ksef_number, by_rate}. Get `by_rate` from `read` of each advance XML.

Common fields: `seller` {name, tax_id, address.line1/line2}; `buyer` (PL NIP, EU `country`+VAT no., other `country`+ID, private person: no `tax_id`); `lines[]` {description, qty, unit, unit_net or net, vat_rate: `23` `8` `5` `0 KR` `0 WDT` `0 EX` `zw` `np I` `np II` `oo`}; optional `sale_date`, `due_date`, `iban`, `place`, `currency`+`fx_rate`, `exemption_basis` (required for `zw`), `split_payment`, `cash_method`, `self_billing`.

Steps:
1. Fill the JSON. Ask for anything missing — never invent a NIP, number, date, amount or KSeF number.
2. `ksef_fa3.py build invoice.json FV-1-11-2026.xml` (file name = number with `/` → `-`).
3. Show: type, number, buyer, net/VAT/gross per rate (negative for corrections), file path, and the next step: upload the XML in their KSeF app or accounting software.

Validate any XML: `ksef_fa3.py validate file.xml` — official XSD, sums vs lines, VAT, P_15, NIP. Explain each issue in plain Polish with the fix.
Read: `ksef_fa3.py read file.xml` → JSON (same shape as input). For many files, export with `invoice-processing` / `xlsx-toolkit`.

Hard rules:
- Not supported: correcting an advance (KOR_ZAL) or a final invoice (KOR_ROZ), margin schemes, new vehicles, JST/VAT groups, attachments. Say so.
- Never send to KSeF, never ask for or handle a KSeF token or certificate.
- VAT rate, exemption basis, reverse charge and correction date are the user's or accountant's decision — flag doubts, don't decide.
