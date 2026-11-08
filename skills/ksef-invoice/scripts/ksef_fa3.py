#!/usr/bin/env python3
"""Budowanie, walidacja, odczyt i korekta e-faktur KSeF w strukturze FA(3).

Użycie:
  python ksef_fa3.py build INVOICE.json OUT.xml             JSON -> FA(3) XML + walidacja
  python ksef_fa3.py validate PLIK|KATALOG|GLOB [--csv P]   Walidacja XSD, sum i NIP
  python ksef_fa3.py read FILE.xml                          FA(3) XML -> JSON
  python ksef_fa3.py correct ORYGINAL.xml ZMIANY.json OUT.xml  Korekta z oryginału XML

Typy faktur ("type" w JSON): invoice (VAT), correction (KOR),
advance (ZAL), final (ROZ), kor_zal (KOR_ZAL), kor_roz (KOR_ROZ).
Wbudowany schemat XSD leży w skills/ksef-invoice/xsd/1-0E (nadpisanie: KSEF_SCHEMA_DIR).
Wymaga: pip install lxml. Wypisuje jedną linię JSON. Kody wyjścia: 0 ok, 1 błędy faktury, 2 błąd użycia.
"""
import csv
import glob
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
    print(json.dumps({"error": "Brak biblioteki lxml. Zainstaluj ją poleceniem: pip install lxml"}, ensure_ascii=False))
    sys.exit(2)

SCHEMA_VERSION = "1-0E"
NS = "http://crd.gov.pl/wzor/2025/06/25/13775/"
DEFS = "http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/DefinicjeTypy/"
SCHEMAS = {
    "schemat.xsd": NS + "schemat.xsd",
    "StrukturyDanych_v10-0E.xsd": DEFS + "StrukturyDanych_v10-0E.xsd",
    "ElementarneTypyDanych_v10-0E.xsd": DEFS + "ElementarneTypyDanych_v10-0E.xsd",
    "KodyKrajow_v10-0E.xsd": DEFS + "KodyKrajow_v10-0E.xsd",
}
BUNDLED_XSD_DIR = Path(__file__).resolve().parent.parent / "xsd" / SCHEMA_VERSION
F = {"f": NS}
CENT = Decimal("0.01")
NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
KINDS = {
    "invoice": "VAT",
    "correction": "KOR",
    "advance": "ZAL",
    "final": "ROZ",
    "kor_zal": "KOR_ZAL",
    "kor_roz": "KOR_ROZ",
}
KIND_BY_XML = {v: k for k, v in KINDS.items()}
CORRECTION_KINDS = ("correction", "kor_zal", "kor_roz")
EU = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE",
      "IT", "LT", "LU", "LV", "MT", "NL", "PT", "RO", "SE", "SI", "SK", "XI"}
GTU_CODES = {f"GTU_{i:02d}" for i in range(1, 14)}
PODMIOT3_ROLES = {
    "faktor": 1, "factor": 1,
    "odbiorca": 2, "recipient": 2,
    "podmiot_pierwotny": 3, "original": 3,
    "dodatkowy_nabywca": 4, "additional_buyer": 4,
    "wystawca": 5, "issuer": 5,
    "platnik": 6, "payer": 6,
    "jst_wystawca": 7, "jst_issuer": 7,
    "jst": 8, "jst_odbiorca": 8, "jst_recipient": 8,
    "gv_wystawca": 9, "gv_issuer": 9,
    "gv": 10, "vat_group": 10, "gv_odbiorca": 10, "gv_recipient": 10,
    "pracownik": 11, "employee": 11,
}

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

SCHEMA_WARNINGS = []


class InvoiceError(Exception):
    pass


def money(value):
    return Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def fmt(value):
    text_val = format(value.normalize(), "f") if isinstance(value, Decimal) else str(value)
    return text_val if text_val not in ("-0", "") else "0"


def digits(value):
    return re.sub(r"\D", "", str(value or ""))


def nip_ok(nip):
    if len(nip) != 10 or not nip.isdigit():
        return False
    check_sum = sum(int(d) * w for d, w in zip(nip, NIP_WEIGHTS)) % 11
    return check_sum != 10 and check_sum == int(nip[9])


def schema():
    env_dir = os.environ.get("KSEF_SCHEMA_DIR")
    folder = Path(env_dir) if env_dir else BUNDLED_XSD_DIR
    missing = [name for name in SCHEMAS if not (folder / name).exists()]
    if missing:
        folder.mkdir(parents=True, exist_ok=True)
        for name in missing:
            url = SCHEMAS[name]
            with urllib.request.urlopen(url, timeout=30) as resp:
                (folder / name).write_bytes(resp.read())
        msg = (f"Brak lokalnego schematu XSD w {folder}. Pobrano z sieci schemat FA(3) "
               f"w wersji {SCHEMA_VERSION}. Wgraj pliki XSD do katalogu xsd/{SCHEMA_VERSION}.")
        if msg not in SCHEMA_WARNINGS:
            SCHEMA_WARNINGS.append(msg)

    class Local(etree.Resolver):
        def resolve(self, url, pubid, context):
            name = url.rsplit("/", 1)[-1]
            if name in SCHEMAS:
                return self.resolve_filename(str(folder / name), context)
            return None

    parser = etree.XMLParser()
    parser.resolvers.add(Local())
    return etree.XMLSchema(etree.parse(str(folder / "schemat.xsd"), parser))


def sub(parent, tag, text_val=None, **attrs):
    el = etree.SubElement(parent, f"{{{NS}}}{tag}", **attrs)
    if text_val is not None:
        el.text = fmt(text_val)
    return el


def address(parent, party, tag="Adres"):
    addr = party.get("address") or {}
    if not addr.get("line1"):
        return
    a = sub(parent, tag)
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


