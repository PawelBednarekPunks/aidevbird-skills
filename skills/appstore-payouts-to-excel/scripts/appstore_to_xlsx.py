#!/usr/bin/env python3
"""Turn App Store Connect financial or sales reports into one Excel workbook.

Usage:
  python appstore_to_xlsx.py OUT.xlsx REPORT [REPORT ...] [--currency PLN] [--nbp YYYY-MM-DD]
                             [--rates rates.json]

REPORT: tab-separated .txt/.tsv/.csv, optionally .gz — financial reports
(Extended Partner Share) or summary sales reports (Units x Developer Proceeds).
--nbp DATE   fetch NBP table A mid rates from the last business day BEFORE DATE
--rates FILE JSON {"USD": 3.65, ...}: rates to --currency (default PLN)

Sheets: Data (one row per report line), Summary (by currency, by country, by app;
SUMIFS formulas), Rates (editable; converted totals follow them).
Prints one JSON line with row counts, totals per currency and warnings.
"""
import csv
import gzip
import io
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font
except ImportError:
    print(json.dumps({"error": "openpyxl missing: pip install openpyxl"}))
    sys.exit(2)

# report type -> column names (first match wins)
COLUMNS = {
    "financial": {
        "amount": ["Extended Partner Share"], "currency": ["Partner Share Currency"],
        "units": ["Quantity"], "country": ["Country Of Sale"], "title": ["Title"],
        "sku": ["Vendor Identifier"], "start": ["Start Date"], "end": ["End Date"],
        "kind": ["Sales or Return"], "type": ["Product Type Identifier"],
    },
    "sales": {
        "unit_amount": ["Developer Proceeds"], "currency": ["Currency of Proceeds"],
        "units": ["Units"], "country": ["Country Code"], "title": ["Title"],
        "sku": ["SKU"], "start": ["Begin Date"], "end": ["End Date"],
        "type": ["Product Type Identifier"],
    },
}
DATA_HEADERS = ["Report", "Start", "End", "App", "SKU", "Type", "Country", "Units", "Currency", "Proceeds"]


def num(value):
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except InvalidOperation:
        return None


def parse_date(value):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def read_rows(path):
    raw = gzip.open(path, "rb").read() if path.endswith(".gz") else open(path, "rb").read()
    text = raw.decode("utf-8-sig", errors="replace")
    delimiter = "\t" if "\t" in text.split("\n", 1)[0] else ","
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def detect(header):
    for kind, cols in COLUMNS.items():
        key = "amount" if kind == "financial" else "unit_amount"
        if any(name in header for name in cols[key]):
            return kind, {f: next((header.index(n) for n in names if n in header), None)
                          for f, names in cols.items()}
    return None, None


def parse_report(path, warnings):
    rows = read_rows(path)
    start = next((i for i, r in enumerate(rows) if detect(r)[0]), None)
    if start is None:
        warnings.append(f"{path}: no known App Store header, skipped")
        return []
    kind, idx = detect(rows[start])
    get = lambda r, f: r[idx[f]].strip() if idx.get(f) is not None and idx[f] < len(r) else ""
    out = []
    for r in rows[start + 1:]:
        if not r or not any(c.strip() for c in r) or r[0].startswith("Total"):
            continue
        units = num(get(r, "units")) or Decimal(0)
        if kind == "financial":
            amount = num(get(r, "amount"))
            refund = get(r, "kind").upper() == "R"
        else:
            per_unit = num(get(r, "unit_amount"))
            amount = None if per_unit is None else abs(per_unit) * abs(units)
            refund = units < 0 or (per_unit is not None and per_unit < 0)
        if amount is None:
            continue  # footer or summary row
        if refund:
            amount, units = -abs(amount), -abs(units)
        out.append([kind, parse_date(get(r, "start")), parse_date(get(r, "end")), get(r, "title"),
                    get(r, "sku"), get(r, "type"), get(r, "country"), float(units),
                    get(r, "currency").upper(), float(amount)])
    if not out:
        warnings.append(f"{path}: header found but no data rows")
    return out


def nbp_rates(before):
    """Table A mid rates from the last business day strictly before `before`."""
    end = before - timedelta(days=1)
    url = (f"https://api.nbp.pl/api/exchangerates/tables/a/"
           f"{end - timedelta(days=10):%Y-%m-%d}/{end:%Y-%m-%d}/?format=json")
    with urllib.request.urlopen(url, timeout=15) as resp:
        table = json.load(resp)[-1]
    return table["effectiveDate"], {r["code"]: r["mid"] for r in table["rates"]}


