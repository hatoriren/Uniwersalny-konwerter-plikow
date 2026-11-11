from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from .errors import ConversionFailedError


def open_path(path: Path) -> None:
    target = Path(path).expanduser()
    if not target.exists():
        raise ConversionFailedError(
            f"Ścieżka nie istnieje: {target}",
            "Plik mógł zostać przeniesiony lub usunięty.",
        )

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(target))
            return
        command = ["open", str(target)] if system == "Darwin" else ["xdg-open", str(target)]
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    except OSError as exc:
        raise ConversionFailedError(
            f"Nie można otworzyć ścieżki: {target}",
            f"Otwórz ją ręcznie w systemowym menedżerze plików ({exc}).",
        ) from exc


def reveal_in_file_manager(path: Path) -> None:
    target = Path(path).expanduser()
    if not target.exists():
        raise ConversionFailedError(
            f"Ścieżka nie istnieje: {target}",
            "Plik mógł zostać przeniesiony lub usunięty.",
        )

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(
                ["open", "-R", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        elif system == "Windows":
            subprocess.Popen(
                ["explorer", "/select,", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        else:
            open_path(target.parent)
    except OSError as exc:
        raise ConversionFailedError(
            f"Nie można pokazać pliku w menedżerze: {target}",
            f"Otwórz katalog ręcznie ({exc}).",
        ) from exc