def norm_role(role_val):
    if role_val is None:
        return 2
    if isinstance(role_val, int) and 1 <= role_val <= 11:
        return role_val
    key = str(role_val).strip().lower()
    if key.isdigit() and 1 <= int(key) <= 11:
        return int(key)
    if key in PODMIOT3_ROLES:
        return PODMIOT3_ROLES[key]
    raise InvoiceError(
        f"Nieprawidłowa rola Podmiot3: {role_val!r}. Użyj liczby 1..11 lub nazwy roli (np. odbiorca, jst, gv)."
    )


def extract_podmiot3_list(inv):
    raw = inv.get("podmiot3") or inv.get("recipient") or inv.get("recipients") or inv.get("third_parties")
    if not raw:
        return []
    items = [raw] if isinstance(raw, dict) else list(raw)
    out_list = []
    for i, item in enumerate(items, 1):
        if not item.get("name"):
            raise InvoiceError(f"Podmiot3 {i}: brak pola name. Podaj nazwę odbiorcy lub podmiotu trzeciego.")
        role = norm_role(item.get("role") if "role" in item else item.get("rola"))
        country = (item.get("country") or "PL").upper()
        id_wew = str(item.get("id_wew") or "").strip()
        tax_id = str(item.get("tax_id") or item.get("nip") or "").strip()
        if country == "PL" and re.fullmatch(r"\d{10}-\d{5}", tax_id) and not id_wew:
            id_wew, tax_id = tax_id, ""
        if id_wew:
            if not re.fullmatch(r"[1-9]((\d[1-9])|([1-9]\d))\d{7}-\d{5}", id_wew) or not nip_ok(id_wew[:10]):
                raise InvoiceError(
                    f"Podmiot3 {i}: nieprawidłowy identyfikator wewnętrzny IDWew ({id_wew}). "
                    "Wymagany format to 10 cyfr poprawnego NIP, myślnik i 5 cyfr (np. 1234560007-00001)."
                )
        elif country == "PL" and tax_id:
            if not nip_ok(digits(tax_id)):
                raise InvoiceError(
                    f"Nieprawidłowa suma kontrolna NIP w Podmiot3 ({tax_id}). Sprawdź 10 cyfr NIP odbiorcy."
                )
        out_list.append({**item, "country": country, "role": role, "id_wew": id_wew, "tax_id": tax_id})
    return out_list


def add_podmiot3(root, p3):
    el = sub(root, "Podmiot3")
    ids = sub(el, "DaneIdentyfikacyjne")
    country = p3["country"]
    raw = re.sub(r"[\s-]", "", p3["tax_id"]).upper()
    prefix = "EL" if country == "GR" else country
    if p3.get("id_wew"):
        sub(ids, "IDWew", p3["id_wew"])
    elif not raw:
        sub(ids, "BrakID", 1)
    elif country == "PL":
        sub(ids, "NIP", digits(raw))
    elif prefix in EU:
        sub(ids, "KodUE", prefix)
        sub(ids, "NrVatUE", raw[len(prefix):] if raw.startswith(prefix) else raw)
    else:
        sub(ids, "KodKraju", country)
        sub(ids, "NrID", raw)
    sub(ids, "Nazwa", p3["name"])
    address(el, p3)
    if p3.get("email") or p3.get("phone"):
        contact = sub(el, "DaneKontaktowe")
        if p3.get("email"):
            sub(contact, "Email", p3["email"])
        if p3.get("phone"):
            sub(contact, "Telefon", p3["phone"])
    sub(el, "Rola", p3["role"])


def norm_kind(raw_kind):
    val = str(raw_kind if raw_kind is not None else "invoice").strip()
    if val in KINDS:
        return val
    if val.lower() in KINDS:
        return val.lower()
    if val.upper() in KIND_BY_XML:
        return KIND_BY_XML[val.upper()]
    raise InvoiceError(f"Nieobsługiwany typ faktury: {raw_kind!r}. Użyj jednego z: {', '.join(KINDS)}.")


def norm_rate(rate, where):
    rate = str(rate if rate is not None else "").strip()
    rate = rate.lower() if rate.lower() in ("zw", "oo") else rate.rstrip("%")
    if rate not in RATE_FIELDS:
        raise InvoiceError(
            f"{where}: nieobsługiwana stawka vat_rate {rate!r}. Użyj jednej z: {', '.join(RATE_FIELDS)}."
        )
    return rate


def norm_gtu(gtu_val, where):
    if gtu_val is None or gtu_val == "":
        return None
    raw = str(gtu_val).strip().upper()
    if raw.isdigit():
        raw = f"GTU_{int(raw):02d}"
    elif re.fullmatch(r"GTU[-_\s]?\d{1,2}", raw):
        num = int(re.sub(r"\D", "", raw))
        raw = f"GTU_{num:02d}"
    if raw not in GTU_CODES:
        raise InvoiceError(
            f"{where}: nieprawidłowy kod GTU {gtu_val!r}. Dozwolone wartości w XSD to GTU_01..GTU_13."
        )
    return raw


