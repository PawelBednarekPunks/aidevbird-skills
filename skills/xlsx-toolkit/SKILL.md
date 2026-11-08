---
name: xlsx-toolkit
description: Create, edit, clean or analyze Excel/CSV files with live formulas and no errors. Use when a spreadsheet (.xlsx, .xlsm, .csv, .tsv) is the input or the deliverable.
---

# XLSX Toolkit

Tools: `openpyxl` for cells, formulas and formatting; `csv`/`pandas` for bulk data. Install only if the import fails.
Script paths are relative to this skill's folder.

Start: `python scripts/inspect_xlsx.py FILE` — sheets, size, first rows, formula and error counts. Plan edits from cell coordinates, not from a text dump.

Rules for every output:
- Formulas, not computed results: `=SUM(B2:B13)`, not the number Python summed. Inputs live in their own labeled cells; formulas reference them (`=B5*(1+$B$2)`, never `=B5*1.05`).
- Use functions every Excel and LibreOffice has: `SUMIFS`, `COUNTIFS`, `INDEX`/`MATCH`, `IFERROR`, `ROUND`. Avoid `XLOOKUP`, `FILTER`, `UNIQUE`, `SORT`, `LET`, `LAMBDA` — sort/filter/dedupe in Python first.
- Guard every division: `=IFERROR(B2/C2,0)`.
- Quote sheet names with spaces: `='Raw Data'!A1`.
- Editing an existing file: keep its layout, styles, names and formulas. Write only into its input cells. Never save a workbook loaded with `data_only=True` (formulas become values). `.xlsm`: load with `keep_vba=True`.
- New file: header row bold and frozen (`ws.freeze_panes = "A2"`), column widths set, one data table per sheet, no merged cells inside data, number formats set (`#,##0.00`, `0.0%` stored as fractions, dates as real dates).
- State assumptions and hardcoded numbers next to them (note cell or comment) with their source.

Verify before handing over:
1. Re-run `inspect_xlsx.py` on the output. `errors` must be empty (exit code 1 means errors).
2. `formulas_without_cached_value` is normal for files written by openpyxl — Excel computes them on open. If LibreOffice is installed, `soffice --headless --convert-to xlsx --outdir checked FILE` and inspect the copy to see real values.
3. Spot-check 2–3 formulas against values you compute by hand — no errors does not mean correct ranges.

Report: file path, sheets, what changed, any assumption the user must confirm.
