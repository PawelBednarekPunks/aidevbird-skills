#!/usr/bin/env python3
"""Build, validate and read Polish KSeF e-invoices in the FA(3) structure.

Usage:
  python ksef_fa3.py build INVOICE.json OUT.xml   JSON (see SKILL.md) -> FA(3) XML, then validate
  python ksef_fa3.py validate FILE.xml            XSD + arithmetic + NIP checks
  python ksef_fa3.py read FILE.xml                FA(3) XML -> invoice JSON

Invoice types ("type" in JSON): invoice (VAT), correction (KOR),
advance (ZAL), final (ROZ, settles earlier advances).
The official XSD files are downloaded once from crd.gov.pl into
~/.cache/ksef-fa3 (override with KSEF_SCHEMA_DIR). Needs: pip install lxml
Prints one JSON line. Exit 0 ok, 1 invoice issues, 2 usage or setup error.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    print(json.dumps({"error": "lxml missing: pip install lxml"}))
    sys.exit(2)

NS = "http://crd.gov.pl/wzor/2025/06/25/13775/"
DEFS = "http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/DefinicjeTypy/"
SCHEMAS = {
    "schemat.xsd": NS + "schemat.xsd",
    "StrukturyDanych_v10-0E.xsd": DEFS + "StrukturyDanych_v10-0E.xsd",
    "ElementarneTypyDanych_v10-0E.xsd": DEFS + "ElementarneTypyDanych_v10-0E.xsd",
    "KodyKrajow_v10-0E.xsd": DEFS + "KodyKrajow_v10-0E.xsd",
}
F = {"f": NS}
CENT = Decimal("0.01")
NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
KINDS = {"invoice": "VAT", "correction": "KOR", "advance": "ZAL", "final": "ROZ"}
EU = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE",
      "IT", "LT", "LU", "LV", "MT", "NL", "PT", "RO", "SE", "SI", "SK", "XI"}

# vat_rate -> (net field, vat field, vat-in-PLN field, percent)
RATE_FIELDS = {
    "23": ("P_13_1", "P_14_1", "P_14_1W", 23), "22": ("P_13_1", "P_14_1", "P_14_1W", 22),
    "8": ("P_13_2", "P_14_2", "P_14_2W", 8), "7": ("P_13_2", "P_14_2", "P_14_2W", 7),
    "5": ("P_13_3", "P_14_3", "P_14_3W", 5),
    "0 KR": ("P_13_6_1", None, None, 0), "0 WDT": ("P_13_6_2", None, None, 0),
    "0 EX": ("P_13_6_3", None, None, 0), "zw": ("P_13_7", None, None, 0),
    "np I": ("P_13_8", None, None, 0), "np II": ("P_13_9", None, None, 0),
    "oo": ("P_13_10", None, None, 0),
}
SUM_ORDER = ["P_13_1", "P_14_1", "P_14_1W", "P_13_2", "P_14_2", "P_14_2W", "P_13_3", "P_14_3",
             "P_14_3W", "P_13_6_1", "P_13_6_2", "P_13_6_3", "P_13_7", "P_13_8", "P_13_9", "P_13_10"]
PAIRS = {"P_13_1": "P_14_1", "P_13_2": "P_14_2", "P_13_3": "P_14_3"}


class InvoiceError(Exception):
    pass


def money(value):
    return Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def fmt(value):
    text = format(value.normalize(), "f") if isinstance(value, Decimal) else str(value)
    return text if text not in ("-0", "") else "0"


def digits(value):
    return re.sub(r"\D", "", str(value or ""))


def nip_ok(nip):
    if len(nip) != 10:
        return False
    check = sum(int(d) * w for d, w in zip(nip, NIP_WEIGHTS)) % 11
    return check != 10 and check == int(nip[9])


def schema():
    folder = Path(os.environ.get("KSEF_SCHEMA_DIR", Path.home() / ".cache" / "ksef-fa3"))
    folder.mkdir(parents=True, exist_ok=True)
    for name, url in SCHEMAS.items():
        target = folder / name
        if not target.exists():
            with urllib.request.urlopen(url, timeout=30) as resp:
                target.write_bytes(resp.read())

    # resolve crd.gov.pl imports to the cached copies instead of the network
    class Local(etree.Resolver):
        def resolve(self, url, pubid, context):
            name = url.rsplit("/", 1)[-1]
            if name in SCHEMAS:
                return self.resolve_filename(str(folder / name), context)
            return None
    parser = etree.XMLParser()
    parser.resolvers.add(Local())
    return etree.XMLSchema(etree.parse(str(folder / "schemat.xsd"), parser))


def sub(parent, tag, text=None, **attrs):
    el = etree.SubElement(parent, f"{{{NS}}}{tag}", **attrs)
    if text is not None:
        el.text = fmt(text)
    return el


def address(parent, party):
    addr = party.get("address") or {}
    if not addr.get("line1"):
        return
    a = sub(parent, "Adres")
    sub(a, "KodKraju", (party.get("country") or "PL").upper())
    sub(a, "AdresL1", addr["line1"])
    if addr.get("line2"):
        sub(a, "AdresL2", addr["line2"])


def buyer_ids(parent, buyer):
    ids = sub(parent, "DaneIdentyfikacyjne")
    country = (buyer.get("country") or "PL").upper()
    raw = re.sub(r"[\s-]", "", str(buyer.get("tax_id") or "")).upper()
    prefix = "EL" if country == "GR" else country
    if not raw:
        sub(ids, "BrakID", 1)
    elif country == "PL":
        sub(ids, "NIP", digits(raw))
    elif prefix in EU:
        sub(ids, "KodUE", prefix)
        sub(ids, "NrVatUE", raw[len(prefix):] if raw.startswith(prefix) else raw)
    else:
        sub(ids, "KodKraju", country)
        sub(ids, "NrID", raw)
    sub(ids, "Nazwa", buyer["name"])


def norm_rate(rate, where):
    rate = str(rate if rate is not None else "").strip()
    rate = rate.lower() if rate.lower() in ("zw", "oo") else rate.rstrip("%")
    if rate not in RATE_FIELDS:
        raise InvoiceError(f"{where}: vat_rate {rate!r} not supported; use one of {list(RATE_FIELDS)}")
    return rate


def parse_lines(lines, where):
    rows = []
    for i, line in enumerate(lines or [], 1):
        rate = norm_rate(line.get("vat_rate"), f"{where} {i}")
        qty = Decimal(str(line.get("qty", 1)))
        unit = Decimal(str(line["unit_net"])) if line.get("unit_net") is not None else None
        if line.get("net") is None and unit is None:
            raise InvoiceError(f"{where} {i}: needs net or unit_net")
        net = money(line["net"]) if line.get("net") is not None else money(qty * unit)
        rows.append({"line": line, "rate": rate, "qty": qty, "unit": unit, "net": net})
    return rows


def by_rate(rows):
    nets = {}
    for r in rows:
        nets[r["rate"]] = nets.get(r["rate"], Decimal(0)) + r["net"]
    return {rate: {"net": net, "vat": money(net * RATE_FIELDS[rate][3] / 100)} for rate, net in nets.items()}


def advance_split(order_rows, paid):
    """Split a gross advance payment over the order's VAT rates (art. 106f ust. 1 pkt 3)."""
    order = by_rate(order_rows)
    total = sum(v["net"] + v["vat"] for v in order.values())
    if total <= 0:
        raise InvoiceError("order total must be positive")
    if paid > total:
        raise InvoiceError(f"advance {paid} exceeds order gross {total}")
    out, left = {}, paid
    rates = list(order)
    for i, rate in enumerate(rates):
        gross = left if i == len(rates) - 1 else money(paid * (order[rate]["net"] + order[rate]["vat"]) / total)
        left -= gross
        pct = RATE_FIELDS[rate][3]
        vat = money(gross * pct / (100 + pct))
        out[rate] = {"net": gross - vat, "vat": vat}
    return out, total