def extract_invoice_gtus(inv):
    codes = []
    raw_gtu = inv.get("gtu")
    if isinstance(raw_gtu, str):
        codes.append(norm_gtu(raw_gtu, "gtu"))
    elif isinstance(raw_gtu, list):
        for item in raw_gtu:
            codes.append(norm_gtu(item, "gtu"))
    elif isinstance(raw_gtu, dict):
        for k, v in raw_gtu.items():
            if v:
                codes.append(norm_gtu(k, "gtu"))
    for container_name in ("adnotacje", "annotations"):
        container = inv.get(container_name)
        if isinstance(container, dict):
            if "gtu" in container:
                sub_gtu = container["gtu"]
                if isinstance(sub_gtu, str):
                    codes.append(norm_gtu(sub_gtu, f"{container_name}.gtu"))
                elif isinstance(sub_gtu, list):
                    for item in sub_gtu:
                        codes.append(norm_gtu(item, f"{container_name}.gtu"))
            for k, v in container.items():
                if k.lower() != "gtu" and v and str(k).upper().startswith("GTU"):
                    codes.append(norm_gtu(k, f"{container_name}.{k}"))
    for k, v in inv.items():
        if k.lower() != "gtu" and v is True and str(k).upper().startswith("GTU"):
            codes.append(norm_gtu(k, k))
    out_codes = []
    for c in codes:
        if c and c not in out_codes:
            out_codes.append(c)
    return out_codes


def parse_lines(lines, where, default_gtus=None):
    rows = []
    default_gtus = default_gtus or []
    for i, line in enumerate(lines or [], 1):
        rate = norm_rate(line.get("vat_rate"), f"{where} {i}")
        qty = Decimal(str(line.get("qty", 1)))
        unit = Decimal(str(line["unit_net"])) if line.get("unit_net") is not None else None
        if line.get("net") is None and unit is None:
            raise InvoiceError(f"{where} {i}: brak kwoty. Podaj pole unit_net (cena netto) lub net (wartość netto).")
        net = money(line["net"]) if line.get("net") is not None else money(qty * unit)
        gtu = norm_gtu(line.get("gtu") or line.get("GTU"), f"{where} {i}")
        if not gtu and default_gtus:
            gtu = default_gtus[min(i - 1, len(default_gtus) - 1)]
        rows.append({"line": line, "rate": rate, "qty": qty, "unit": unit, "net": net, "gtu": gtu})
    return rows


def by_rate(rows):
    nets = {}
    for r in rows:
        nets[r["rate"]] = nets.get(r["rate"], Decimal(0)) + r["net"]
    return {rate: {"net": net, "vat": money(net * RATE_FIELDS[rate][3] / 100)} for rate, net in nets.items()}


def advance_split(order_rows, paid):
    """Rozbicie kwoty brutto zaliczki proporcjonalnie na stawki VAT zamówienia (art. 106f ust. 1 pkt 3)."""
    order = by_rate(order_rows)
    total = sum(v["net"] + v["vat"] for v in order.values())
    if total <= 0:
        raise InvoiceError("Wartość zamówienia (order_lines) musi być dodatnia. Sprawdź kwoty pozycji.")
    if paid > total:
        raise InvoiceError(
            f"Kwota zaliczki ({paid}) przekracza wartość brutto zamówienia ({total}). "
            "Zmniejsz pole paid lub zaktualizuj order_lines."
        )
    out_parts, left = {}, paid
    rates = list(order)
    for i, rate in enumerate(rates):
        gross = left if i == len(rates) - 1 else money(paid * (order[rate]["net"] + order[rate]["vat"]) / total)
        left -= gross
        pct = RATE_FIELDS[rate][3]
        vat = money(gross * pct / (100 + pct))
        out_parts[rate] = {"net": gross - vat, "vat": vat}
    return out_parts, total


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
                    raise InvoiceError(
                        "Faktura w walucie obcej z podatkiem VAT wymaga kursu przeliczeniowego. "
                        "Podaj pole fx_rate (kurs PLN za 1 jednostkę waluty)."
                    )
                sums[vat_pln_f] = sums.get(vat_pln_f, Decimal(0)) + money(v["vat"] * fx)
    return sums


def subtract(a, b):
    out_diff = {}
    for rate in list(a) + [r for r in b if r not in a]:
        x, y = a.get(rate, {"net": 0, "vat": 0}), b.get(rate, {"net": 0, "vat": 0})
        out_diff[rate] = {"net": Decimal(x["net"]) - Decimal(y["net"]), "vat": Decimal(x["vat"]) - Decimal(y["vat"])}
    return out_diff


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
        if r.get("gtu"):
            sub(row, "GTU", r["gtu"])
        if before:
            sub(row, "StanPrzed", 1)
    return start + len(rows)


