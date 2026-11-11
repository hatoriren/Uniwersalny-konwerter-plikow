from __future__ import annotations

import json
from pathlib import Path

from converter.cli import main


def test_cli_converts_csv_to_json(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("imię,miasto\nŁucja,Wrocław\n", encoding="utf-8")
    output_dir = tmp_path / "wyniki"
    output_dir.mkdir()

    exit_code = main(
        ["convert", str(source), "json", "--output", str(output_dir)]
    )

    assert exit_code == 0
    result = output_dir / "dane.json"
    assert json.loads(result.read_text(encoding="utf-8")) == [
        {"imię": "Łucja", "miasto": "Wrocław"}
    ]


def test_cli_uses_custom_output_name(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a\n1\n", encoding="utf-8")
    output_dir = tmp_path / "wyniki"
    output_dir.mkdir()

    exit_code = main(
        [
            "convert",
            str(source),
            "json",
            "--output",
            str(output_dir),
            "--name",
            "wynik końcowy",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "wynik końcowy.json").exists()


def test_cli_reports_error_for_missing_file(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "convert",
            str(tmp_path / "brak.csv"),
            "json",
            "--output",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Błąd:" in captured.err


def test_cli_uses_unique_name_when_requested(tmp_path: Path) -> None:
    source = tmp_path / "dane.txt"
    source.write_text("Treść akapitu.\n", encoding="utf-8")
    existing = tmp_path / "dane.docx"
    existing.write_bytes(b"stary plik")

    exit_code = main(
        ["convert", str(source), "docx", "--output", str(tmp_path), "--on-exists", "unique"]
    )

    assert exit_code == 0
    assert (tmp_path / "dane (1).docx").exists()
    assert existing.read_bytes() == b"stary plik"
