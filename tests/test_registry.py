from __future__ import annotations

from pathlib import Path

import pytest

from converter.errors import OutputExistsError, UnsupportedConversionError, ValidationError
from converter.registry import (
    ConversionRequest,
    available_targets,
    execute,
    normalize_format,
    unique_path,
)


def test_available_targets_for_each_source() -> None:
    assert available_targets(Path("dane.csv")) == [".json"]
    assert available_targets(Path("dane.json")) == [".csv"]
    assert available_targets(Path("dane.txt")) == [".docx", ".odt"]
    assert available_targets(Path("dane.docx")) == [".odt", ".pdf", ".txt"]
    assert available_targets(Path("dane.odt")) == [".docx", ".pdf", ".txt"]
    assert available_targets(Path("dane.zip")) == []


def test_normalize_format_accepts_dot_and_case() -> None:
    assert normalize_format("JSON") == ".json"
    assert normalize_format(".PdF ") == ".pdf"
    assert normalize_format("") == ""


def test_validate_rejects_missing_source(tmp_path: Path) -> None:
    request = ConversionRequest(
        source=tmp_path / "brak.csv",
        target_format=".json",
        output_dir=tmp_path,
    )
    with pytest.raises(ValidationError, match="nie istnieje"):
        request.validate()


def test_validate_rejects_unsupported_pair(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    request = ConversionRequest(
        source=source,
        target_format=".pdf",
        output_dir=tmp_path,
    )
    with pytest.raises(UnsupportedConversionError):
        request.validate()


def test_validate_rejects_missing_output_dir(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    request = ConversionRequest(
        source=source,
        target_format=".json",
        output_dir=tmp_path / "nie_ma",
    )
    with pytest.raises(ValidationError, match="Katalog docelowy nie istnieje"):
        request.validate()


def test_existing_target_requires_policy(tmp_path: Path) -> None:
    source = tmp_path / "dane.txt"
    source.write_text("Treść\n", encoding="utf-8")
    (tmp_path / "dane.docx").write_bytes(b"existing")

    request = ConversionRequest(
        source=source,
        target_format=".docx",
        output_dir=tmp_path,
    )
    with pytest.raises(OutputExistsError):
        execute(request)


def test_unique_policy_creates_safe_name(tmp_path: Path) -> None:
    source = tmp_path / "dane.txt"
    source.write_text("Pierwszy akapit.\n\nDrugi akapit.\n", encoding="utf-8")
    existing = tmp_path / "dane.docx"
    existing.write_bytes(b"existing")

    request = ConversionRequest(
        source=source,
        target_format=".docx",
        output_dir=tmp_path,
        on_exists="unique",
    )
    result = execute(request)

    assert result == tmp_path / "dane (1).docx"
    assert result.exists()
    assert existing.read_bytes() == b"existing"


def test_custom_output_name_is_used(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")

    request = ConversionRequest(
        source=source,
        target_format=".json",
        output_dir=tmp_path,
        output_name="mój raport",
    )
    result = execute(request)

    assert result == tmp_path / "mój raport.json"
    assert result.exists()


def test_custom_output_name_rejects_path_separators(tmp_path: Path) -> None:
    source = tmp_path / "dane.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")

    request = ConversionRequest(
        source=source,
        target_format=".json",
        output_dir=tmp_path,
        output_name="../raport",
    )

    with pytest.raises(ValidationError, match="niedozwolone znaki"):
        request.validate()


def test_unique_path_increments_counter(tmp_path: Path) -> None:
    target = tmp_path / "plik.pdf"
    target.write_text("1", encoding="utf-8")
    (tmp_path / "plik (1).pdf").write_text("2", encoding="utf-8")

    assert unique_path(target) == tmp_path / "plik (2).pdf"
