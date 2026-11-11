from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from ..errors import ConversionFailedError
from ..registry import converter
from ..textio import decode_text, write_text


def _detect_dialect(text: str) -> csv.Dialect:
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


@converter(".csv", ".json")
def csv_to_json(source: Path, target: Path) -> Path:
    text = decode_text(source)
    if not text.strip():
        raise ConversionFailedError(
            "Plik CSV jest pusty.",
            "Dodaj wiersz nagłówka i co najmniej jeden wiersz danych.",
        )

    reader = csv.DictReader(io.StringIO(text, newline=""), dialect=_detect_dialect(text))
    if not reader.fieldnames:
        raise ConversionFailedError(
            "Plik CSV nie zawiera wiersza nagłówka.",
            "Pierwszy wiersz musi zawierać nazwy kolumn.",
        )

    headers = [name if name is not None else "" for name in reader.fieldnames]
    if any(not name.strip() for name in headers):
        raise ConversionFailedError(
            "Wiersz nagłówka zawiera pustą nazwę kolumny.",
            "Uzupełnij nazwy wszystkich kolumn.",
        )
    if len(set(headers)) != len(headers):
        raise ConversionFailedError(
            "Wiersz nagłówka zawiera zduplikowane nazwy kolumn.",
            "Nazwy kolumn muszą być unikalne.",
        )

    rows = []
    for line_number, row in enumerate(reader, start=2):
        if row.get(None):
            raise ConversionFailedError(
                f"Wiersz {line_number} zawiera więcej wartości niż nagłówek.",
                "Sprawdź, czy w danych nie ma zbędnych separatorów.",
            )
        rows.append({header: row.get(header) or "" for header in headers})

    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    return write_text(target, f"{payload}\n")


@converter(".json", ".csv")
def json_to_csv(source: Path, target: Path) -> Path:
    text = decode_text(source)
    if not text.strip():
        raise ConversionFailedError(
            "Plik JSON jest pusty.",
            "Dodaj tablicę obiektów zgodną z opisem w README.",
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConversionFailedError(
            f"Nieprawidłowy JSON: {exc.msg} (wiersz {exc.lineno}, kolumna {exc.colno}).",
            "Popraw składnię JSON i spróbuj ponownie.",
        ) from exc

    if not isinstance(data, list):
        raise ConversionFailedError(
            "Nieobsługiwana struktura JSON: oczekiwana jest tablica obiektów.",
            "Przykład: [{\"kolumna\": \"wartość\"}].",
        )
    if any(not isinstance(item, dict) for item in data):
        raise ConversionFailedError(
            "Tablica JSON zawiera element, który nie jest obiektem.",
            "Każdy element tablicy musi być obiektem z parami klucz-wartość.",
        )

    headers: list[str] = []
    for item in data:
        for key in item:
            if key not in headers:
                headers.append(key)

    if not data:
        return write_text(target, "")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for item in data:
        writer.writerow([_cell(item.get(header)) for header in headers])

    return write_text(target, buffer.getvalue())
