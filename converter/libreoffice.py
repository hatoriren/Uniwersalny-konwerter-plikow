from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import ConversionFailedError, DependencyError

logger = logging.getLogger("converter")

FILTERS = {
    ".pdf": "pdf:writer_pdf_Export",
    ".odt": "odt:writer8",
    ".docx": "docx:MS Word 2007 XML",
}


def _install_hint() -> str:
    system = platform.system()
    if system == "Darwin":
        command = "brew install --cask libreoffice"
    elif system == "Windows":
        command = "zainstaluj pakiet z https://www.libreoffice.org/download/"
    else:
        command = "sudo apt install libreoffice (Debian/Ubuntu) lub sudo dnf install libreoffice (Fedora)"
    return (
        "Zainstaluj LibreOffice i upewnij się, że polecenie soffice jest dostępne. "
        f"Na tym systemie: {command}. Możesz też ustawić zmienną CONVERTER_SOFFICE."
    )


def find_soffice() -> Path | None:
    candidates: list[Path] = []

    for variable in ("CONVERTER_SOFFICE", "SOFFICE_PATH"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value))

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    if platform.system() == "Darwin":
        candidates.extend(
            [
                Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                Path.home()
                / "Applications/LibreOffice.app/Contents/MacOS/soffice",
            ]
        )
    elif platform.system() == "Windows":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.environ.get(variable)
            if base:
                candidates.append(Path(base) / "LibreOffice/program/soffice.exe")
    else:
        candidates.extend(
            [
                Path("/usr/bin/soffice"),
                Path("/usr/lib/libreoffice/program/soffice"),
            ]
        )

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def soffice_available() -> bool:
    return find_soffice() is not None


def require_soffice() -> Path:
    path = find_soffice()
    if path is None:
        raise DependencyError(
            "Nie znaleziono LibreOffice, który jest wymagany do tej konwersji.",
            _install_hint(),
        )
    return path


def convert_with_libreoffice(
    source: Path, target: Path, timeout: int | None = None
) -> Path:
    soffice = require_soffice()
    source = Path(source)
    target = Path(target)
    suffix = target.suffix.lower()
    filter_name = FILTERS.get(suffix)
    if filter_name is None:
        raise ConversionFailedError(
            f"Brak filtra LibreOffice dla formatu {suffix}.",
            "Zgłoś błąd lub wybierz inny format docelowy.",
        )

    if timeout is None:
        timeout = int(os.environ.get("CONVERTER_LO_TIMEOUT", "120"))

    with tempfile.TemporaryDirectory(prefix="konwerter-lo-") as temporary:
        profile = Path(temporary) / "profile"
        output_dir = Path(temporary) / "out"
        profile.mkdir()
        output_dir.mkdir()

        command = [
            str(soffice),
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--norestore",
            "--convert-to",
            filter_name,
            "--outdir",
            str(output_dir),
            str(source),
        ]

        logger.debug("Wywołanie LibreOffice: %r", command)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversionFailedError(
                f"Konwersja LibreOffice przekroczyła limit {timeout} s.",
                "Spróbuj ponownie lub zwiększ zmienną CONVERTER_LO_TIMEOUT.",
            ) from exc
        except OSError as exc:
            raise ConversionFailedError(
                f"Nie można uruchomić LibreOffice: {exc}",
                _install_hint(),
            ) from exc

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        if result.returncode != 0:
            detail = error or output or "brak komunikatu"
            raise ConversionFailedError(
                f"LibreOffice zakończył konwersję z kodem {result.returncode}: {detail}",
                "Sprawdź, czy plik wejściowy nie jest uszkodzony i czy LibreOffice działa.",
            )

        expected = output_dir / f"{source.stem}{suffix}"
        if not expected.is_file():
            candidates = sorted(output_dir.glob(f"*{suffix}"))
            if len(candidates) == 1:
                expected = candidates[0]
            else:
                detail = error or output or "brak pliku wynikowego"
                raise ConversionFailedError(
                    f"LibreOffice nie utworzył pliku {target.name}: {detail}",
                    "Sprawdź dziennik zdarzeń i poprawność pliku wejściowego.",
                )

        if target.exists():
            target.unlink()
        shutil.move(str(expected), str(target))

    logger.debug("LibreOffice zapisał plik: %s", target)
    return target
