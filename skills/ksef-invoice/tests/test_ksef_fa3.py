import copy
import csv
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SKILL_DIR / "scripts" / "ksef_fa3.py"
EXAMPLES_DIR = SKILL_DIR / "examples"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import ksef_fa3  # noqa: E402

TYPES = ["invoice", "correction", "advance", "final", "kor_zal", "kor_roz"]


def run_cli(*args, env=None):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
    )
    stdout = proc.stdout.strip()
    payload = json.loads(stdout) if stdout.startswith("{") else stdout
    return proc.returncode, payload


@pytest.mark.parametrize("kind", TYPES)
def test_example_pairs_valid(kind, tmp_path):
    json_path = EXAMPLES_DIR / f"{kind}.json"
    xml_path = EXAMPLES_DIR / f"{kind}.xml"
    assert json_path.exists()
    assert xml_path.exists()

    # Walidacja istniejącego pliku XML z examples/
    tree = etree.parse(str(xml_path))
    assert ksef_fa3.check(tree) == []

    # Zbudowanie z JSON i porównanie odczytanych danych
    out_xml = tmp_path / f"{kind}.xml"
    code, res = run_cli("build", json_path, out_xml)
    assert code == 0
    assert res["status"] == "ok"
    assert res["issues"] == []
    assert ksef_fa3.read(etree.parse(str(out_xml))) == ksef_fa3.read(tree)


@pytest.mark.parametrize("kind", TYPES)
def test_roundtrip_build_read_build(kind):
    with open(EXAMPLES_DIR / f"{kind}.json", encoding="utf-8") as f:
        inv = json.load(f)
    tree1 = ksef_fa3.build(inv)
    assert ksef_fa3.check(tree1) == []
    read1 = ksef_fa3.read(tree1)

    tree2 = ksef_fa3.build(read1)
    assert ksef_fa3.check(tree2) == []
    read2 = ksef_fa3.read(tree2)

    assert read1 == read2


def test_corrupted_files_detected(tmp_path):
    base_xml = EXAMPLES_DIR / "invoice.xml"
    kor_xml = EXAMPLES_DIR / "correction.xml"
    kor_zal_xml = EXAMPLES_DIR / "kor_zal.xml"
    kor_roz_xml = EXAMPLES_DIR / "kor_roz.xml"
    ns = {"f": ksef_fa3.NS}

    # 1. Zła suma netto P_13_1 względem pozycji
    t_sum = etree.parse(str(base_xml))
    t_sum.find(".//f:P_13_1", ns).text = "99999.00"
    issues_sum = ksef_fa3.check(t_sum)
    assert any("P_13_1" in msg for msg in issues_sum)

    # 2. Zła kwota VAT P_14_1 oraz zła należność P_15
    t_vat = etree.parse(str(base_xml))
    t_vat.find(".//f:P_14_1", ns).text = "100.00"
    issues_vat = ksef_fa3.check(t_vat)
    assert any("P_14_1" in msg for msg in issues_vat)
    assert any("P_15" in msg for msg in issues_vat)

    # 3. Zły NIP sprzedawcy i nabywcy
    t_nip = etree.parse(str(base_xml))
    t_nip.find(".//f:Podmiot1/f:DaneIdentyfikacyjne/f:NIP", ns).text = "1234560008"
    t_nip.find(".//f:Podmiot2/f:DaneIdentyfikacyjne/f:NIP", ns).text = "9876540017"
    issues_nip = ksef_fa3.check(t_nip)
    assert any("NIP sprzedawcy" in msg for msg in issues_nip)
    assert any("NIP nabywcy" in msg for msg in issues_nip)

    # 4. KOR bez DaneFaKorygowanej
    t_kor = etree.parse(str(kor_xml))
    fa_kor = t_kor.find(".//f:Fa", ns)
    for el in list(fa_kor):
        if etree.QName(el).localname in ("PrzyczynaKorekty", "TypKorekty", "DaneFaKorygowanej"):
            fa_kor.remove(el)
    issues_kor = ksef_fa3.check(t_kor)
    assert any("DaneFaKorygowanej" in msg for msg in issues_kor)

    # 5. KOR_ZAL bez referencji do faktury zaliczkowej
    t_kzal = etree.parse(str(kor_zal_xml))
    fa_kzal = t_kzal.find(".//f:Fa", ns)
    for el in list(fa_kzal):
        if etree.QName(el).localname in ("PrzyczynaKorekty", "TypKorekty", "DaneFaKorygowanej"):
            fa_kzal.remove(el)
    issues_kzal = ksef_fa3.check(t_kzal)
    assert any("KOR_ZAL" in msg and "zaliczkowej" in msg for msg in issues_kzal)

    # 6. KOR_ROZ bez FakturaZaliczkowa
    t_kroz = etree.parse(str(kor_roz_xml))
    fa_kroz = t_kroz.find(".//f:Fa", ns)
    for el in list(fa_kroz):
        if etree.QName(el).localname == "FakturaZaliczkowa":
            fa_kroz.remove(el)
    issues_kroz = ksef_fa3.check(t_kroz)
    assert any("KOR_ROZ" in msg and "FakturaZaliczkowa" in msg for msg in issues_kroz)


