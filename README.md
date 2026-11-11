# Uniwersalny konwerter plików

## Cel

Aplikacja desktopowa w Pythonie 3 z interfejsem CustomTkinter (na bazie Tkinter),
która konwertuje pliki CSV, JSON, TXT, DOCX, ODT i PDF. Użytkownik wybiera plik
wejściowy, katalog zapisu oraz format docelowy; lista formatów jest ograniczona
do rzeczywiście obsługiwanych par. Dostępny jest też tryb CLI.

Projekt zaliczeniowy z przedmiotu **Programowanie V** (Projekt 1).

**Autor:** Anastasiia Nerestenko

Historia zmian: [`CHANGELOG.md`](CHANGELOG.md) oraz repozytorium Git.

## Funkcje

- 10 kierunków konwersji w trzech grupach: dane strukturalne, tekst/dokumenty i formaty biurowe.
- Interfejs inspirowany japońskim drzeworytem ukiyo-e: papier washi, tusz, indygo, vermilion, herbata i akcent sakury.
- Dynamiczna lista formatów docelowych zależna od rozszerzenia pliku wejściowego.
- Własna nazwa pliku wynikowego z podglądem i automatycznym rozszerzeniem.
- Szybki dostęp do folderu pliku wejściowego oraz wyników („Otwórz folder”, „Pokaż w folderze”).
- Delikatne ilustracje sakury (kwiat, gałąź, kot) w stałych, niewielkich rozmiarach — bez rozciągania na całe okno.
- Walidacja wejścia, katalogu zapisu, uprawnień, pary formatów i konfliktu nazw.
- Bezpieczna obsługa nadpisywania: okno wyboru w GUI, polityki `error`/`overwrite`/`unique` w CLI.
- Praca w wątku roboczym — interfejs nie zamarza podczas konwersji.
- Czytelne komunikaty błędów z przyczyną i wskazówką, bez blokujących okien, oraz dziennik zdarzeń.
- Rejestr konwerterów oddzielony od GUI; dodanie pary formatów nie wymaga przebudowy okna.
- Tryb CLI do testowania i uruchamiania bez GUI.

## Styl wizualny

Paleta i nastrój nawiązują do japońskiego drzeworytu: ciepły papier washi, tuszowa
czerń, głębokie indygo, vermilion pieczęci, herbaciany teal i pyłek sakury. Tytuł jest
złożony krojem Mincho, logo to kwiat sakury w czerwonej ramce, panel statusu zdobi
gałąź, a w ciemno-indygowej karcie pomocy siedzi mały kot szczęścia. Ilustracje mają
stałe, niewielkie rozmiary, dzięki czemu nie dominują nad interfejsem.

## Obsługiwane konwersje

| Grupa | Wejście | Wyjście | Implementacja | Ograniczenia |
|-------|---------|---------|---------------|--------------|
| A | `.csv` | `.json` | `csv` + `json` (biblioteka standardowa) | Wartości pozostają tekstowe; wymagany nagłówek |
| A | `.json` | `.csv` | `csv` + `json` (biblioteka standardowa) | Tylko tablica obiektów; obiekty zagnieżdżone trafiają do CSV jako JSON |
| B | `.txt` | `.docx` | `python-docx` | Bez formatowania; akapity i łamanie wierszy są zachowane |
| B | `.txt` | `.odt` | `odfpy` | Bez formatowania; akapity i łamanie wierszy są zachowane |
| B | `.docx` | `.txt` | `python-docx` | Tracone są style, obrazy i przypisy; proste tabele są spłaszczane do tekstu |
| B | `.odt` | `.txt` | `odfpy` | Tracone są style, obrazy i przypisy; proste tabele są spłaszczane do tekstu |
| C | `.docx` | `.pdf` | LibreOffice (headless) | Wymaga LibreOffice; układ może różnić się od oryginału |
| C | `.odt` | `.pdf` | LibreOffice (headless) | Wymaga LibreOffice; układ może różnić się od oryginału |
| C | `.docx` | `.odt` | LibreOffice (headless) | Wymaga LibreOffice; złożone formatowanie może zostać uproszczone |
| C | `.odt` | `.docx` | LibreOffice (headless) | Wymaga LibreOffice; złożone formatowanie może zostać uproszczone |

