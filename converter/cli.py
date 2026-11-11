from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path

from .errors import ConverterError
from .libreoffice import find_soffice
from .logging_setup import setup_logging
from .registry import (
    ConversionRequest,
    ON_EXISTS_POLICIES,
    conversion_matrix,
    execute,
    normalize_format,
    supported_sources,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="konwerter",
        description="Uniwersalny konwerter plików (CSV, JSON, TXT, DOCX, ODT, PDF).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="szczegółowe logowanie"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("gui", help="uruchom interfejs graficzny")

    subparsers.add_parser("list", help="pokaż macierz obsługiwanych konwersji")

    subparsers.add_parser("doctor", help="sprawdź zależności i środowisko")

    convert = subparsers.add_parser("convert", help="wykonaj konwersję")
    convert.add_argument("source", help="ścieżka pliku wejściowego")
    convert.add_argument("target", help="format docelowy, np. json lub .json")
    convert.add_argument(
        "-o",
        "--output",
        help="katalog zapisu (domyślnie katalog pliku wejściowego)",
    )
    convert.add_argument(
        "-n",
        "--name",
        help="nazwa pliku wynikowego, z rozszerzeniem lub bez",
    )
    convert.add_argument(
        "--on-exists",
        choices=ON_EXISTS_POLICIES,
        default="error",
        help="zachowanie, gdy plik docelowy istnieje (domyślnie error)",
    )

    return parser


def command_list() -> int:
    print("Obsługiwane formaty wejściowe:", ", ".join(supported_sources()))
    print("\nMacierz konwersji:")
    for source, target in conversion_matrix():
        print(f"  {source:7} -> {target}")
    print("\nPDF oraz DOCX/ODT wymagają LibreOffice.")
    return 0


def command_doctor() -> int:
    print(f"Python: {platform.python_version()} ({platform.system()} {platform.machine()})")
    modules = (
        ("tkinter", "Tkinter"),
        ("customtkinter", "CustomTkinter"),
        ("docx", "python-docx"),
        ("odf", "odfpy"),
    )
    for module, label in modules:
        try:
            importlib.import_module(module)
            print(f"{label}: OK")
        except Exception as exc:
            print(f"{label}: BRAK ({exc})")

    soffice = find_soffice()
    print(f"LibreOffice: {soffice if soffice else 'nie wykryty'}")
    print(f"Dziennik: {setup_logging()}")
    return 0


def command_convert(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser()
    output_dir = (
        Path(args.output).expanduser() if args.output else source.parent
    )
    request = ConversionRequest(
        source=source,
        target_format=normalize_format(args.target),
        output_dir=output_dir,
        output_name=args.name,
        on_exists=args.on_exists,
    )

    try:
        result = execute(request)
    except ConverterError as exc:
        print(f"Błąd: {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"Wskazówka: {exc.hint}", file=sys.stderr)
        return 1

    print(f"Zapisano: {result}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(verbose=args.verbose)

    if args.command in (None, "gui"):
        from .gui import run_gui

        run_gui()
        return 0
    if args.command == "list":
        return command_list()
    if args.command == "doctor":
        return command_doctor()
    if args.command == "convert":
        return command_convert(args)

    parser.print_help()
    return 2