def build(inv):
    kind = norm_kind(inv.get("type", "invoice"))
    for key in ("number", "issue_date", "seller", "buyer"):
        if not inv.get(key):
            raise InvoiceError(f"Brak wymaganego pola {key}. Uzupełnij je w pliku JSON.")
    seller, buyer = inv["seller"], inv["buyer"]
    if not nip_ok(digits(seller.get("tax_id"))):
        raise InvoiceError(
            f"Nieprawidłowa suma kontrolna NIP sprzedawcy ({seller.get('tax_id')}). "
            "Sprawdź 10 cyfr NIP w wykazie podatników VAT."
        )
    if (buyer.get("country") or "PL").upper() == "PL" and buyer.get("tax_id") \
            and not nip_ok(digits(buyer["tax_id"])):
        raise InvoiceError(
            f"Nieprawidłowa suma kontrolna NIP nabywcy ({buyer['tax_id']}). "
            "Sprawdź 10 cyfr NIP lub usuń pole tax_id dla osoby prywatnej."
        )
    if not (seller.get("address") or {}).get("line1"):
        raise InvoiceError("Brak adresu sprzedawcy (seller.address.line1). Podaj ulicę i numer lub miejscowość.")
    podmiot3_list = extract_podmiot3_list(inv)
    default_gtus = extract_invoice_gtus(inv)
    currency = (inv.get("currency") or "PLN").upper()
    fx = Decimal(str(inv["fx_rate"])) if inv.get("fx_rate") else None

    rows = parse_lines(inv.get("lines"), "line", default_gtus)
    before_rows, order_rows, order_total = [], [], None
    if kind == "invoice":
        if not rows:
            raise InvoiceError("Brak pozycji faktury (lines). Dodaj co najmniej jedną pozycję.")
        parts = by_rate(rows)
    elif kind in CORRECTION_KINDS:
        corr = inv.get("corrects") or {}
        if not (corr.get("number") and corr.get("issue_date")):
            raise InvoiceError(
                f"Korekta ({kind}) wymaga pól corrects.number oraz corrects.issue_date "
                "(numer i data wystawienia faktury korygowanej)."
            )
        before_rows = parse_lines(inv.get("lines_before"), "lines_before")
        if not before_rows:
            raise InvoiceError(
                f"Korekta ({kind}) wymaga pola lines_before z pozycjami faktury przed korektą."
            )
        if kind == "kor_roz":
            advances = inv.get("advances") or []
            if not advances:
                raise InvoiceError(
                    "Korekta faktury rozliczającej (kor_roz) wymaga listy advances z referencjami "
                    "do faktur zaliczkowych (number lub ksef_number)."
                )
            for i, adv in enumerate(advances, 1):
                if not (adv.get("number") or adv.get("ksef_number")):
                    raise InvoiceError(
                        f"Zaliczka {i} w kor_roz wymaga pola number lub ksef_number."
                    )
        parts = subtract(by_rate(rows), by_rate(before_rows))
    elif kind == "advance":
        order_rows = parse_lines(inv.get("order_lines"), "order_line", default_gtus)
        if not order_rows or inv.get("paid") is None:
            raise InvoiceError(
                "Faktura zaliczkowa (advance) wymaga pól order_lines (pozycje zamówienia) oraz paid (otrzymana kwota brutto)."
            )
        parts, order_total = advance_split(order_rows, money(inv["paid"]))
    else:  # final
        if not rows or not inv.get("advances"):
            raise InvoiceError(
                "Faktura rozliczająca (final) wymaga pól lines (całe zamówienie) oraz advances (wcześniejsze zaliczki)."
            )
        parts = by_rate(rows)
        for i, adv in enumerate(inv["advances"], 1):
            if not (adv.get("number") or adv.get("ksef_number")) or not adv.get("by_rate"):
                raise InvoiceError(
                    f"Zaliczka {i}: wymagane pole number (lub ksef_number) oraz by_rate (odczytane poleceniem read z zaliczki)."
                )
            taken = {norm_rate(r, f"advance {i}"): {"net": money(v["net"]), "vat": money(v.get("vat", 0))}
                     for r, v in adv["by_rate"].items()}
            parts = subtract(parts, taken)
    rates_used = {r["rate"] for r in rows + before_rows + order_rows}
    if "zw" in rates_used and not inv.get("exemption_basis"):
        raise InvoiceError(
            "Stawka zw (zwolnione z VAT) wymaga podania podstawy prawnej w polu exemption_basis "
            "(np. 'art. 113 ust. 1 ustawy o VAT')."
        )
    sums = rate_sums(parts, currency, fx)
    gross = sum(v for k, v in sums.items() if not k.endswith("W"))
    if kind == "advance" and gross != money(inv["paid"]):
        raise InvoiceError(f"Błąd wewnętrzny podziału zaliczki: suma {gross} != wpłata {inv['paid']}.")

    root = etree.Element(f"{{{NS}}}Faktura", nsmap={None: NS})
    head = sub(root, "Naglowek")
    sub(head, "KodFormularza", "FA", kodSystemowy="FA (3)", wersjaSchemy=SCHEMA_VERSION)
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
    has_jst = bool(buyer.get("jst")) or any(p["role"] == 8 for p in podmiot3_list)
    has_gv = bool(buyer.get("gv")) or any(p["role"] == 10 for p in podmiot3_list)
    sub(p2, "JST", 1 if has_jst else 2)
    sub(p2, "GV", 1 if has_gv else 2)

    for p3 in podmiot3_list:
        add_podmiot3(root, p3)

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
    sub(notes, "P_23", 2)
    sub(sub(notes, "PMarzy"), "P_PMarzyN", 1)
    sub(fa, "RodzajFaktury", KINDS[kind])

    if kind in CORRECTION_KINDS:
        corr = inv["corrects"]
        if inv.get("reason"):
            sub(fa, "PrzyczynaKorekty", inv["reason"])
        sub(fa, "TypKorekty", inv.get("correction_effect", 2))
        ref = sub(fa, "DaneFaKorygowanej")
        sub(ref, "DataWystFaKorygowanej", corr["issue_date"])
        sub(ref, "NrFaKorygowanej", corr["number"])
        ksef_ref(ref, corr, "NrKSeF", "NrKSeFFaKorygowanej", "NrKSeFN")
    if kind in ("final", "kor_roz") or (kind == "kor_zal" and inv.get("advances")):
        for adv in inv.get("advances") or []:
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
            if r.get("gtu"):
                sub(row, "GTUZ", r["gtu"])
    return etree.ElementTree(root)