def rate_sums(parts, currency, fx):
    """{rate: {net, vat}} -> {P_13_x/P_14_x/P_14_xW: amount}."""
    sums = {}
    for rate, v in parts.items():
        net_f, vat_f, vat_pln_f, _ = RATE_FIELDS[rate]
        sums[net_f] = sums.get(net_f, Decimal(0)) + v["net"]
        if vat_f:
            sums[vat_f] = sums.get(vat_f, Decimal(0)) + v["vat"]
            if currency != "PLN" and v["vat"]:
                if fx is None:
                    raise InvoiceError("foreign-currency invoice with VAT needs fx_rate (PLN per unit)")
                sums[vat_pln_f] = sums.get(vat_pln_f, Decimal(0)) + money(v["vat"] * fx)
    return sums


def subtract(a, b):
    out = {}
    for rate in list(a) + [r for r in b if r not in a]:
        x, y = a.get(rate, {"net": 0, "vat": 0}), b.get(rate, {"net": 0, "vat": 0})
        out[rate] = {"net": Decimal(x["net"]) - Decimal(y["net"]), "vat": Decimal(x["vat"]) - Decimal(y["vat"])}
    return out


def ksef_ref(parent, ref, yes_tag, number_tag, no_tag, plain_number_tag=None):
    if ref.get("ksef_number"):
        if yes_tag:
            sub(parent, yes_tag, 1)
        sub(parent, number_tag, ref["ksef_number"])
    else:
        sub(parent, no_tag, 1)
        if plain_number_tag:
            sub(parent, plain_number_tag, ref["number"])


