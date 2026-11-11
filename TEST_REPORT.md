# Raport testów

Projekt: **Uniwersalny konwerter plików**
Data: 2026-10-21
Autor: Anastasiia Nereschenko

## Środowisko

| Element | Wartość |
|---------|---------|
| System | macOS 26.5 (arm64) |
| Python | 3.12.13 (Homebrew) |
| Tkinter | 9.0.3 |
| python-docx | 1.2.0 |
| odfpy | 1.4.1 |
| CustomTkinter | 6.0.0 |
| pytest | 8.4.2 |
| LibreOffice | 26.8.1.1 |

## Testy automatyczne

Polecenie:

```bash
python -m pytest -v
```

Wynik:

```text
33 passed in 5.75s
```

| Plik | Zakres | Liczba testów |
|------|--------|---------------|
| `tests/test_registry.py` | rejestr, walidacja, konflikt nazw, unikalne nazwy, nazwa użytkownika | 10 |
| `tests/test_data.py` | CSV → JSON, JSON → CSV, polskie znaki, puste wartości, błędny JSON | 8 |
| `tests/test_text.py` | TXT ↔ DOCX, TXT ↔ ODT, tabele DOCX, uszkodzone pliki, CP1250 | 6 |
| `tests/test_office.py` | brak LibreOffice oraz DOCX/ODT → PDF/ODT/DOCX | 5 |
| `tests/test_cli.py` | konwersja przez CLI, błąd wejścia, unikalna i własna nazwa | 4 |

Testy LibreOffice są automatycznie pomijane, jeśli `soffice` nie jest dostępny
(`skipif`), dzięki czemu pakiet testów działa również na maszynie bez tego pakietu.

## Testy manualne — minimalna macierz

| # | Przypadek | Dane wejściowe | Oczekiwany rezultat | Wynik |
|---|-----------|----------------|---------------------|-------|
| 1 | CSV → JSON | `samples/sample.csv` | 4 obiekty, kolejność kolumn, polskie znaki, puste `uwagi` | PASS |
| 2 | JSON → CSV | `samples/sample.json` | 3 wiersze, unia kluczy, `true`/`false`, brakujące pole puste | PASS |
| 3 | CSV → JSON → CSV | `samples/sample.csv` | plik identyczny z wejściem (poza kolejnością cudzysłowów CSV) | PASS |
| 4 | TXT → DOCX | `samples/sample.txt` | plik otwieralny, 4 akapity, łamanie wierszy i polskie znaki | PASS |
| 5 | TXT → ODT | `samples/sample.txt` | plik otwieralny, 4 akapity, łamanie wierszy i polskie znaki | PASS |
| 6 | DOCX → TXT | `samples/sample.docx` | treść identyczna z `samples/sample.txt` | PASS |
| 7 | ODT → TXT | `samples/sample.odt` | treść identyczna z `samples/sample.txt` | PASS |
| 8 | DOCX → PDF | `samples/sample.docx` | PDF 1.7, 1 strona, tekst z polskimi znakami | PASS |
| 9 | ODT → PDF | `samples/sample.odt` | PDF 1.7, 1 strona, tekst z polskimi znakami | PASS |
| 10 | DOCX → ODT | `samples/sample.docx` | poprawny plik OpenDocument, otwieralny przez odfpy | PASS |
| 11 | ODT → DOCX | `samples/sample.odt` | poprawny plik OOXML, otwieralny przez python-docx | PASS |
| 12 | CSV → JSON z własną nazwą | `samples/sample.csv`, nazwa `mój raport` | plik `mój raport.json` z poprawną treścią | PASS |

Weryfikacja PDF: tekst wyodrębniony przez PDFKit zawiera m.in.
`Uniwersalny konwerter plików`, `ąćęłńóśźż` oraz `zażółć gęślą jaźń`.

## Testy błędów i przypadków brzegowych

| Przypadek | Oczekiwany rezultat | Wynik |
|-----------|---------------------|-------|
| Nieistniejący plik wejściowy | komunikat „Plik wejściowy nie istnieje” + wskazówka, kod CLI 1 | PASS |
| Nieobsługiwana para (CSV → PDF) | GUI nie pokazuje formatu; CLI zwraca kontrolowany błąd | PASS |
| Błędna składnia JSON | komunikat z numerem wiersza i kolumny, brak awarii | PASS |
| JSON inny niż tablica obiektów | opis oczekiwanej struktury, brak awarii | PASS |
| Uszkodzony DOCX/ODT | kontrolowany błąd otwarcia pliku | PASS |
| Brak katalogu docelowego | walidacja przed konwersją, czytelny komunikat | PASS |
| Plik docelowy istnieje | CLI: błąd lub `--on-exists unique/overwrite`; GUI: pytanie o nadpisanie | PASS |
| Brak LibreOffice | `DependencyError` z instrukcją instalacji (test z podstawioną detekcją) | PASS |
| Polskie znaki i puste wartości | zachowane w CSV, JSON, TXT, DOCX, ODT i PDF | PASS |
| Puste pola w GUI | ostrzeżenie, brak próby konwersji | PASS |
| Dłuższa konwersja | GUI pracuje w wątku, okno się nie zamraża | PASS |

## Test GUI

Interfejs CustomTkinter sprawdzono skryptami uruchamiającymi prawdziwe okno aplikacji:

- wybór `samples/sample.csv`, automatyczne ustawienie katalogu i nazwy `sample`,
- dynamiczna zmiana formatów: `sample.csv` → `.json`; `sample.txt` → `.docx`, `.odt`;
  `sample.docx` → `.odt`, `.pdf`, `.txt`,
- wpisanie własnej nazwy `mój raport`, podgląd `mój raport.json` i zapis pliku,
- panel statusu po sukcesie pokazuje akcje „Otwórz wynik”, „Pokaż w folderze”,
  „Otwórz folder”,
- okno konfliktu nazw zwraca poprawne decyzje `unique` / `overwrite` / anulowanie,
- przełączanie motywu systemowy/jasny/ciemny działa bez restartu,
- przycisk „Otwórz folder” przy pliku wejściowym i katalogu docelowym jest aktywny
  tylko dla istniejących ścieżek,
- okno ma układ dwukolumnowy: po lewej plik i ustawienia, po prawej status i pomoc,
- paleta ukiyo-e (washi, indygo, vermilion, teal), gradientowy pasek nieba i przełączanie motywu działają w obu trybach,
- ilustracje są skalowane do rozmiarów 42×42 (logo), 250×89 (gałąź) i 52×70 (kot),
  więc nie rozciągają się na całą aplikację i nie zmieniają układu okna.

## Znane problemy

- Systemowy Python na macOS (`/usr/bin/python3`) ma Tk 8.5, który może wyświetlać
  puste, szare okno. Projekt wykrywa ten przypadek i kończy się instrukcją instalacji;
  rozwiązaniem jest Python z Homebrew z `python-tk` (Tk 9.0.3). Testy GUI wykonano
  na Pythonie 3.12.13 z Tk 9.0.3.
- Brak otwartych błędów krytycznych. Ograniczenia funkcjonalne opisano w README
  (brak PDF jako wejścia, utrata złożonego formatowania, wymóg LibreOffice dla grupy C).