def text(el, path):
    if el is None:
        return None
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
        raise SystemExit(
            json.dumps(
                {
                    "error": f"Nie można wczytać schematu XSD FA(3): {exc}. "
                    f"Sprawdź katalog {BUNDLED_XSD_DIR} lub zmienną KSEF_SCHEMA_DIR."
                },
                ensure_ascii=False,
            )
        )
    root = tree.getroot()
    fa = root.find("f:Fa", F)
    kind = text(fa, "f:RodzajFaktury") if fa is not None else None

    # Sprawdź obowiązkowe referencje dla korekt i rozliczeń także przed/po XSD
    if fa is not None:
        if kind == "KOR" and fa.find("f:DaneFaKorygowanej", F) is None:
            issues.append(
                "Faktura KOR nie zawiera sekcji DaneFaKorygowanej. "
                "Dodaj numer i datę korygowanej faktury w polu corrects."
            )
        if kind == "KOR_ZAL" and fa.find("f:DaneFaKorygowanej", F) is None:
            issues.append(
                "Faktura KOR_ZAL nie zawiera referencji do faktury zaliczkowej (brak DaneFaKorygowanej). "
                "Dodaj dane korygowanej faktury zaliczkowej w polu corrects."
            )
        if kind == "KOR_ROZ":
            if fa.find("f:DaneFaKorygowanej", F) is None:
                issues.append(
                    "Faktura KOR_ROZ nie zawiera sekcji DaneFaKorygowanej. "
                    "Dodaj dane korygowanej faktury rozliczającej w polu corrects."
                )
            if fa.find("f:FakturaZaliczkowa", F) is None:
                issues.append(
                    "Faktura KOR_ROZ nie zawiera sekcji FakturaZaliczkowa. "
                    "Dodaj referencje do faktur zaliczkowych w polu advances."
                )
        if kind == "ROZ" and fa.find("f:FakturaZaliczkowa", F) is None:
            issues.append(
                "Faktura ROZ nie zawiera sekcji FakturaZaliczkowa. "
                "Dodaj numery lub numery KSeF wcześniejszych zaliczek w polu advances."
            )

    if not xsd.validate(tree):
        xsd_issues = [
            f"Błąd XSD (linia {e.line}): {e.message}. Sprawdź strukturę i dozwolone wartości pól względem schematu FA(3)."
            for e in xsd.error_log
        ][:20]
        return issues + [msg for msg in xsd_issues if msg not in issues]

    sums = {f: Decimal(text(fa, f"f:{f}")) for f in SUM_ORDER if text(fa, f"f:{f}") is not None}

    if kind in ("VAT", "KOR", "KOR_ZAL", "KOR_ROZ"):
        by_field = {}
        for row in fa.findall("f:FaWiersz", F):
            rate, net = text(row, "f:P_12"), text(row, "f:P_11")
            if rate in RATE_FIELDS and net is not None:
                sign = -1 if text(row, "f:StanPrzed") == "1" else 1
                field = RATE_FIELDS[rate][0]
                by_field[field] = by_field.get(field, Decimal(0)) + sign * Decimal(net)
        for field in set(by_field) | {f for f in sums if f.startswith("P_13")}:
            if abs(by_field.get(field, Decimal(0)) - sums.get(field, Decimal(0))) > CENT:
                issues.append(
                    f"Pole {field} ({sums.get(field, 0)}) nie zgadza się z sumą pozycji lines ({by_field.get(field, 0)}). "
                    f"Przelicz wartość netto w polu {field} lub przebuduj fakturę poleceniem build."
                )
    for net_f, vat_f in PAIRS.items():
        if net_f not in sums:
            continue
        pct, net, vat = pct_of(net_f, fa), sums[net_f], sums.get(vat_f, Decimal(0))
        expected = money((net + vat) * pct / (100 + pct)) if kind == "ZAL" else money(net * pct / 100)
        if abs(expected - vat) > Decimal("0.02"):
            issues.append(
                f"Pole {vat_f} ({vat}) nie zgadza się z wyliczonym podatkiem VAT {expected} ({pct}%). "
                f"Popraw kwotę VAT w polu {vat_f}."
            )
    gross = sum(v for k, v in sums.items() if not k.endswith("W"))
    p15 = Decimal(text(fa, "f:P_15"))
    if abs(gross - p15) > CENT:
        issues.append(
            f"Pole P_15 ({p15}) nie zgadza się z sumą pól P_13 i P_14 ({gross}). "
            "Popraw kwotę należności ogółem w polu P_15."
        )
    if kind == "ZAL":
        order = text(fa, "f:Zamowienie/f:WartoscZamowienia")
        if order is None:
            issues.append(
                "Faktura ZAL nie zawiera sekcji Zamowienie. Dodaj pozycje zamówienia w polu order_lines."
            )
        elif p15 > Decimal(order):
            issues.append(
                f"Kwota zaliczki P_15 ({p15}) przekracza wartość zamówienia WartoscZamowienia ({order}). "
                "Zmniejsz kwotę zaliczki lub zaktualizuj wartość zamówienia."
            )
    seller_nip = text(root, "f:Podmiot1/f:DaneIdentyfikacyjne/f:NIP")
    if not nip_ok(seller_nip or ""):
        issues.append(
            f"Nieprawidłowa suma kontrolna NIP sprzedawcy ({seller_nip}). "
            "Sprawdź 10 cyfr NIP w wykazie podatników VAT."
        )
    buyer_nip = text(root, "f:Podmiot2/f:DaneIdentyfikacyjne/f:NIP")
    if buyer_nip and not nip_ok(buyer_nip):
        issues.append(
            f"Nieprawidłowa suma kontrolna NIP nabywcy ({buyer_nip}). "
            "Sprawdź 10 cyfr NIP nabywcy."
        )
    for idx, p3 in enumerate(root.findall("f:Podmiot3", F), 1):
        p3_nip = text(p3, "f:DaneIdentyfikacyjne/f:NIP")
        if p3_nip and not nip_ok(p3_nip):
            issues.append(
                f"Nieprawidłowa suma kontrolna NIP w Podmiot3 nr {idx} ({p3_nip}). "
                "Sprawdź 10 cyfr NIP odbiorcy."
            )
        p3_idwew = text(p3, "f:DaneIdentyfikacyjne/f:IDWew")
        if p3_idwew and not nip_ok(p3_idwew[:10]):
            issues.append(
                f"Nieprawidłowa suma kontrolna NIP w IDWew Podmiot3 nr {idx} ({p3_idwew}). "
                "Pierwsze 10 cyfr IDWew musi stanowić poprawny NIP."
            )
    return issues