Aplikacja nie obsługuje PDF jako pliku wejściowego i nie obiecuje „dowolnej konwersji”.

## Wymagania

- Python 3.9 lub nowszy (z Tkinterem; w instalatorach Windows/macOS jest domyślnie).
- `customtkinter` — nowoczesny interfejs graficzny.
- `pillow` — skalowanie i wyświetlanie obrazów dekoracyjnych.
- `python-docx` — obsługa DOCX.
- `odfpy` — obsługa ODT.
- LibreOffice — wymagany wyłącznie dla czterech konwersji z grupy C (PDF/ODT/DOCX).

## Instalacja

### macOS

Systemowy `/usr/bin/python3` korzysta z Tk 8.5, który na współczesnym macOS może
pokazywać puste, szare okno. Dlatego na macOS zalecany jest Python z Homebrew z Tk 8.6+
(Homebrew instaluje Tk 9):

```bash
brew install python@3.12 python-tk@3.12
brew install --cask libreoffice
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -c "import tkinter; print('Tk', tkinter.TkVersion)"
```

Na Macu z procesorem Intel ścieżka to zwykle `/usr/local/bin/python3.12`.
Jeśli `TkVersion` jest mniejsze niż `8.6`, GUI może się nie wyświetlać poprawnie.

**Szare okno na macOS:** to znany problem Tk 8.5 dołączonego do systemowego Pythona,
a nie błąd konwertera. Rozwiązanie: utwórz środowisko interpreterem Homebrew
(`python@3.12` + `python-tk@3.12`) i zainstaluj zależności ponownie, tak jak wyżej.

### Linux (Debian/Ubuntu)

