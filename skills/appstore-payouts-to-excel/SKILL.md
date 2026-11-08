---
name: appstore-payouts-to-excel
description: Turn App Store Connect financial or sales reports into an Excel workbook with proceeds by currency, country and app, converted at NBP or given rates. Use for App Store income, payouts or bookkeeping.
---

# App Store Payouts to Excel

Input — ask the user to download from App Store Connect (never sign in for them):
- **Payments and Financial Reports** → one month, all regions (`.txt`, tab-separated). Use these for bookkeeping: they match what Apple pays.
- **Sales and Trends** → Summary Sales report (`.txt.gz`). Use only for quick estimates — not final amounts.
Use one kind per period; mixing both counts the same sales twice.

Run (path relative to this skill):

```bash
python scripts/appstore_to_xlsx.py payouts-2026-10.xlsx reports/*.txt --nbp 2026-11-05
```

- `--nbp DATE`: NBP table A mid rates from the last business day before DATE (the common Polish rule for income in foreign currency; DATE = the income date the accountant uses, usually the invoice or payment date).
- `--rates rates.json --currency EUR`: own rates (`{"USD": 0.86}`) to any currency.
- No rate flag: amounts stay in original currencies; the Rates sheet lists what to fill in.

The script prints one JSON line: `rows`, `totals` per currency, `rates`, `warnings`. Act on every warning (unknown file, missing rate, mixed report kinds).

Workbook:
- **Summary**: proceeds by currency, by country, by app — `SUMIFS` formulas, so they update when Data or Rates change.
- **Data**: one row per report line; refunds are negative.
- **Rates**: one rate per currency with its source. Edit here, not in Summary.

Check before handing over:
1. Per-currency `totals` match the report footers (`Total_Amount`) or the payment shown in App Store Connect. If not, say which currency differs.
2. Run `xlsx-toolkit`'s `inspect_xlsx.py` on the output: no errors.

Report: totals per currency, total in the target currency with the rate date, and warnings.
Hard rules: never alter report numbers; tax and VAT treatment (e.g. Apple's self-billing, reverse charge) is for the user's accountant — mention it, don't decide it.