def build(out_path, data, target, rates, rate_note):
    wb = Workbook()
    bold = Font(bold=True)
    ws = wb.active
    ws.title = "Data"
    ws.append(DATA_HEADERS)
    for row in sorted(data, key=lambda r: (r[1] or date.min, r[3], r[6])):
        ws.append(row)
    n = ws.max_row
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=3):
        for c in row:
            c.number_format = "yyyy-mm-dd"
    for c in ws["J"][1:]:
        c.number_format = "#,##0.00"
    for col, width in zip("ABCDEFGHIJ", (10, 11, 11, 28, 18, 7, 8, 8, 9, 12)):
        ws.column_dimensions[col].width = width

    currencies = sorted({r[8] for r in data})
    rs = wb.create_sheet("Rates")
    rs.append(["Currency", f"Rate to {target}", "Source"])
    for cur in currencies:
        rate = 1 if cur == target else rates.get(cur)
        rs.append([cur, rate, "same currency" if cur == target else (rate_note if rate else "MISSING - fill in")])
    rs.column_dimensions["C"].width = 40

    sm = wb.create_sheet("Summary", 0)
    amount, cur_col = f"Data!$J$2:$J${n}", f"Data!$I$2:$I${n}"
    sm.append(["By currency", "Proceeds", f"Proceeds {target}"])
    first = sm.max_row + 1
    for i, cur in enumerate(currencies):
        r = sm.max_row + 1
        sm.append([cur, f'=SUMIFS({amount},{cur_col},A{r})',
                   f"=IFERROR(B{r}*INDEX(Rates!$B:$B,MATCH(A{r},Rates!$A:$A,0)),0)"])
    last = sm.max_row
    sm.append([f"Total {target}", None, f"=SUM(C{first}:C{last})"])
    total_row = sm.max_row
    for title, col in (("By country", "G"), ("By app", "D")):
        sm.append([])
        sm.append([title, "Currency", "Proceeds", f"Proceeds {target}"])
        header_row = sm.max_row
        keys = sorted({(r[6] if col == "G" else r[3], r[8]) for r in data})
        for key, cur in keys:
            r = sm.max_row + 1
            sm.append([key, cur, f'=SUMIFS({amount},Data!${col}$2:${col}${n},A{r},{cur_col},B{r})',
                       f"=IFERROR(C{r}*INDEX(Rates!$B:$B,MATCH(B{r},Rates!$A:$A,0)),0)"])
        sm.cell(header_row, 1).font = bold
    for r in (1, total_row):
        for c in sm[r]:
            c.font = bold
    for row in sm.iter_rows(min_col=2, max_col=4):
        for c in row:
            c.number_format = "#,##0.00"
    sm.column_dimensions["A"].width = 28
    for col in "BCD":
        sm.column_dimensions[col].width = 16
    for sheet in (ws, rs):
        sheet.freeze_panes = "A2"
        for c in sheet[1]:
            c.font = bold
    wb.save(out_path)
    return currencies


def main():
    args = sys.argv[1:]
    opts = {}
    for flag in ("--currency", "--nbp", "--rates"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if len(args) < 2:
        print(__doc__.strip())
        sys.exit(2)
    out_path, reports = args[0], args[1:]
    target = opts.get("--currency", "PLN").upper()
    warnings, data = [], []
    for path in reports:
        try:
            data.extend(parse_report(path, warnings))
        except OSError as exc:
            warnings.append(f"{path}: {exc}")
    if not data:
        print(json.dumps({"error": "no data rows", "warnings": warnings}))
        sys.exit(2)
    if len({r[0] for r in data}) > 1:
        warnings.append("financial and sales reports mixed - same sales may be counted twice")

    rates, note = {}, ""
    if "--rates" in opts:
        with open(opts["--rates"], encoding="utf-8") as f:
            rates = {k.upper(): v for k, v in json.load(f).items()}
        note = f"from {opts['--rates']}"
    if "--nbp" in opts:
        if target != "PLN":
            warnings.append("--nbp gives rates to PLN; use --currency PLN")
        try:
            day, rates = nbp_rates(date.fromisoformat(opts["--nbp"]))
            note = f"NBP table A, {day}"
        except Exception as exc:
            warnings.append(f"NBP fetch failed: {exc}")

    currencies = build(out_path, data, target, rates, note)
    missing = [c for c in currencies if c != target and c not in rates]
    if missing:
        warnings.append(f"no rate for {', '.join(missing)} - fill Rates sheet")
    totals = {}
    for r in data:
        totals[r[8]] = round(totals.get(r[8], 0) + r[9], 2)
    print(json.dumps({"out": out_path, "rows": len(data), "totals": totals,
                      "rates": note or None, "warnings": warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
