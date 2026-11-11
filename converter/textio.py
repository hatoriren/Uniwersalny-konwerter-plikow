from __future__ import annotations

import re
from pathlib import Path

from .errors import ConversionFailedError

SUPPORTED_ENCODINGS = ("utf-8-sig", "cp1250", "iso-8859-2")


def decode_text(path: Path) -> str:
    data = Path(path).read_bytes()
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ConversionFailedError(
        f"Nie można odczytać pliku {Path(path).name} w obsługiwanym kodowaniu.",
        "Zapisz plik jako UTF-8, Windows-1250 lub ISO-8859-2.",
    )


def write_text(path: Path, text: str) -> Path:
    target = Path(path)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return target


def split_paragraphs(text: str) -> list[list[str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", normalized)
    paragraphs: list[list[str]] = []
    for block in blocks:
        lines = block.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            paragraphs.append(lines)
    return paragraphs


def join_paragraphs(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraphs).strip("\n") + "\n" if paragraphs else ""