def iban_from(nrb):
    return f"PL{nrb}" if nrb and re.fullmatch(r"\d{26}", nrb) else nrb


def read_rows(rows, rate_tag="f:P_12", net_tag="f:P_11", name_tag="f:P_7", qty_tag="f:P_8B",
              unit_tag="f:P_8A", price_tag="f:P_9A", gtu_tag="f:GTU"):
    out_rows = []
    for row in rows:
        rate, net = text(row, rate_tag), Decimal(text(row, net_tag) or 0)
        pct = RATE_FIELDS.get(rate, (None, None, None, 0))[3]
        price = text(row, price_tag)
        item = {
            "description": text(row, name_tag),
            "qty": float(Decimal(text(row, qty_tag) or 1)),
            "unit": text(row, unit_tag),
            "unit_net": price and float(price),
            "net": float(net),
            "vat_rate": rate,
            "vat": float(money(net * pct / 100)),
        }
        gtu = text(row, gtu_tag)
        if gtu:
            item["gtu"] = gtu
        out_rows.append(item)
    return out_rows


def read_ksef_number_from_root(root, fa):
    for attr in ("ksef_number", "nrKSeF", "NrKSeF"):
        if root.get(attr):
            return root.get(attr)
    head = root.find("f:Naglowek", F)
    if head is not None:
        for attr in ("ksef_number", "nrKSeF", "NrKSeF"):
            if head.get(attr):
                return head.get(attr)
        for tag in ("NrKSeF", "NumerKSeF"):
            val = text(head, f"f:{tag}")
            if val:
                return val
    if fa is not None:
        for desc in fa.findall("f:DodatkowyOpis", F):
            if (text(desc, "f:Klucz") or "").strip().lower() in ("nrksef", "ksef_number", "numerksef"):
                val = text(desc, "f:Wartosc")
                if val:
                    return val.strip()
    return None