```bash
sudo apt install python3-tk libreoffice
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows

1. Zainstaluj Python 3.9+ (zaznacz „Add Python to PATH”).
2. Zainstaluj LibreOffice z <https://www.libreoffice.org/download/>.
3. W terminalu:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Jeśli LibreOffice nie jest wykrywany, wskaż ścieżkę do `soffice` zmienną środowiskową
`CONVERTER_SOFFICE`. Polecenie `python -m converter doctor` pokazuje stan zależności.

## Uruchomienie

### GUI

```bash
python main.py
```

lub:

```bash
python -m converter gui
```

Kolejność pracy: **Wybierz plik → Format docelowy → Katalog zapisu → Nazwa pliku → Konwertuj**.
Po wybraniu pliku można od razu otworzyć jego folder, a katalog zapisu i nazwa są
uzupełniane automatycznie. Rozszerzenie jest dodawane na podstawie wybranego formatu.

Jeśli plik docelowy istnieje, aplikacja pokazuje okno z wyborem: **Nadpisz**,
**Zapisz jako nową** (unikalna nazwa, np. `raport (1).pdf`) lub **Anuluj**.
Po konwersji panel statusu oferuje „Otwórz wynik”, „Pokaż w folderze” i „Otwórz folder”.
Motyw interfejsu (jasny, ciemny, systemowy) można przełączyć w prawym górnym rogu.

### CLI

```bash
python -m converter list
python -m converter doctor
python -m converter convert samples/sample.csv json -o output
python -m converter convert samples/sample.csv json -o output --name "raport końcowy"
python -m converter convert samples/sample.txt docx -o output
python -m converter convert samples/sample.txt odt -o output
python -m converter convert output/sample.docx pdf -o output
python -m converter convert output/sample.docx txt -o output
```

Opcje:

- `-o, --output` — katalog zapisu (domyślnie katalog pliku wejściowego),
- `-n, --name` — nazwa pliku wynikowego, z rozszerzeniem lub bez,
- `--on-exists error|overwrite|unique` — zachowanie przy istniejącym pliku docelowym,
- `--verbose` — szczegółowy dziennik (przed nazwą podpolecenia).

Kody wyjścia: `0` — sukces, `1` — kontrolowany błąd konwersji, `2` — błąd użycia CLI.

## Semantyka formatów

### CSV

- Wejście: UTF-8 (także z BOM), Windows-1250 lub ISO-8859-2.
- Separator wykrywany automatycznie spośród `,` `;` tabulator `|`; przy niepowodzeniu przecinek.
- Pierwszy wiersz jest nagłówkiem; nazwy kolumn muszą być niepuste i unikalne.
- Kolejność kolumn jest zachowywana, puste wartości pozostają puste.
- Wiersz z większą liczbą wartości niż nagłówek kończy się kontrolowanym błędem.
- Wynik JSON: tablica obiektów, UTF-8, wcięcie 2 spacje.

Przykład:

```csv
imię,nazwisko,miasto,uwagi
Zażółć,gęślą,Jaźń,
```

```json
[
  {
    "imię": "Zażółć",
    "nazwisko": "gęślą",
    "miasto": "Jaźń",
    "uwagi": ""
  }
]
```

### JSON

- Akceptowana struktura: tablica obiektów, np. `[{"a": "1"}, {"a": "2"}]`.
- Klucze muszą być tekstowe; kolejność kluczy jest zachowywana.
- Brakujący klucz w wierszu daje pustą komórkę; nowe klucze są dopisywane na końcu nagłówka.
- Wartości `null` → pusta komórka, booleany → `true`/`false`, liczby → tekst.
- Obiekty i tablice zagnieżdżone są zapisywane w komórce jako kompaktowy JSON.
- Pusta tablica `[]` daje pusty plik CSV.
- Błędna składnia JSON daje komunikat z numerem wiersza i kolumny.

### TXT

- Wejście: UTF-8, Windows-1250 lub ISO-8859-2.
- Akapit to blok oddzielony pustą linią; pojedyncze łamania wierszy wewnątrz akapitu
  są zachowywane jako łamanie wiersza w DOCX/ODT.
- Polskie znaki są zapisywane w UTF-8.

### DOCX / ODT / PDF

- DOCX i ODT → TXT: akapity oddzielone pustą linią, proste tabele jako wiersze rozdzielone
  tabulatorami. Formatowanie, obrazy i przypisy nie są przenoszone.
- Konwersje grupy C uruchamiają `soffice --headless` przez `subprocess` bez `shell=True`,
  z kontrolą kodu wyjścia, limitem czasu i osobnym profilem użytkownika.
- Narzędzie jest wykrywane na macOS, Linux i Windows; brak LibreOffice daje kontrolowany
  błąd z instrukcją instalacji. Ścieżkę można ustawić przez `CONVERTER_SOFFICE`,
  a limit czasu przez `CONVERTER_LO_TIMEOUT` (domyślnie 120 s).

## Obsługa błędów i dziennik

Walidowane są: istnienie i typ pliku, rozszerzenie, obsługiwana para formatów, istnienie
i uprawnienia katalogu docelowego, prawo odczytu pliku, konflikt nazw oraz niepuste wybory
w GUI. Błędy są logowane do `logs/converter.log` (rotacja, UTF-8). Ścieżkę można zmienić
zmienną `CONVERTER_LOG_FILE`. GUI pokazuje komunikat z przyczyną i dalszym krokiem.

## Testy

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

Testy automatyczne obejmują rejestr i walidację, konwersje CSV/JSON, TXT/DOCX/ODT,
obsługę błędów, politykę nadpisywania, CLI oraz konwersje LibreOffice (te ostatnie są
pomijane, gdy LibreOffice nie jest zainstalowany). Szczegóły i wyniki: [`TEST_REPORT.md`](TEST_REPORT.md).

Dane testowe znajdują się w katalogu `samples/`:

| Plik | Oczekiwany wynik |
|------|------------------|
| `samples/sample.csv` | `sample.json`: 4 obiekty, kolejność kolumn `imię, nazwisko, miasto, uwagi`, polskie znaki i puste wartości zachowane |
| `samples/sample.json` | `sample.csv`: 3 wiersze, unia kluczy `imię, nazwisko, miasto, wiek, aktywny, uwagi`, brakujące pola puste |
| `samples/sample.txt` | `sample.docx` / `sample.odt`: 4 akapity, wewnętrzne łamania wierszy i polskie znaki zachowane; po konwersji z powrotem do TXT treść jest identyczna |
| `samples/sample.docx` | `sample.pdf` oraz `sample.odt`: plik otwieralny, treść i polskie znaki zachowane |
| `samples/sample.odt` | `sample.docx` oraz `sample.pdf`: plik otwieralny, treść i polskie znaki zachowane |

Gotowe pliki `samples/sample.docx`, `samples/sample.odt` i `samples/sample.pdf` są
wynikami konwersji danych przykładowych i mogą służyć do szybkiego testu grup B i C.

## Struktura projektu

```text
.
├── main.py                     # punkt wejścia (GUI lub CLI)
├── converter/
│   ├── __main__.py             # python -m converter
│   ├── cli.py                  # CLI: list, doctor, convert, gui
│   ├── gui.py                  # CustomTkinter: karty, motywy, wątek roboczy, dialog konfliktu
│   ├── registry.py             # rejestr, walidacja, nazwa wyniku, execute()
│   ├── errors.py               # wspólny model błędów
│   ├── textio.py               # kodowania i dzielenie akapitów
│   ├── system.py               # otwieranie plików i folderów w systemie
│   ├── libreoffice.py          # wykrywanie i bezpieczne wywołanie soffice
│   └── converters/
│       ├── data.py             # CSV ↔ JSON
│       ├── text.py             # TXT ↔ DOCX/ODT
│       └── office.py           # DOCX/ODT ↔ PDF/ODT/DOCX
├── images/                     # ilustracje GUI (*_small.png)
├── samples/                    # dane testowe (min. 3 reprezentatywne)
├── tests/                      # testy pytest
├── TEST_REPORT.md              # raport testów
├── CHANGELOG.md                # dziennik zmian
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```


## Znane ograniczenia

- Brak konwersji z PDF do innych formatów.
- Konwersje dokumentów nie zachowują złożonego formatowania, osadzonych wykresów,
  przypisów, makr ani identycznego układu stron.
- Tabele DOCX/ODT są spłaszczane do tekstu rozdzielonego tabulatorami.
- Automatyczne wykrywanie separatora CSV może się pomylić dla plików jednokolumnowych;
  wtedy używany jest przecinek.
- Zagnieżdżone struktury JSON w CSV stają się tekstem JSON, a nie osobnymi kolumnami.
- Konwersje grupy C wymagają sprawnego LibreOffice; bez niego przycisk pozostaje dostępny,
  ale operacja kończy się czytelnym błędem z instrukcją instalacji.
- Aplikacja nie obsługuje pracy wsadowej ani przeciągania plików.

## Źródła i wykorzystane narzędzia

Dokumentacje:

- Tkinter i `tkinter.filedialog`: <https://docs.python.org/3/library/dialog.html>
- `subprocess`: <https://docs.python.org/3/library/subprocess.html>
- python-docx: <https://python-docx.readthedocs.io/>
- odfpy: <https://github.com/eea/odfpy>
- CustomTkinter: <https://customtkinter.tomschimansky.com/>
- LibreOffice — parametry wiersza poleceń:
  <https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html>

Wykorzystane biblioteki i narzędzia: Python 3, Tkinter, CustomTkinter, Pillow,
python-docx, odfpy, LibreOffice, pytest.

Ilustracje sakury i kota zostały dostarczone przez autorkę projektu. Interfejs korzysta
wyłącznie z lekkich plików `images/*_small.png` (bez dużych oryginałów w pakiecie).

**Ujawnienie AI:** podczas tworzenia projektu korzystano z asystentów AI
(m.in. Cursor oraz wcześniej opencode / `deepseek-flash`) do wsparcia przy
szkielecie kodu, refaktorze GUI, testach i dokumentacji. Kod został uruchomiony
i zweryfikowany testami (`pytest`); autorka rozumie działanie rejestru konwerterów,
walidacji, obsługi błędów, LibreOffice oraz wątku roboczego w GUI.