def add_rows(fa, rows, start=1, before=False):
    for n, r in enumerate(rows, start):
        row = sub(fa, "FaWiersz")
        sub(row, "NrWierszaFa", n)
        sub(row, "P_7", r["line"]["description"])
        sub(row, "P_8A", r["line"].get("unit", "szt."))
        sub(row, "P_8B", r["qty"])
        if r["unit"] is not None:
            sub(row, "P_9A", r["unit"])
        sub(row, "P_11", f"{r['net']:.2f}")
        sub(row, "P_12", r["rate"])
        if before:
            sub(row, "StanPrzed", 1)
    return start + len(rows)


def build(inv):
    kind = inv.get("type", "invoice")
    if kind not in KINDS:
        raise InvoiceError(f"type {kind!r} not supported; use one of {list(KINDS)}")
    for key in ("number", "issue_date", "seller", "buyer"):
        if not inv.get(key):
            raise InvoiceError(f"{key} missing")
    seller, buyer = inv["seller"], inv["buyer"]
    if not nip_ok(digits(seller.get("tax_id"))):
        raise InvoiceError(f"seller NIP {seller.get('tax_id')} fails checksum")
    if (buyer.get("country") or "PL").upper() == "PL" and buyer.get("tax_id") \
            and not nip_ok(digits(buyer["tax_id"])):
        raise InvoiceError(f"buyer NIP {buyer['tax_id']} fails checksum")
    if not (seller.get("address") or {}).get("line1"):
        raise InvoiceError("seller.address.line1 missing")
    currency = (inv.get("currency") or "PLN").upper()
    fx = Decimal(str(inv["fx_rate"])) if inv.get("fx_rate") else None

    rows = parse_lines(inv.get("lines"), "line")
    before_rows, order_rows, order_total = [], [], None
    if kind == "invoice":
        if not rows:
            raise InvoiceError("lines missing")
        parts = by_rate(rows)
    elif kind == "correction":
        corr = inv.get("corrects") or {}
        if not (corr.get("number") and corr.get("issue_date")):
            raise InvoiceError("correction needs corrects.number and corrects.issue_date")
        before_rows = parse_lines(inv.get("lines_before"), "lines_before")
        if not before_rows:
            raise InvoiceError("correction needs lines_before (the corrected invoice's lines)")
        parts = subtract(by_rate(rows), by_rate(before_rows))
    elif kind == "advance":
        order_rows = parse_lines(inv.get("order_lines"), "order_line")
        if not order_rows or inv.get("paid") is None:
            raise InvoiceError("advance needs order_lines and paid (gross amount received)")
        parts, order_total = advance_split(order_rows, money(inv["paid"]))
    else:  # final
        if not rows or not inv.get("advances"):
            raise InvoiceError("final invoice needs lines (whole order) and advances")
        parts = by_rate(rows)
        for i, adv in enumerate(inv["advances"], 1):
            if not adv.get("number") or not adv.get("by_rate"):
                raise InvoiceError(f"advance {i}: needs number and by_rate (from `read` of the advance)")
            taken = {norm_rate(r, f"advance {i}"): {"net": money(v["net"]), "vat": money(v.get("vat", 0))}
                     for r, v in adv["by_rate"].items()}
            parts = subtract(parts, taken)
    rates_used = {r["rate"] for r in rows + before_rows + order_rows}
    if "zw" in rates_used and not inv.get("exemption_basis"):
        raise InvoiceError("vat_rate zw needs exemption_basis (e.g. 'art. 113 ust. 1 ustawy o VAT')")
    sums = rate_sums(parts, currency, fx)
    gross = sum(v for k, v in sums.items() if not k.endswith("W"))
    if kind == "advance" and gross != money(inv["paid"]):
        raise InvoiceError(f"internal: advance split {gross} != paid {inv['paid']}")

    root = etree.Element(f"{{{NS}}}Faktura", nsmap={None: NS})
    head = sub(root, "Naglowek")
    sub(head, "KodFormularza", "FA", kodSystemowy="FA (3)", wersjaSchemy="1-0E")
    sub(head, "WariantFormularza", 3)
    sub(head, "DataWytworzeniaFa", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    sub(head, "SystemInfo", "aidevbird ksef-invoice")

    p1 = sub(root, "Podmiot1")
    ids = sub(p1, "DaneIdentyfikacyjne")
    sub(ids, "NIP", digits(seller["tax_id"]))
    sub(ids, "Nazwa", seller["name"])
    address(p1, {**seller, "country": "PL"})
    if seller.get("email") or seller.get("phone"):
        contact = sub(p1, "DaneKontaktowe")
        if seller.get("email"):
            sub(contact, "Email", seller["email"])
        if seller.get("phone"):
            sub(contact, "Telefon", seller["phone"])

    p2 = sub(root, "Podmiot2")
    buyer_ids(p2, buyer)
    address(p2, buyer)
    sub(p2, "JST", 2)
    sub(p2, "GV", 2)

    fa = sub(root, "Fa")
    sub(fa, "KodWaluty", currency)
    sub(fa, "P_1", inv["issue_date"])
    if inv.get("place"):
        sub(fa, "P_1M", inv["place"])
    sub(fa, "P_2", inv["number"])
    event_date = inv.get("paid_date") if kind == "advance" else inv.get("sale_date")
    if event_date and event_date != inv["issue_date"]:
        sub(fa, "P_6", event_date)
    for field in SUM_ORDER:
        if field in sums:
            sub(fa, field, f"{sums[field]:.2f}")
    sub(fa, "P_15", f"{gross:.2f}")
    notes = sub(fa, "Adnotacje")
    sub(notes, "P_16", 1 if inv.get("cash_method") else 2)
    sub(notes, "P_17", 1 if inv.get("self_billing") else 2)
    sub(notes, "P_18", 1 if "oo" in rates_used else 2)
    sub(notes, "P_18A", 1 if inv.get("split_payment") else 2)
    exemption = sub(notes, "Zwolnienie")
    if "zw" in rates_used:
        sub(exemption, "P_19", 1)
        sub(exemption, "P_19A", inv["exemption_basis"])
    else:
        sub(exemption, "P_19N", 1)
    sub(sub(notes, "NoweSrodkiTransportu"), "P_22N", 1)
    sub(notes, "P_23", 2)  # not a simplified triangular (art. 135) invoice
    sub(sub(notes, "PMarzy"), "P_PMarzyN", 1)
    sub(fa, "RodzajFaktury", KINDS[kind])

    if kind == "correction":
        corr = inv["corrects"]
        if inv.get("reason"):
            sub(fa, "PrzyczynaKorekty", inv["reason"])
        sub(fa, "TypKorekty", inv.get("correction_effect", 2))
        ref = sub(fa, "DaneFaKorygowanej")
        sub(ref, "DataWystFaKorygowanej", corr["issue_date"])
        sub(ref, "NrFaKorygowanej", corr["number"])
        ksef_ref(ref, corr, "NrKSeF", "NrKSeFFaKorygowanej", "NrKSeFN")
    if kind == "final":
        for adv in inv["advances"]:
            ksef_ref(sub(fa, "FakturaZaliczkowa"), adv, None, "NrKSeFFaZaliczkowej", "NrKSeFZN", "NrFaZaliczkowej")

    n = add_rows(fa, before_rows, 1, before=True)
    add_rows(fa, rows, n)

    if kind == "advance" or inv.get("due_date") or inv.get("iban"):
        pay = sub(fa, "Platnosc")
        if kind == "advance":
            sub(pay, "Zaplacono", 1)
            sub(pay, "DataZaplaty", inv.get("paid_date") or inv["issue_date"])
        if inv.get("due_date") and gross > 0 and kind != "advance":
            sub(sub(pay, "TerminPlatnosci"), "Termin", inv["due_date"])
        if inv.get("iban"):
            sub(pay, "FormaPlatnosci", 6)
            iban = re.sub(r"\s", "", inv["iban"]).upper()
            sub(sub(pay, "RachunekBankowy"), "NrRB", iban[2:] if iban.startswith("PL") else iban)

    if kind == "advance":
        order = sub(fa, "Zamowienie")
        sub(order, "WartoscZamowienia", f"{order_total:.2f}")
        for i, r in enumerate(order_rows, 1):
            row = sub(order, "ZamowienieWiersz")
            sub(row, "NrWierszaZam", i)
            sub(row, "P_7Z", r["line"]["description"])
            sub(row, "P_8AZ", r["line"].get("unit", "szt."))
            sub(row, "P_8BZ", r["qty"])
            if r["unit"] is not None:
                sub(row, "P_9AZ", r["unit"])
            sub(row, "P_11NettoZ", f"{r['net']:.2f}")
            pct = RATE_FIELDS[r["rate"]][3]
            sub(row, "P_11VatZ", f"{money(r['net'] * pct / 100):.2f}")
            sub(row, "P_12Z", r["rate"])
    return etree.ElementTree(root)


def text(el, path):
    found = el.find(path, F)
    return found.text if found is not None else None


def pct_of(field, fa):
    rates = {text(r, "f:P_12") for r in fa.findall("f:FaWiersz", F)} | \
            {text(r, "f:P_12Z") for r in fa.findall("f:Zamowienie/f:ZamowienieWiersz", F)}
    used = [RATE_FIELDS[r][3] for r in rates if r in RATE_FIELDS and RATE_FIELDS[r][0] == field]
    return used[0] if len(used) == 1 else next(p for n, _, _, p in RATE_FIELDS.values() if n == field)


def check(tree):
    issues = []
    try:
        xsd = schema()
    except Exception as exc:
        raise SystemExit(json.dumps({"error": f"cannot load FA(3) schema: {exc}"}))
    if not xsd.validate(tree):
        return [f"xsd line {e.line}: {e.message}" for e in xsd.error_log][:20]
    root = tree.getroot()
    fa = root.find("f:Fa", F)
    kind = text(fa, "f:RodzajFaktury")
    sums = {f: Decimal(text(fa, f"f:{f}")) for f in SUM_ORDER if text(fa, f"f:{f}") is not None}

    if kind in ("VAT", "KOR"):  # sums must follow the lines (after minus before for KOR)
        by_field = {}
        for row in fa.findall("f:FaWiersz", F):
            rate, net = text(row, "f:P_12"), text(row, "f:P_11")
            if rate in RATE_FIELDS and net is not None:
                sign = -1 if text(row, "f:StanPrzed") == "1" else 1
                field = RATE_FIELDS[rate][0]
                by_field[field] = by_field.get(field, Decimal(0)) + sign * Decimal(net)
        for field in set(by_field) | {f for f in sums if f.startswith("P_13")}:
            if abs(by_field.get(field, Decimal(0)) - sums.get(field, Decimal(0))) > CENT:
                issues.append(f"{field} {sums.get(field, 0)} != lines {by_field.get(field, 0)}")
        if kind == "KOR" and fa.find("f:DaneFaKorygowanej", F) is None:
            issues.append("KOR without DaneFaKorygowanej")
    for net_f, vat_f in PAIRS.items():
        if net_f not in sums:
            continue
        pct, net, vat = pct_of(net_f, fa), sums[net_f], sums.get(vat_f, Decimal(0))
        expected = money((net + vat) * pct / (100 + pct)) if kind == "ZAL" else money(net * pct / 100)
        if abs(expected - vat) > Decimal("0.02"):  # KOR/ROZ differences may be off by a grosz
            issues.append(f"{vat_f} {vat} != {expected} ({pct}%)")
    gross = sum(v for k, v in sums.items() if not k.endswith("W"))
    p15 = Decimal(text(fa, "f:P_15"))
    if abs(gross - p15) > CENT:
        issues.append(f"P_15 {p15} != sum of P_13/P_14 {gross}")
    if kind == "ZAL":
        order = text(fa, "f:Zamowienie/f:WartoscZamowienia")
        if order is None:
            issues.append("ZAL without Zamowienie")
        elif p15 > Decimal(order):
            issues.append(f"advance {p15} exceeds order value {order}")
    if kind == "ROZ" and fa.find("f:FakturaZaliczkowa", F) is None:
        issues.append("ROZ without FakturaZaliczkowa")
    seller_nip = text(root, "f:Podmiot1/f:DaneIdentyfikacyjne/f:NIP")
    if not nip_ok(seller_nip or ""):
        issues.append(f"seller NIP {seller_nip} fails checksum")
    buyer_nip = text(root, "f:Podmiot2/f:DaneIdentyfikacyjne/f:NIP")
    if buyer_nip and not nip_ok(buyer_nip):
        issues.append(f"buyer NIP {buyer_nip} fails checksum")
    return issues


def iban_from(nrb):
    # KSeF stores Polish accounts as 26 digits without the country prefix
    return f"PL{nrb}" if nrb and re.fullmatch(r"\d{26}", nrb) else nrb


def read_rows(rows, rate_tag="f:P_12", net_tag="f:P_11", name_tag="f:P_7", qty_tag="f:P_8B",
              unit_tag="f:P_8A", price_tag="f:P_9A"):
    out = []
    for row in rows:
        rate, net = text(row, rate_tag), Decimal(text(row, net_tag) or 0)
        pct = RATE_FIELDS.get(rate, (None, None, None, 0))[3]
        price = text(row, price_tag)
        out.append({"description": text(row, name_tag), "qty": float(Decimal(text(row, qty_tag) or 1)),
                    "unit": text(row, unit_tag), "unit_net": price and float(price),
                    "net": float(net), "vat_rate": rate, "vat": float(money(net * pct / 100))})
    return out


def read(tree):
    root = tree.getroot()
    fa = root.find("f:Fa", F)
    p = lambda path: text(root, path)
    kind = {v: k for k, v in KINDS.items()}.get(text(fa, "f:RodzajFaktury"), text(fa, "f:RodzajFaktury"))
    rows = fa.findall("f:FaWiersz", F)
    sums = {f: Decimal(text(fa, f"f:{f}")) for f in SUM_ORDER if text(fa, f"f:{f}") is not None}
    rates = {}
    for rate, (net_f, vat_f, _, _) in RATE_FIELDS.items():
        if net_f in sums and net_f not in {v[0] for r, v in RATE_FIELDS.items() if r in rates}:
            rates[rate] = {"net": float(sums[net_f]), "vat": float(sums.get(vat_f, 0)) if vat_f else 0.0}
    for rate in list(rates):  # prefer the rate actually used in lines (8 vs 7, 23 vs 22)
        used = {text(r, "f:P_12") for r in rows} | {text(r, "f:P_12Z") for r in fa.findall(".//f:ZamowienieWiersz", F)}
        alt = [r for r in used if r in RATE_FIELDS and RATE_FIELDS[r][0] == RATE_FIELDS[rate][0]]
        if alt and alt[0] != rate:
            rates[alt[0]] = rates.pop(rate)
    out = {
        "number": text(fa, "f:P_2"), "type": kind, "issue_date": text(fa, "f:P_1"),
        "sale_date": text(fa, "f:P_6") or text(fa, "f:P_1"),
        "due_date": text(fa, "f:Platnosc/f:TerminPlatnosci/f:Termin"), "currency": text(fa, "f:KodWaluty"),
        "place": text(fa, "f:P_1M"),
        "seller": {"name": p("f:Podmiot1/f:DaneIdentyfikacyjne/f:Nazwa"),
                   "tax_id": p("f:Podmiot1/f:DaneIdentyfikacyjne/f:NIP"), "country": "PL",
                   "address": {"line1": p("f:Podmiot1/f:Adres/f:AdresL1"), "line2": p("f:Podmiot1/f:Adres/f:AdresL2")},
                   "email": p("f:Podmiot1/f:DaneKontaktowe/f:Email")},
        "buyer": {"name": p("f:Podmiot2/f:DaneIdentyfikacyjne/f:Nazwa"),
                  "tax_id": p("f:Podmiot2/f:DaneIdentyfikacyjne/f:NIP")
                  or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:NrVatUE")
                  or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:NrID"),
                  "country": p("f:Podmiot2/f:Adres/f:KodKraju")
                  or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:KodUE") or "PL",
                  "address": {"line1": p("f:Podmiot2/f:Adres/f:AdresL1"), "line2": p("f:Podmiot2/f:Adres/f:AdresL2")}},
        "lines": read_rows([r for r in rows if text(r, "f:StanPrzed") != "1"]),
        "by_rate": rates,
        "totals": {"net": float(sum(v for k, v in sums.items() if k.startswith("P_13"))),
                   "vat": float(sum(v for k, v in sums.items() if k.startswith("P_14") and not k.endswith("W"))),
                   "gross": float(Decimal(text(fa, "f:P_15")))},
        "iban": iban_from(text(fa, "f:Platnosc/f:RachunekBankowy/f:NrRB")),
        "notes": ["reverse charge"] if text(fa, "f:Adnotacje/f:P_18") == "1" else [],
    }
    flags = {"cash_method": "P_16", "self_billing": "P_17", "split_payment": "P_18A"}
    out.update({k: True for k, tag in flags.items() if text(fa, f"f:Adnotacje/f:{tag}") == "1"})
    if text(fa, "f:Adnotacje/f:Zwolnienie/f:P_19A"):
        out["exemption_basis"] = text(fa, "f:Adnotacje/f:Zwolnienie/f:P_19A")
    for vat_f in ("P_14_1", "P_14_2", "P_14_3"):
        if sums.get(vat_f) and sums.get(vat_f + "W"):
            out["fx_rate"] = float(round(sums[vat_f + "W"] / sums[vat_f], 4))  # derived from VAT in PLN
            break
    if kind == "correction":
        ref = fa.find("f:DaneFaKorygowanej", F)
        out["lines_before"] = read_rows([r for r in rows if text(r, "f:StanPrzed") == "1"])
        out["corrects"] = {"number": text(ref, "f:NrFaKorygowanej"), "issue_date": text(ref, "f:DataWystFaKorygowanej"),
                           "ksef_number": text(ref, "f:NrKSeFFaKorygowanej")}
        out["reason"] = text(fa, "f:PrzyczynaKorekty")
    if kind == "advance":
        out["paid"] = out["totals"]["gross"]
        out["paid_date"] = text(fa, "f:Platnosc/f:DataZaplaty")
        out["order_lines"] = read_rows(fa.findall("f:Zamowienie/f:ZamowienieWiersz", F), "f:P_12Z",
                                       "f:P_11NettoZ", "f:P_7Z", "f:P_8BZ", "f:P_8AZ", "f:P_9AZ")
    if kind == "final":
        out["advances"] = [{"number": text(a, "f:NrFaZaliczkowej"), "ksef_number": text(a, "f:NrKSeFFaZaliczkowej")}
                           for a in fa.findall("f:FakturaZaliczkowa", F)]
    return out


def out(payload, code):
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))
    sys.exit(code)


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("build", "validate", "read"):
        print(__doc__.strip())
        sys.exit(2)
    cmd, src = args[0], args[1]
    try:
        if cmd == "build":
            if len(args) < 3:
                out({"error": "build needs INVOICE.json OUT.xml"}, 2)
            with open(src, encoding="utf-8") as f:
                tree = build(json.load(f))
            tree.write(args[2], xml_declaration=True, encoding="UTF-8", pretty_print=True)
            issues = check(etree.parse(args[2]))  # re-read so XSD errors carry line numbers
            out({"out": args[2], "status": "issues" if issues else "ok", "issues": issues}, 1 if issues else 0)
        tree = etree.parse(src)
        if cmd == "validate":
            issues = check(tree)
            out({"file": src, "status": "issues" if issues else "ok", "issues": issues}, 1 if issues else 0)
        out(read(tree), 0)
    except InvoiceError as exc:
        out({"status": "issues", "issues": [str(exc)]}, 1)
    except (OSError, ValueError, KeyError, etree.XMLSyntaxError) as exc:
        out({"error": f"{type(exc).__name__}: {exc}"}, 2)


if __name__ == "__main__":
    main()
