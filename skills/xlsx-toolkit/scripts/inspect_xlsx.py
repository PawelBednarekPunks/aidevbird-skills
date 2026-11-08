#!/usr/bin/env python3
"""Inspect an .xlsx/.xlsm workbook and print a compact JSON report.

Usage: python inspect_xlsx.py FILE [--rows N]

Reports per sheet: size, first rows, formula count, formulas with no cached
value (file never recalculated), cells holding error values, merged ranges.
Exit code 1 when error values are found, 2 when the file cannot be read.
"""
import json
import sys

try:
    from openpyxl import load_workbook
except ImportError:
    print(json.dumps({"error": "openpyxl missing: pip install openpyxl"}))
    sys.exit(2)

ERRORS = {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "#SPILL!", "#CALC!"}
MAX_LIST = 20


def cell_text(value):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= 40 else text[:37] + "..."


def inspect(path, preview_rows):
    keep_vba = path.lower().endswith(".xlsm")
    formulas_wb = load_workbook(path, keep_vba=keep_vba)
    values_wb = load_workbook(path, data_only=True, keep_vba=keep_vba)
    report = {"file": path, "sheets": [], "external_links": len(formulas_wb._external_links)}
    total_errors = 0

    for ws in formulas_wb.worksheets:
        vs = values_wb[ws.title]
        formulas, uncached, errors = 0, [], []
        for row in ws.iter_rows():
            for cell in row:
                cached = vs[cell.coordinate].value
                if cell.data_type == "f":
                    formulas += 1
                    if cached is None and len(uncached) < MAX_LIST:
                        uncached.append(cell.coordinate)
                if isinstance(cached, str) and cached.strip() in ERRORS:
                    errors.append(f"{cell.coordinate}={cached.strip()}")
        total_errors += len(errors)
        report["sheets"].append({
            "name": ws.title,
            "dimensions": ws.dimensions,
            "max_row": ws.max_row,
            "max_column": ws.max_column,
            "preview": [[cell_text(v) for v in row]
                        for row in vs.iter_rows(max_row=min(preview_rows, vs.max_row), values_only=True)],
            "formulas": formulas,
            "formulas_without_cached_value": uncached,
            "errors": errors[:MAX_LIST],
            "error_count": len(errors),
            "merged_ranges": len(ws.merged_cells.ranges),
        })

    report["total_errors"] = total_errors
    report["status"] = "errors_found" if total_errors else "ok"
    return report


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__.strip())
        sys.exit(2)
    rows = 5
    if "--rows" in args:
        i = args.index("--rows")
        rows = int(args[i + 1])
        del args[i:i + 2]
    try:
        report = inspect(args[0], rows)
    except Exception as exc:  # unreadable or not a workbook
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(2)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), default=str))
    sys.exit(1 if report["total_errors"] else 0)


if __name__ == "__main__":
    main()