def read(tree):
    root = tree.getroot()
    fa = root.find("f:Fa", F)
    p = lambda path: text(root, path)
    kind = KIND_BY_XML.get(text(fa, "f:RodzajFaktury"), text(fa, "f:RodzajFaktury"))
    rows = fa.findall("f:FaWiersz", F)
    sums = {f: Decimal(text(fa, f"f:{f}")) for f in SUM_ORDER if text(fa, f"f:{f}") is not None}
    rates = {}
    for rate, (net_f, vat_f, _, _) in RATE_FIELDS.items():
        if net_f in sums and net_f not in {v[0] for r, v in RATE_FIELDS.items() if r in rates}:
            rates[rate] = {"net": float(sums[net_f]), "vat": float(sums.get(vat_f, 0)) if vat_f else 0.0}
    for rate in list(rates):
        used = {text(r, "f:P_12") for r in rows} | {text(r, "f:P_12Z") for r in fa.findall(".//f:ZamowienieWiersz", F)}
        alt = [r for r in used if r in RATE_FIELDS and RATE_FIELDS[r][0] == RATE_FIELDS[rate][0]]
        if alt and alt[0] != rate:
            rates[alt[0]] = rates.pop(rate)
    seller_dict = {
        "name": p("f:Podmiot1/f:DaneIdentyfikacyjne/f:Nazwa"),
        "tax_id": p("f:Podmiot1/f:DaneIdentyfikacyjne/f:NIP"),
        "country": "PL",
        "address": {"line1": p("f:Podmiot1/f:Adres/f:AdresL1"), "line2": p("f:Podmiot1/f:Adres/f:AdresL2")},
        "email": p("f:Podmiot1/f:DaneKontaktowe/f:Email"),
    }
    if p("f:Podmiot1/f:DaneKontaktowe/f:Telefon"):
        seller_dict["phone"] = p("f:Podmiot1/f:DaneKontaktowe/f:Telefon")

    buyer_dict = {
        "name": p("f:Podmiot2/f:DaneIdentyfikacyjne/f:Nazwa"),
        "tax_id": (p("f:Podmiot2/f:DaneIdentyfikacyjne/f:NIP")
                   or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:NrVatUE")
                   or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:NrID")),
        "country": (p("f:Podmiot2/f:Adres/f:KodKraju")
                    or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:KodUE")
                    or p("f:Podmiot2/f:DaneIdentyfikacyjne/f:KodKraju") or "PL"),
        "address": {"line1": p("f:Podmiot2/f:Adres/f:AdresL1"), "line2": p("f:Podmiot2/f:Adres/f:AdresL2")},
    }
    if p("f:Podmiot2/f:JST") == "1":
        buyer_dict["jst"] = True
    if p("f:Podmiot2/f:GV") == "1":
        buyer_dict["gv"] = True

    out_data = {
        "number": text(fa, "f:P_2"),
        "type": kind,
        "issue_date": text(fa, "f:P_1"),
        "sale_date": text(fa, "f:P_6") or text(fa, "f:P_1"),
        "due_date": text(fa, "f:Platnosc/f:TerminPlatnosci/f:Termin"),
        "currency": text(fa, "f:KodWaluty"),
        "place": text(fa, "f:P_1M"),
        "seller": seller_dict,
        "buyer": buyer_dict,
        "lines": read_rows([r for r in rows if text(r, "f:StanPrzed") != "1"]),
        "by_rate": rates,
        "totals": {
            "net": float(sum(v for k, v in sums.items() if k.startswith("P_13"))),
            "vat": float(sum(v for k, v in sums.items() if k.startswith("P_14") and not k.endswith("W"))),
            "gross": float(Decimal(text(fa, "f:P_15"))),
        },
        "iban": iban_from(text(fa, "f:Platnosc/f:RachunekBankowy/f:NrRB")),
        "notes": ["reverse charge"] if text(fa, "f:Adnotacje/f:P_18") == "1" else [],
    }
    ksef_root_no = read_ksef_number_from_root(root, fa)
    if ksef_root_no:
        out_data["ksef_number"] = ksef_root_no

    p3_nodes = root.findall("f:Podmiot3", F)
    if p3_nodes:
        p3_list = []
        for p3 in p3_nodes:
            p3_item = {
                "name": text(p3, "f:DaneIdentyfikacyjne/f:Nazwa"),
                "tax_id": (text(p3, "f:DaneIdentyfikacyjne/f:NIP")
                           or text(p3, "f:DaneIdentyfikacyjne/f:IDWew")
                           or text(p3, "f:DaneIdentyfikacyjne/f:NrVatUE")
                           or text(p3, "f:DaneIdentyfikacyjne/f:NrID")),
                "country": (text(p3, "f:Adres/f:KodKraju")
                            or text(p3, "f:DaneIdentyfikacyjne/f:KodUE")
                            or text(p3, "f:DaneIdentyfikacyjne/f:KodKraju") or "PL"),
                "address": {"line1": text(p3, "f:Adres/f:AdresL1"), "line2": text(p3, "f:Adres/f:AdresL2")},
                "role": int(text(p3, "f:Rola")) if text(p3, "f:Rola") else 2,
            }
            if text(p3, "f:DaneIdentyfikacyjne/f:IDWew"):
                p3_item["id_wew"] = text(p3, "f:DaneIdentyfikacyjne/f:IDWew")
            if text(p3, "f:DaneKontaktowe/f:Email"):
                p3_item["email"] = text(p3, "f:DaneKontaktowe/f:Email")
            if text(p3, "f:DaneKontaktowe/f:Telefon"):
                p3_item["phone"] = text(p3, "f:DaneKontaktowe/f:Telefon")
            p3_list.append(p3_item)
        out_data["podmiot3"] = p3_list

    flags = {"cash_method": "P_16", "self_billing": "P_17", "split_payment": "P_18A"}
    out_data.update({k: True for k, tag in flags.items() if text(fa, f"f:Adnotacje/f:{tag}") == "1"})
    if text(fa, "f:Adnotacje/f:Zwolnienie/f:P_19A"):
        out_data["exemption_basis"] = text(fa, "f:Adnotacje/f:Zwolnienie/f:P_19A")
    for vat_f in ("P_14_1", "P_14_2", "P_14_3"):
        if sums.get(vat_f) and sums.get(vat_f + "W"):
            out_data["fx_rate"] = float(round(sums[vat_f + "W"] / sums[vat_f], 4))
            break
    if kind in CORRECTION_KINDS:
        ref = fa.find("f:DaneFaKorygowanej", F)
        out_data["lines_before"] = read_rows([r for r in rows if text(r, "f:StanPrzed") == "1"])
        if ref is not None:
            out_data["corrects"] = {
                "number": text(ref, "f:NrFaKorygowanej"),
                "issue_date": text(ref, "f:DataWystFaKorygowanej"),
                "ksef_number": text(ref, "f:NrKSeFFaKorygowanej"),
            }
        out_data["reason"] = text(fa, "f:PrzyczynaKorekty")
        typ_kor = text(fa, "f:TypKorekty")
        if typ_kor and int(typ_kor) != 2:
            out_data["correction_effect"] = int(typ_kor)
    if kind == "advance":
        out_data["paid"] = out_data["totals"]["gross"]
        out_data["paid_date"] = text(fa, "f:Platnosc/f:DataZaplaty")
        out_data["order_lines"] = read_rows(
            fa.findall("f:Zamowienie/f:ZamowienieWiersz", F),
            "f:P_12Z", "f:P_11NettoZ", "f:P_7Z", "f:P_8BZ", "f:P_8AZ", "f:P_9AZ", "f:GTUZ"
        )
    if kind in ("final", "kor_roz") or fa.findall("f:FakturaZaliczkowa", F):
        adv_list = [
            {"number": text(a, "f:NrFaZaliczkowej"), "ksef_number": text(a, "f:NrKSeFFaZaliczkowej")}
            for a in fa.findall("f:FakturaZaliczkowa", F)
        ]
        if kind == "final" and adv_list and out_data["lines"]:
            order_by_rate = by_rate(parse_lines(out_data["lines"], "line"))
            inv_by_rate = {
                r: {"net": Decimal(str(v["net"])), "vat": Decimal(str(v["vat"]))}
                for r, v in out_data["by_rate"].items()
            }
            deducted = subtract(order_by_rate, inv_by_rate)
            adv_list[0]["by_rate"] = {
                r: {"net": float(v["net"]), "vat": float(v["vat"])}
                for r, v in deducted.items()
                if v["net"] != 0 or v["vat"] != 0
            }
            for extra_adv in adv_list[1:]:
                extra_adv["by_rate"] = {}
        out_data["advances"] = adv_list

    gtus = sorted({
        r["gtu"]
        for r in out_data["lines"] + out_data.get("lines_before", []) + out_data.get("order_lines", [])
        if r.get("gtu")
    })
    if gtus:
        out_data["gtu"] = gtus
    return out_data


def correct_invoice(orig_tree, changes):
    orig = read(orig_tree) if not isinstance(orig_tree, dict) else orig_tree
    ksef_no = (
        changes.get("ksef_number")
        or (changes.get("corrects") or {}).get("ksef_number")
        or orig.get("ksef_number")
    )
    if not ksef_no:
        raise InvoiceError(
            "Oryginał nie ma numeru KSeF. Podaj pole ksef_number (lub corrects.ksef_number) w pliku zmian, "
            "aby wystawić korektę faktury z KSeF."
        )
    orig_type = orig.get("type", "invoice")
    if changes.get("type"):
        corr_type = norm_kind(changes["type"])
    elif orig_type == "advance":
        corr_type = "kor_zal"
    elif orig_type == "final":
        corr_type = "kor_roz"
    else:
        corr_type = "correction"

    before = changes.get("lines_before")
    if before is None:
        before = orig.get("lines") if orig.get("lines") else orig.get("order_lines", [])

    merged = {**orig, **changes}
    merged["type"] = corr_type
    merged["number"] = changes.get("number") or f"KOR/{orig['number']}"
    merged["lines_before"] = before
    if "lines" not in changes:
        merged["lines"] = orig.get("lines") or []
    merged["corrects"] = {
        **(changes.get("corrects") or {}),
        "number": (changes.get("corrects") or {}).get("number") or orig["number"],
        "issue_date": (changes.get("corrects") or {}).get("issue_date") or orig["issue_date"],
        "ksef_number": ksef_no,
    }
    return build(merged)


def resolve_xml_targets(targets):
    files = []
    for target in targets:
        p = Path(target)
        if p.is_dir():
            matched = sorted(p.glob("*.xml")) or sorted(p.rglob("*.xml"))
            files.extend(matched)
        elif any(ch in target for ch in ("*", "?", "[")):
            matched = sorted(Path(m) for m in glob.glob(target, recursive=True) if Path(m).is_file())
            files.extend(matched)
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"Brak pliku lub katalogu: {target}. Sprawdź podaną ścieżkę.")
    seen = set()
    unique = []
    for f in files:
        key = str(f)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    if not unique:
        raise FileNotFoundError("Nie znaleziono żadnych plików XML do walidacji. Sprawdź ścieżkę lub wzorzec glob.")
    return unique


