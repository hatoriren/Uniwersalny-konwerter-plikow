from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from converter.converters.data import csv_to_json, json_to_csv
from converter.errors import ConversionFailedError


def test_csv_to_json_preserves_headers_order_and_polish(tmp_path: Path) -> None:
    source = tmp_path / "osoby.csv"
    source.write_text(
        "imię,nazwisko,miasto,uwagi\n"
        "Zażółć,gęślą,Jaźń,\n"
        "Anna,Kowalska,Kraków,studentka\n",
        encoding="utf-8",
    )
    target = tmp_path / "osoby.json"

    csv_to_json(source, target)

    data = json.loads(target.read_text(encoding="utf-8"))
    assert list(data[0].keys()) == ["imię", "nazwisko", "miasto", "uwagi"]
    assert data[0] == {
        "imię": "Zażółć",
        "nazwisko": "gęślą",
        "miasto": "Jaźń",
        "uwagi": "",
    }
    assert data[1]["miasto"] == "Kraków"


def test_csv_to_json_detects_semicolon(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    target = tmp_path / "dane.json"

    csv_to_json(source, target)

    assert json.loads(target.read_text(encoding="utf-8")) == [
        {"a": "1", "b": "2", "c": "3"}
    ]


def test_csv_to_json_rejects_extra_columns(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a,b\n1,2,3\n", encoding="utf-8")

    with pytest.raises(ConversionFailedError, match="więcej wartości"):
        csv_to_json(source, tmp_path / "dane.json")


def test_csv_to_json_rejects_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "puste.csv"
    source.write_text("", encoding="utf-8")

    with pytest.raises(ConversionFailedError, match="pusty"):
        csv_to_json(source, tmp_path / "puste.json")


def test_json_to_csv_preserves_key_order_and_missing_values(tmp_path: Path) -> None:
    source = tmp_path / "dane.json"
    source.write_text(
        json.dumps(
            [
                {"imię": "Łucja", "wiek": 21, "aktywny": True},
                {"wiek": 23, "imię": "Jan", "miasto": "Gdańsk"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    target = tmp_path / "dane.csv"

    json_to_csv(source, target)

    with target.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == ["imię", "wiek", "aktywny", "miasto"]
    assert rows[1] == ["Łucja", "21", "true", ""]
    assert rows[2] == ["Jan", "23", "", "Gdańsk"]


def test_json_to_csv_rejects_malformed_json(tmp_path: Path) -> None:
    source = tmp_path / "zly.json"
    source.write_text('{"a": 1,,}', encoding="utf-8")

    with pytest.raises(ConversionFailedError, match="Nieprawidłowy JSON"):
        json_to_csv(source, tmp_path / "zly.csv")


def test_json_to_csv_rejects_non_list_structure(tmp_path: Path) -> None:
    source = tmp_path / "obiekt.json"
    source.write_text('{"a": 1}', encoding="utf-8")

    with pytest.raises(ConversionFailedError, match="tablica obiektów"):
        json_to_csv(source, tmp_path / "obiekt.csv")


def test_json_to_csv_handles_empty_list(tmp_path: Path) -> None:
    source = tmp_path / "puste.json"
    source.write_text("[]", encoding="utf-8")
    target = tmp_path / "puste.csv"

    json_to_csv(source, target)

    assert target.read_text(encoding="utf-8") == ""
