---
name: ksef-invoice
description: Wystawia, waliduje, odczytuje i koryguje e-faktury KSeF (FA(3) XML) - faktury VAT, korekty, zaliczki i rozliczenia - zgodnie ze schematem XSD. Użyj przy e-fakturze, KSeF, korekcie, zaliczce lub odrzuconym pliku XML.
---

# KSeF Invoice (FA(3))

Skrypt: `python scripts/ksef_fa3.py build|validate|read|correct ...` (względem katalogu skilla). Wymaga `pip install lxml`. Schemat XSD FA(3) w wersji `1-0E` jest wbudowany w `xsd/1-0E/` (sieć z `crd.gov.pl` tylko jako fallback). Odpowiadaj po polsku, chyba że użytkownik pisze w innym języku.

Dane sprzedawcy: jeśli w katalogu roboczym jest `ksef-firma.json`, weź z niego `seller` i `iban`. Jeśli nie ma, zapytaj raz i zaproponuj zapisanie. Numer faktury: zaproponuj kolejny na podstawie plików XML w folderze (`read`), poproś o potwierdzenie.

Wybierz `type` (przykłady w `examples/<type>.json`):
- `invoice` (VAT): zwykła faktura, `lines[]`.
- `correction` (KOR): korekta zwykłej faktury, `corrects` {number, issue_date, ksef_number}, `lines_before` (stan przed), `lines` (stan po, `[]` = korekta do zera), `reason`, `correction_effect` (1 w dacie pierwotnej, 2 w dacie korekty - domyślnie, 3 inna). Dla faktury z KSeF użyj `ksef_fa3.py correct ORYGINAL.xml ZMIANY.json OUT.xml`.
- `advance` (ZAL): zaliczka, `order_lines` (całe zamówienie), `paid` (otrzymana kwota brutto), `paid_date`. Skrypt sam dzieli wpłatę na stawki VAT.
- `final` (ROZ): rozliczenie po zaliczkach, `lines` (całe zamówienie), `advances[]` {number, ksef_number, by_rate}. `by_rate` weź z `read` każdej zaliczki XML.
- `kor_zal` (KOR_ZAL): korekta zaliczki, szkielet jak `correction` (`corrects` wskazuje korygowaną zaliczkę, `lines_before`, `lines`).
- `kor_roz` (KOR_ROZ): korekta faktury rozliczającej, szkielet jak `correction` plus `advances[]` {number, ksef_number} (`FakturaZaliczkowa`).

Pola wspólne: `seller` {name, tax_id, address.line1/line2}; `buyer` (PL NIP, UE `country`+VAT, inny `country`+ID, osoba prywatna: bez `tax_id`); `podmiot3[]` lub `recipient` {name, tax_id lub id_wew, address, role: `odbiorca` (2), `jst` (8 - ustawia `JST=1` w `Podmiot2`), `gv` (10 - ustawia `GV=1` w `Podmiot2`) lub 1..11}; `lines[]` {description, qty, unit, unit_net lub net, vat_rate: `23` `8` `5` `0 KR` `0 WDT` `0 EX` `zw` `np I` `np II` `oo`, opcjonalnie `gtu`: `GTU_01`..`GTU_13` (`FaWiersz/GTU`, w zaliczce `ZamowienieWiersz/GTUZ`)}; opcjonalnie `sale_date`, `due_date`, `iban`, `place`, `currency`+`fx_rate`, `exemption_basis` (wymagane dla `zw`), `split_payment`, `cash_method`, `self_billing`.

Kroki:
1. Uzupełnij JSON. Dopytaj o brakujące dane - nigdy nie zmyślaj NIP, numeru, daty, kwoty ani numeru KSeF.
2. Zbuduj XML: `ksef_fa3.py build invoice.json FV-1-11-2026.xml` albo skoryguj oryginał z KSeF: `ksef_fa3.py correct FV-1-11-2026.xml zmiany.json FVK-1-11-2026.xml`.
3. Pokaż: typ, numer, nabywcę, netto/VAT/brutto wg stawek (ujemne przy korekcie zmniejszającej), ścieżkę pliku oraz następny krok: wysyłka XML w Aplikacji Podatnika KSeF lub programie księgowym.

Walidacja (plik, katalog lub glob): `ksef_fa3.py validate sciezka [--csv raport.csv]` - lokalny XSD, sumy względem pozycji, VAT, P_15, NIP, referencje korekt i zaliczek. Wyjaśnij każdy błąd prostym językiem wraz z poprawką.
Odczyt: `ksef_fa3.py read plik.xml` -> JSON. Przy wielu plikach eksportuj ze skillami `invoice-processing` i `xlsx-toolkit`.

Zasady bezwzględne:
- Nieobsługiwane: procedura marży, nowe środki transportu, załączniki. Poinformuj o tym wprost.
- Nigdy nie wysyłaj plików do KSeF, nie proś o token ani certyfikat KSeF.
- Stawka VAT, podstawa zwolnienia, odwrotne obciążenie, kody GTU i data ujęcia korekty to decyzja podatnika lub księgowego - sygnalizuj wątpliwości, nie decyduj za użytkownika.
