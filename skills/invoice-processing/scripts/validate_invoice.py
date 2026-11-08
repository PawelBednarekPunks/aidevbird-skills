#!/usr/bin/env python3
"""Validate extracted invoice JSON: arithmetic, tax IDs, IBAN, dates, duplicates.

Usage: python validate_invoice.py invoice.json [more.json ...]
       (a file may hold one invoice object or a list of them)

Prints one compact JSON line per invoice: {"number", "status", "issues"}.
Exit code 1 if any invoice has issues, 2 on unreadable input.
"""
import json
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

TOLERANCE = Decimal("0.02")
NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


def dec(value):
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def nip_ok(raw):
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 10:
        return False
    check = sum(int(d) * w for d, w in zip(digits, NIP_WEIGHTS)) % 11
    return check != 10 and check == int(digits[9])


def iban_ok(raw):
    iban = re.sub(r"\s", "", raw).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", iban):
        return False
    moved = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def tax_id_issue(party, label):
    tax_id = (party or {}).get("tax_id")
    if not tax_id:
        return f"{label}.tax_id missing"
    country = (party.get("country") or "PL").upper()
    compact = re.sub(r"[\s-]", "", tax_id).upper()
    if compact.startswith(country):
        compact = compact[len(country):]
    if country == "PL" and not nip_ok(compact):
        return f"{label}.tax_id {tax_id} fails NIP checksum"
    return None


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def check_lines(lines, label, issues):
    net_sum = vat_sum = Decimal(0)
    for i, line in enumerate(lines or [], 1):
        qty, price, net = dec(line.get("qty")), dec(line.get("unit_net")), dec(line.get("net"))
        vat, rate = dec(line.get("vat", 0)), str(line.get("vat_rate", "")).strip().lower()
        if net is None:
            issues.append(f"{label} {i}: net missing")
            continue
        if qty is not None and price is not None and abs(qty * price - net) > TOLERANCE:
            issues.append(f"{label} {i}: qty*unit_net={qty * price} != net {net}")
        if rate.rstrip("%").isdigit() and vat is not None:
            expected = (net * Decimal(rate.rstrip("%")) / 100).quantize(Decimal("0.01"))
            if abs(expected - vat) > TOLERANCE:
                issues.append(f"{label} {i}: vat {vat} != {expected} at {rate}")
        net_sum += net
        vat_sum += vat or 0
    return net_sum, vat_sum


def validate(inv):
    issues = []
    kind = inv.get("type", "invoice")
    required = ["number", "issue_date", "seller", "totals"]
    if kind in ("invoice", "receipt", "proforma", "final"):
        required.append("lines")
    if kind != "receipt":
        required.append("buyer")
    for key in required:
        if not inv.get(key):
            issues.append(f"{key} missing")
    parties = [(inv.get("seller"), "seller")]
    if inv.get("type") != "receipt":  # a receipt usually has no buyer tax ID
        parties.append((inv.get("buyer"), "buyer"))
    for party, label in parties:
        issue = tax_id_issue(party, label)
        if issue:
            issues.append(issue)

    net_sum, vat_sum = check_lines(inv.get("lines"), "line", issues)
    if kind == "correction":  # totals are the difference: after minus before
        before_net, before_vat = check_lines(inv.get("lines_before"), "before line", issues)
        net_sum, vat_sum = net_sum - before_net, vat_sum - before_vat
    compare_lines = kind not in ("advance", "final")  # advances and settlements differ from line sums

    totals = inv.get("totals") or {}
    t_net, t_vat, t_gross = dec(totals.get("net")), dec(totals.get("vat", 0)), dec(totals.get("gross"))
    if compare_lines and t_net is not None and abs(t_net - net_sum) > TOLERANCE:
        issues.append(f"totals.net {t_net} != lines {net_sum}")
    if compare_lines and t_vat is not None and abs(t_vat - vat_sum) > TOLERANCE:
        issues.append(f"totals.vat {t_vat} != lines {vat_sum}")
    if None not in (t_net, t_vat, t_gross) and abs(t_net + t_vat - t_gross) > TOLERANCE:
        issues.append(f"totals.gross {t_gross} != net+vat {t_net + t_vat}")

    issued, due = parse_date(inv.get("issue_date")), parse_date(inv.get("due_date"))
    if inv.get("issue_date") and not issued:
        issues.append("issue_date not YYYY-MM-DD")
    if issued and due and due < issued:
        issues.append("due_date before issue_date")
    if inv.get("iban") and not iban_ok(inv["iban"]):
        issues.append("iban fails checksum")
    return issues


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(2)
    invoices = []
    for path in sys.argv[1:]:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps({"file": path, "error": str(exc)}))
            sys.exit(2)
        invoices.extend(data if isinstance(data, list) else [data])

    seen, failed = set(), False
    for inv in invoices:
        issues = validate(inv)
        key = (re.sub(r"\D", "", str((inv.get("seller") or {}).get("tax_id", ""))), inv.get("number"))
        if key in seen:
            issues.append("duplicate: same seller tax_id and number")
        seen.add(key)
        failed = failed or bool(issues)
        print(json.dumps({"number": inv.get("number"), "status": "issues" if issues else "ok",
                          "issues": issues}, ensure_ascii=False, separators=(",", ":")))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