def test_validate_file_dir_glob_and_csv(tmp_path):
    ok_file = tmp_path / "ok.xml"
    bad_file = tmp_path / "bad.xml"
    ok_file.write_bytes((EXAMPLES_DIR / "invoice.xml").read_bytes())

    t_bad = etree.parse(str(ok_file))
    t_bad.find(".//{http://crd.gov.pl/wzor/2025/06/25/13775/}P_15").text = "1.00"
    t_bad.write(str(bad_file), xml_declaration=True, encoding="UTF-8")

    # Pojedynczy poprawny plik
    code_ok, payload_ok = run_cli("validate", ok_file)
    assert code_ok == 0
    assert payload_ok["summary"] == {"ok": 1, "issues": 0}
    assert len(payload_ok["files"]) == 1
    assert payload_ok["files"][0]["status"] == "ok"

    # Katalog z plikiem poprawnym i błędnym + zapis CSV
    csv_out = tmp_path / "report.csv"
    code_dir, payload_dir = run_cli("validate", tmp_path, "--csv", csv_out)
    assert code_dir == 1
    assert payload_dir["summary"] == {"ok": 1, "issues": 1}
    assert csv_out.exists()
    with open(csv_out, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    by_status = {r["status"]: r for r in rows}
    assert by_status["ok"]["first_issue"] == ""
    assert "P_15" in by_status["issues"]["first_issue"]

    # Glob
    code_glob, payload_glob = run_cli("validate", f"{tmp_path}/*.xml")
    assert code_glob == 1
    assert payload_glob["summary"] == {"ok": 1, "issues": 1}


def test_correct_command(tmp_path):
    orig_xml = EXAMPLES_DIR / "invoice.xml"
    out_xml = tmp_path / "korekta.xml"

    # Odmowa gdy brak numeru KSeF
    changes_no_ksef = tmp_path / "changes_no_ksef.json"
    changes_no_ksef.write_text(
        json.dumps({"number": "FVK/9/11/2026", "reason": "Rabat", "lines": []}),
        encoding="utf-8",
    )
    code_err, payload_err = run_cli("correct", orig_xml, changes_no_ksef, out_xml)
    assert code_err == 1
    assert payload_err["status"] == "issues"
    assert any("KSeF" in msg for msg in payload_err["issues"])

    # Poprawna korekta z numerem KSeF
    changes_ok = tmp_path / "changes_ok.json"
    changes_ok.write_text(
        json.dumps(
            {
                "number": "FVK/1/11/2026",
                "ksef_number": "1234560007-20261108-0A1B2C-3D4E5F-A1",
                "reason": "Rabat - 10 godzin mniej",
                "lines": [
                    {
                        "description": "Programowanie 10/2026",
                        "qty": 150,
                        "unit": "godz.",
                        "unit_net": 150,
                        "vat_rate": "23",
                    },
                    {
                        "description": "Hosting",
                        "qty": 1,
                        "unit_net": 99.99,
                        "vat_rate": "23",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    code_ok, payload_ok = run_cli("correct", orig_xml, changes_ok, out_xml)
    assert code_ok == 0
    assert payload_ok["status"] == "ok"
    data = ksef_fa3.read(etree.parse(str(out_xml)))
    assert data["type"] == "correction"
    assert data["totals"]["gross"] == -1845.0
    assert data["corrects"]["ksef_number"] == "1234560007-20261108-0A1B2C-3D4E5F-A1"
    assert len(data["lines_before"]) == 2


def test_gtu_and_podmiot3_jst_gv():
    with open(EXAMPLES_DIR / "invoice.json", encoding="utf-8") as f:
        inv = json.load(f)

    inv_gtu = copy.deepcopy(inv)
    inv_gtu["lines"][0]["gtu"] = "GTU_12"
    inv_gtu["lines"][1]["gtu"] = "GTU_01"
    inv_gtu["podmiot3"] = [
        {
            "name": "Szkoła Podstawowa nr 1",
            "id_wew": "9876540016-00001",
            "address": {"line1": "ul. Szkolna 10", "line2": "30-001 Kraków"},
            "role": "jst",
        },
        {
            "name": "Acme Oddział Spółka z Grupy VAT",
            "tax_id": "9876540016",
            "address": {"line1": "ul. Grupy 2", "line2": "30-001 Kraków"},
            "role": "gv",
        },
    ]
    tree = ksef_fa3.build(inv_gtu)
    assert ksef_fa3.check(tree) == []

    ns = {"f": ksef_fa3.NS}
    assert tree.find(".//f:Podmiot2/f:JST", ns).text == "1"
    assert tree.find(".//f:Podmiot2/f:GV", ns).text == "1"
    roles = [el.text for el in tree.findall(".//f:Podmiot3/f:Rola", ns)]
    assert roles == ["8", "10"]
    gtus = [el.text for el in tree.findall(".//f:FaWiersz/f:GTU", ns)]
    assert gtus == ["GTU_12", "GTU_01"]

    # Roundtrip build -> read -> build dla GTU i Podmiot3
    read1 = ksef_fa3.read(tree)
    assert read1["gtu"] == ["GTU_01", "GTU_12"]
    assert len(read1["podmiot3"]) == 2
    tree2 = ksef_fa3.build(read1)
    assert ksef_fa3.check(tree2) == []
    assert ksef_fa3.read(tree2) == read1

    # Błędny kod GTU
    inv_bad_gtu = copy.deepcopy(inv)
    inv_bad_gtu["lines"][0]["gtu"] = "GTU_99"
    with pytest.raises(ksef_fa3.InvoiceError, match="GTU"):
        ksef_fa3.build(inv_bad_gtu)


def test_local_schema_and_fallback_warning(tmp_path, monkeypatch):
    # Domyślnie używa lokalnego katalogu xsd/1-0E bez ostrzeżeń
    ksef_fa3.SCHEMA_WARNINGS.clear()
    ksef_fa3.schema()
    assert ksef_fa3.SCHEMA_WARNINGS == []

    # Fallback sieciowy z ostrzeżeniem, gdy lokalny katalog jest pusty
    empty_xsd_dir = tmp_path / "empty_xsd"
    monkeypatch.setenv("KSEF_SCHEMA_DIR", str(empty_xsd_dir))

    class DummyResp:
        def __init__(self, data):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_urlopen(url, timeout=30):
        name = url.rsplit("/", 1)[-1]
        return DummyResp((ksef_fa3.BUNDLED_XSD_DIR / name).read_bytes())

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        ksef_fa3.schema()
    assert len(ksef_fa3.SCHEMA_WARNINGS) == 1
    assert ksef_fa3.SCHEMA_VERSION in ksef_fa3.SCHEMA_WARNINGS[0]