def out(payload, code):
    if SCHEMA_WARNINGS and isinstance(payload, dict) and "warnings" not in payload:
        payload["warnings"] = list(SCHEMA_WARNINGS)
        payload["schema_version"] = SCHEMA_VERSION
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))
    sys.exit(code)


def main():
    SCHEMA_WARNINGS.clear()
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("build", "validate", "read", "correct"):
        print(__doc__.strip())
        sys.exit(2)
    cmd = args[0]
    try:
        if cmd == "build":
            if len(args) < 3:
                out({"error": "Polecenie build wymaga argumentów: INVOICE.json OUT.xml"}, 2)
            src, dst = args[1], args[2]
            with open(src, encoding="utf-8") as f:
                tree = build(json.load(f))
            tree.write(dst, xml_declaration=True, encoding="UTF-8", pretty_print=True)
            issues = check(etree.parse(dst))
            out({"out": dst, "status": "issues" if issues else "ok", "issues": issues}, 1 if issues else 0)

        if cmd == "correct":
            if len(args) < 4:
                out({"error": "Polecenie correct wymaga argumentów: ORYGINAL.xml ZMIANY.json OUT.xml"}, 2)
            orig_path, changes_path, dst = args[1], args[2], args[3]
            orig_tree = etree.parse(orig_path)
            with open(changes_path, encoding="utf-8") as f:
                changes = json.load(f)
            tree = correct_invoice(orig_tree, changes)
            tree.write(dst, xml_declaration=True, encoding="UTF-8", pretty_print=True)
            issues = check(etree.parse(dst))
            out({"out": dst, "status": "issues" if issues else "ok", "issues": issues}, 1 if issues else 0)

        if cmd == "validate":
            csv_path = None
            targets = []
            i = 1
            while i < len(args):
                if args[i] == "--csv":
                    if i + 1 >= len(args):
                        out({"error": "Opcja --csv wymaga podania ścieżki do pliku wyjściowego."}, 2)
                    csv_path = args[i + 1]
                    i += 2
                elif args[i].startswith("--csv="):
                    csv_path = args[i].split("=", 1)[1]
                    i += 1
                else:
                    targets.append(args[i])
                    i += 1
            if not targets:
                out({"error": "Polecenie validate wymaga podania pliku, katalogu lub wzorca glob."}, 2)
            xml_files = resolve_xml_targets(targets)
            results = []
            for xf in xml_files:
                try:
                    t = etree.parse(str(xf))
                    file_issues = check(t)
                except etree.XMLSyntaxError as exc:
                    file_issues = [f"Błąd składni XML: {exc}. Sprawdź domknięcie znaczników i kodowanie UTF-8."]
                results.append({
                    "file": str(xf),
                    "status": "issues" if file_issues else "ok",
                    "issues": file_issues,
                })
            summary = {
                "ok": sum(1 for r in results if r["status"] == "ok"),
                "issues": sum(1 for r in results if r["status"] == "issues"),
            }
            if csv_path:
                with open(csv_path, "w", encoding="utf-8", newline="") as cf:
                    writer = csv.writer(cf)
                    writer.writerow(["file", "status", "first_issue"])
                    for r in results:
                        writer.writerow([r["file"], r["status"], r["issues"][0] if r["issues"] else ""])
            out({"files": results, "summary": summary}, 1 if summary["issues"] > 0 else 0)

        src = args[1]
        tree = etree.parse(src)
        out(read(tree), 0)
    except InvoiceError as exc:
        out({"status": "issues", "issues": [str(exc)]}, 1)
    except (OSError, ValueError, KeyError, etree.XMLSyntaxError) as exc:
        out({"error": f"{type(exc).__name__}: {exc}"}, 2)


if __name__ == "__main__":
    main()
