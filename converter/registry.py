from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import (
    ConversionFailedError,
    ConverterError,
    OutputExistsError,
    UnsupportedConversionError,
    ValidationError,
)

Converter = Callable[[Path, Path], Path]

REGISTRY: dict[tuple[str, str], Converter] = {}

ON_EXISTS_POLICIES = ("error", "overwrite", "unique")

INVALID_NAME_CHARS = set('\\/:*?"<>|')

logger = logging.getLogger("converter")


def normalize_format(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        return ""
    if not cleaned.startswith("."):
        cleaned = f".{cleaned}"
    return cleaned


def converter(source_format: str, target_format: str):
    source = normalize_format(source_format)
    target = normalize_format(target_format)

    def register(func: Converter) -> Converter:
        key = (source, target)
        if key in REGISTRY:
            raise ValueError(f"Konwerter już zarejestrowany: {key}")
        REGISTRY[key] = func
        logger.debug("Zarejestrowano konwersję %s -> %s", source, target)
        return func

    return register


def normalize_output_name(name: str, target_format: str) -> str:
    suffix = normalize_format(target_format)
    candidate = (name or "").strip()
    if not candidate:
        return ""
    if candidate.lower().endswith(suffix):
        return candidate
    return f"{candidate}{suffix}"


def validate_output_name(name: str, target_format: str) -> None:
    if not name or not name.strip():
        return

    candidate = name.strip()
    if any(character in INVALID_NAME_CHARS for character in candidate):
        raise ValidationError(
            "Nazwa pliku zawiera niedozwolone znaki.",
            'Usuń znaki: \\ / : * ? " < > | i spróbuj ponownie.',
        )
    if any(ord(character) < 32 for character in candidate):
        raise ValidationError(
            "Nazwa pliku zawiera znaki sterujące.",
            "Użyj zwykłych liter, cyfr, spacji, kropek, myślników lub podkreśleń.",
        )

    final_name = normalize_output_name(candidate, target_format)
    suffix = normalize_format(target_format)
    stem = final_name[: -len(suffix)] if final_name.lower().endswith(suffix) else final_name
    if not stem.strip(" ."):
        raise ValidationError(
            "Nazwa pliku nie może być pusta.",
            "Wpisz nazwę bez rozszerzenia, np. raport.",
        )
    if len(final_name) > 200:
        raise ValidationError(
            "Nazwa pliku jest zbyt długa.",
            "Skróć nazwę do maksymalnie 200 znaków.",
        )


@dataclass(frozen=True)
class ConversionRequest:
    source: Path
    target_format: str
    output_dir: Path
    output_name: str | None = None
    on_exists: str = "error"

    def key(self) -> tuple[str, str]:
        return (self.source.suffix.lower(), normalize_format(self.target_format))

    def target_name(self) -> str:
        custom_name = normalize_output_name(self.output_name or "", self.target_format)
        if custom_name:
            return custom_name
        return f"{self.source.stem}{normalize_format(self.target_format)}"

    def validate(self) -> None:
        source = Path(self.source)
        output_dir = Path(self.output_dir)

        if not str(self.source).strip():
            raise ValidationError("Nie wybrano pliku wejściowego.")
        if not source.exists():
            raise ValidationError(
                f"Plik wejściowy nie istnieje: {source}",
                "Sprawdź ścieżkę i spróbuj ponownie.",
            )
        if not source.is_file():
            raise ValidationError(
                f"Ścieżka nie wskazuje pliku: {source}",
                "Wybierz pojedynczy plik, nie katalog.",
            )
        if not source.suffix:
            raise ValidationError(
                f"Plik nie ma rozszerzenia: {source.name}",
                "Zmień nazwę pliku tak, aby zawierała rozszerzenie.",
            )
        if self.on_exists not in ON_EXISTS_POLICIES:
            raise ValidationError(
                f"Nieznana polityka nadpisywania: {self.on_exists}",
                f"Dozwolone wartości: {', '.join(ON_EXISTS_POLICIES)}.",
            )

        key = self.key()
        if key not in REGISTRY:
            targets = available_targets(source)
            if targets:
                hint = f"Dla plików {key[0]} dostępne są: {', '.join(targets)}."
            else:
                hint = "Ten format wejściowy nie jest obsługiwany."
            raise UnsupportedConversionError(
                f"Nieobsługiwana konwersja: {key[0]} -> {key[1]}", hint
            )

        validate_output_name(self.output_name or "", self.target_format)

        if not str(self.output_dir).strip():
            raise ValidationError("Nie wybrano katalogu docelowego.")
        if not output_dir.exists():
            raise ValidationError(
                f"Katalog docelowy nie istnieje: {output_dir}",
                "Wskaż istniejący katalog lub utwórz go wcześniej.",
            )
        if not output_dir.is_dir():
            raise ValidationError(f"Ścieżka nie jest katalogiem: {output_dir}")
        if not os.access(output_dir, os.W_OK | os.X_OK):
            raise ValidationError(
                f"Brak prawa zapisu w katalogu: {output_dir}",
                "Wybierz inny katalog lub zmień uprawnienia.",
            )
        if not os.access(source, os.R_OK):
            raise ValidationError(
                f"Brak prawa odczytu pliku: {source}",
                "Zmień uprawnienia pliku lub skopiuj go w dostępne miejsce.",
            )


def resolve_output_path(request: ConversionRequest) -> Path:
    output_dir = Path(request.output_dir)
    target = output_dir / request.target_name()

    if not target.exists() or request.on_exists == "overwrite":
        return target
    if request.on_exists == "unique":
        return unique_path(target)
    raise OutputExistsError(target)


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    counter = 1
    while True:
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def execute(request: ConversionRequest) -> Path:
    try:
        request.validate()
        key = request.key()
        target = resolve_output_path(request)
    except ConverterError as exc:
        logger.warning(
            "Odrzucono konwersję %s -> %s: %s",
            request.source,
            request.target_format,
            exc,
        )
        raise
    started = time.monotonic()

    logger.info(
        "Start konwersji: %s -> %s (format %s)",
        request.source,
        target,
        request.target_format,
    )
    try:
        result = Path(REGISTRY[key](Path(request.source), target))
    except ConverterError as exc:
        logger.error("Błąd konwersji %s -> %s: %s", request.source, target, exc)
        raise
    except Exception as exc:
        logger.exception("Nieoczekiwany błąd konwersji %s -> %s", request.source, target)
        raise ConversionFailedError(
            f"Nieoczekiwany błąd konwersji: {exc}",
            "Sprawdź dziennik zdarzeń i poprawność pliku wejściowego.",
        ) from exc

    if not result.exists() or not result.is_file():
        logger.error("Konwerter nie utworzył pliku: %s", result)
        raise ConversionFailedError(
            "Konwerter nie utworzył oczekiwanego pliku.",
            "Sprawdź dziennik zdarzeń oraz dostępność wymaganych narzędzi.",
        )

    logger.info(
        "Zakończono konwersję: %s -> %s w %.2f s",
        request.source,
        result,
        time.monotonic() - started,
    )
    return result


def available_targets(source: Path | str) -> list[str]:
    suffix = Path(source).suffix.lower()
    return sorted({target for (src, target) in REGISTRY if src == suffix})


def supported_sources() -> list[str]:
    return sorted({source for (source, _) in REGISTRY})


def conversion_matrix() -> list[tuple[str, str]]:
    return sorted(REGISTRY)


def supported_pairs_text() -> str:
    lines = []
    for source, target in conversion_matrix():
        lines.append(f"{source} -> {target}")
    return "\n".join(lines)
