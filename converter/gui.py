from __future__ import annotations

import logging
import platform
import queue
import re
import sys
import threading
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

try:
    from PIL import Image
except ImportError:
    Image = None

from .errors import ConversionFailedError, ConverterError
from .libreoffice import soffice_available
from .logging_setup import setup_logging
from .registry import (
    ConversionRequest,
    available_targets,
    execute,
    normalize_output_name,
    validate_output_name,
)
from .system import open_path, reveal_in_file_manager

logger = logging.getLogger("converter")

BG = ("#f2e8d5", "#101822")
CARD = ("#fbf5e9", "#1b2735")
SOFT = ("#f6ecd9", "#233142")
BORDER = ("#d8c6a6", "#385164")
TEXT = ("#28211c", "#f4ead8")
MUTED = ("#7c6a55", "#aa9a83")
ACCENT = ("#b5483d", "#d76a5c")
ACCENT_HOVER = ("#94382f", "#b5483d")
BUTTON = ("#b5483d", "#cf5f51")
BUTTON_HOVER = ("#96372e", "#b5483d")
BUTTON_TEXT = ("#fff4e4", "#fff4e4")
BUTTON_TEXT_DISABLED = ("#d6a29a", "#a56f68")
SECONDARY = ("#e9d9bd", "#2b3c4c")
SECONDARY_HOVER = ("#dfc9a6", "#395064")
SUCCESS = ("#3f726b", "#78b0a3")
ERROR = ("#9f3b31", "#e08a7a")
CHIP = ("#eddfc5", "#293846")
GOLD = ("#b8893f", "#d9b36a")
INDIGO = ("#2f4f6b", "#3d5f7a")
INDIGO_HOVER = ("#263f56", "#4a7089")
HELP_CARD = ("#2a4256", "#22313f")
HELP_TEXT = ("#f5ead6", "#f0e3cc")
HELP_MUTED = ("#c7b79d", "#b8a98f")

GRADIENT_LIGHT = ("#f2e2c4", "#e7c3b4", "#cf8f94", "#557786", "#253a4d")
GRADIENT_DARK = ("#d9b36a", "#cf8f94", "#6f8f93", "#2f4f6b", "#101822")

IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"

SUPPORTED_FILETYPES = [
    ("Wspierane pliki", "*.csv *.json *.txt *.docx *.odt"),
    ("Dane", "*.csv *.json"),
    ("Tekst i dokumenty", "*.txt *.docx *.odt"),
    ("Wszystkie pliki", "*.*"),
]

THEME_MODES = {
    "Systemowy": "System",
    "Jasny": "Light",
    "Ciemny": "Dark",
}


def _font_family() -> tuple[str, str]:
    system = platform.system()
    if system == "Darwin":
        return "Hiragino Sans", "Hiragino Mincho ProN"
    if system == "Windows":
        return "Segoe UI", "Yu Mincho"
    return "Noto Sans", "Noto Serif"


def _mix_hex(start: str, end: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
    mixed = [round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb)]
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def _gradient_color(position: float, stops: tuple[str, ...]) -> str:
    segments = len(stops) - 1
    scaled = max(0.0, min(position, 1.0)) * segments
    index = min(int(scaled), segments - 1)
    return _mix_hex(stops[index], stops[index + 1], scaled - index)


class GradientStrip(tk.Canvas):
    def __init__(self, master, height: int = 10) -> None:
        super().__init__(
            master,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            background=GRADIENT_LIGHT[1],
        )
        self._height = height
        self._dark = False
        self.bind("<Configure>", lambda event: self._draw())

    def set_mode(self, dark: bool) -> None:
        if dark != self._dark:
            self._dark = dark
            self._draw()

    def _draw(self) -> None:
        width = self.winfo_width()
        if width <= 1:
            return
        stops = GRADIENT_DARK if self._dark else GRADIENT_LIGHT
        self.delete("all")
        step = max(width // 260, 1)
        for x in range(0, width, step):
            color = _gradient_color(x / max(width - 1, 1), stops)
            self.create_rectangle(
                x, 0, x + step, self._height, fill=color, outline=color
            )


def _human_size(path: Path) -> str:
    size = path.stat().st_size
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{size} B"


def _shorten_path(path: Path, limit: int = 62) -> str:
    text = str(path)
    home = str(Path.home())
    if text.startswith(home):
        text = f"~{text[len(home):]}"
    if len(text) <= limit:
        return text
    return f"…{text[-(limit - 1):]}"


def _safe_stem(stem: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", stem).strip(" .")
    return cleaned or "wynik"


def _shorten_name(name: str, limit: int = 34) -> str:
    if len(name) <= limit:
        return name
    side = max((limit - 1) // 2, 4)
    return f"{name[:side]}…{name[-side:]}"


def _balance_button_text(button: ctk.CTkButton, lift: int = 3) -> ctk.CTkButton:
    """Shift button caption up a little — Hiragino metrics leave extra top gap."""
    label = getattr(button, "_text_label", None)
    if label is not None:
        try:
            label.grid_configure(pady=(0, lift))
        except tk.TclError:
            pass
    return button


class ConflictDialog(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, target: Path) -> None:
        super().__init__(master, fg_color=BG)
        self.result: str | None = None
        self.title("Plik już istnieje")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        family, display = _font_family()
        card = ctk.CTkFrame(
            self,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        card.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Taki plik już istnieje",
            font=ctk.CTkFont(family=display, size=21, weight="bold"),
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 4))

        ctk.CTkLabel(
            card,
            text=str(target),
            font=ctk.CTkFont(family=family, size=12),
            text_color=MUTED,
            wraplength=470,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

        ctk.CTkLabel(
            card,
            text="Możesz nadpisać plik albo zapisać wynik pod nową, unikalną nazwą.",
            font=ctk.CTkFont(family=family, size=13),
            text_color=TEXT,
            wraplength=470,
            justify="left",
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 18))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 20))
        buttons.grid_columnconfigure(0, weight=1)

        _balance_button_text(
            ctk.CTkButton(
                buttons,
                text="Anuluj",
                width=90,
                height=36,
                corner_radius=10,
                fg_color="transparent",
                hover_color=SOFT,
                text_color=MUTED,
                font=ctk.CTkFont(family=family, size=13),
                command=self._cancel,
            )
        ).grid(row=0, column=0, sticky="w")

        _balance_button_text(
            ctk.CTkButton(
                buttons,
                text="Zapisz jako nową",
                width=150,
                height=36,
                corner_radius=10,
                fg_color=SECONDARY,
                hover_color=SECONDARY_HOVER,
                text_color=TEXT,
                font=ctk.CTkFont(family=family, size=13),
                command=lambda: self._choose("unique"),
            )
        ).grid(row=0, column=1, padx=(0, 8))

        _balance_button_text(
            ctk.CTkButton(
                buttons,
                text="Nadpisz",
                width=110,
                height=36,
                corner_radius=10,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                text_color="#ffffff",
                font=ctk.CTkFont(family=family, size=13, weight="bold"),
                command=lambda: self._choose("overwrite"),
            )
        ).grid(row=0, column=2)

        self.update_idletasks()
        width = 540
        height = self.winfo_reqheight()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{max(x, 40)}+{max(y, 40)}")
        self.bind("<Escape>", lambda event: self._cancel())
        self.after(40, self.grab_set)
        self.after(80, self.focus_force)

    def _choose(self, value: str) -> None:
        self.result = value
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ConverterApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("Light")
        super().__init__(fg_color=BG)
        self.title("Uniwersalny konwerter plików")
        self.minsize(960, 760)

        family, display = _font_family()
        self.font_title = ctk.CTkFont(family=display, size=30, weight="bold")
        self.font_subtitle = ctk.CTkFont(family=family, size=13)
        self.font_h2 = ctk.CTkFont(family=family, size=17, weight="bold")
        self.font_h3 = ctk.CTkFont(family=family, size=14, weight="bold")
        self.font_body = ctk.CTkFont(family=family, size=13)
        self.font_small = ctk.CTkFont(family=family, size=12)
        self.font_tiny = ctk.CTkFont(family=family, size=11)
        self.font_button = ctk.CTkFont(family=family, size=14, weight="bold")
        self.font_mono = ctk.CTkFont(family="Menlo", size=11)

        self.queue: queue.Queue = queue.Queue()
        self.busy = False
        self._appearance = ctk.get_appearance_mode()
        self.source_path: Path | None = None
        self.last_result: Path | None = None
        self._targets: list[str] = []
        self._format_lookup: dict[str, str] = {}
        self._output_auto = True
        self._setting_output = False
        self._images: dict[tuple[str, tuple[int, int]], ctk.CTkImage] = {}
        self.log_path = setup_logging()

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.theme_var = tk.StringVar(value="Jasny")

        self._build()
        self._center_window()
        self._refresh_output_state()
        self._update_preview()
        self._set_status(
            "No to zaczynamy!",
            "Wybierz plik, ustaw format i nazwę — resztą zajmę się ja.",
        )
        self._set_busy(False)

        self.bind("<Command-o>", lambda event: self._choose_source())
        self.bind("<Control-o>", lambda event: self._choose_source())
        self.bind("<Return>", self._on_return)
        self.after(120, self._poll_queue)

    def _center_window(self) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(1020, screen_width - 80)
        height = min(780, screen_height - 110)
        x = max((screen_width - width) // 2, 20)
        y = max((screen_height - height) // 2 - 10, 20)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.gradient = GradientStrip(self)
        self.gradient.grid(row=0, column=0, sticky="ew")
        self._build_header()
        self._build_content()
        self._build_footer()
        self.gradient.set_mode(self._appearance == "Dark")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=1, column=0, sticky="ew", padx=28, pady=(13, 10))
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkFrame(
            header,
            width=52,
            height=52,
            corner_radius=16,
            fg_color=("#fdf6e8", "#1f2c3a"),
            border_width=2,
            border_color=ACCENT,
        )
        logo.grid(row=0, column=0, rowspan=2, sticky="w")
        logo.grid_propagate(False)
        flower = self._image("sakura_flower_small.png", (42, 42))
        if flower is not None:
            ctk.CTkLabel(logo, image=flower, text="").place(
                relx=0.5, rely=0.5, anchor="center"
            )
        else:
            ctk.CTkLabel(
                logo,
                text="K",
                font=ctk.CTkFont(family=_font_family()[1], size=24),
                text_color=ACCENT,
            ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            header,
            text="Uniwersalny konwerter plików",
            font=self.font_title,
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(14, 0))

        ctk.CTkLabel(
            header,
            text="CSV  ·  JSON  ·  TXT  ·  DOCX  ·  ODT  ·  PDF",
            font=self.font_subtitle,
            text_color=ACCENT,
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(14, 0))

        ctk.CTkOptionMenu(
            header,
            values=list(THEME_MODES),
            variable=self.theme_var,
            command=self._change_theme,
            width=128,
            height=34,
            corner_radius=10,
            fg_color=CARD,
            button_color=CARD,
            button_hover_color=SOFT,
            text_color=TEXT,
            dropdown_fg_color=CARD,
            dropdown_hover_color=SOFT,
            dropdown_text_color=TEXT,
            font=self.font_small,
            dropdown_font=self.font_small,
        ).grid(row=0, column=2, rowspan=2, sticky="e")

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=28)
        content.grid_columnconfigure(0, weight=3, uniform="columns")
        content.grid_columnconfigure(1, weight=2, uniform="columns")
        content.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        self._build_input_card(left)
        self._build_settings_card(left)
        self._build_convert_button(left)
        self._build_status_card(right)
        self._build_help_card(right)

    def _build_input_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        title_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            title_row,
            text="Plik wejściowy",
            font=self.font_h2,
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.file_badge = ctk.CTkLabel(
            title_row,
            text="Nie wybrano",
            font=self.font_tiny,
            text_color=MUTED,
            fg_color=CHIP,
            corner_radius=8,
            padx=10,
            pady=3,
        )
        self.file_badge.grid(row=0, column=1, sticky="e")

        drop = ctk.CTkFrame(
            card,
            fg_color=SOFT,
            corner_radius=14,
            border_width=1,
            border_color=BORDER,
        )
        drop.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 18))
        drop.grid_columnconfigure(0, weight=1)

        labels = ctk.CTkFrame(drop, fg_color="transparent")
        labels.grid(row=0, column=0, sticky="ew", padx=16, pady=14)
        labels.grid_columnconfigure(0, weight=1)

        self.file_name_label = ctk.CTkLabel(
            labels,
            text="Kliknij „Wybierz plik”",
            font=self.font_h3,
            text_color=TEXT,
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.file_name_label.grid(row=0, column=0, sticky="ew")
        self.file_meta_label = ctk.CTkLabel(
            labels,
            text="CSV, JSON, TXT, DOCX lub ODT",
            font=self.font_small,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.file_meta_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))

        buttons = ctk.CTkFrame(drop, fg_color="transparent")
        buttons.grid(row=0, column=1, sticky="e", padx=(0, 14), pady=14)

        self.choose_file_button = _balance_button_text(
            ctk.CTkButton(
                buttons,
                text="Wybierz plik",
                width=116,
                height=36,
                corner_radius=10,
                fg_color=BUTTON,
                hover_color=BUTTON_HOVER,
                text_color=BUTTON_TEXT,
                font=self.font_button,
                command=self._choose_source,
            )
        )
        self.choose_file_button.grid(row=0, column=0)

        self.open_input_button = _balance_button_text(
            ctk.CTkButton(
                buttons,
                text="Otwórz folder",
                width=112,
                height=36,
                corner_radius=10,
                fg_color="transparent",
                hover_color=CHIP,
                border_width=1,
                border_color=BORDER,
                text_color=TEXT,
                font=self.font_small,
                state="disabled",
                command=self._open_input_folder,
            )
        )
        self.open_input_button.grid(row=0, column=1, padx=(8, 0))

    def _build_settings_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Ustawienia konwersji",
            font=self.font_h2,
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 12))

        ctk.CTkLabel(
            card,
            text="FORMAT DOCELOWY",
            font=self.font_tiny,
            text_color=ACCENT,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20)

        self.format_segmented = ctk.CTkSegmentedButton(
            card,
            values=["—"],
            state="disabled",
            height=38,
            corner_radius=10,
            font=self.font_body,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=INDIGO,
            unselected_hover_color=INDIGO_HOVER,
            text_color=("#f7ecd9", "#f7ecd9"),
            text_color_disabled=MUTED,
            command=self._on_format_changed,
        )
        self.format_segmented.grid(row=2, column=0, sticky="ew", padx=20, pady=(6, 14))

        ctk.CTkFrame(card, height=1, fg_color=BORDER).grid(
            row=3, column=0, sticky="ew", padx=20
        )

        ctk.CTkLabel(
            card,
            text="KATALOG ZAPISU",
            font=self.font_tiny,
            text_color=ACCENT,
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=20, pady=(14, 0))

        folder_row = ctk.CTkFrame(card, fg_color="transparent")
        folder_row.grid(row=5, column=0, sticky="ew", padx=20, pady=(6, 14))
        folder_row.grid_columnconfigure(0, weight=1)

        self.output_entry = ctk.CTkEntry(
            folder_row,
            textvariable=self.output_var,
            height=38,
            corner_radius=10,
            fg_color=SOFT,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text="Katalog, w którym zapiszę wynik",
            font=self.font_body,
        )
        self.output_entry.grid(row=0, column=0, sticky="ew")

        self.output_browse_button = _balance_button_text(
            ctk.CTkButton(
                folder_row,
                text="Zmień",
                width=68,
                height=38,
                corner_radius=10,
                fg_color=SECONDARY,
                hover_color=SECONDARY_HOVER,
                text_color=TEXT,
                font=self.font_small,
                command=self._choose_output,
            )
        )
        self.output_browse_button.grid(row=0, column=1, padx=(8, 0))

        self.output_open_button = _balance_button_text(
            ctk.CTkButton(
                folder_row,
                text="Otwórz",
                width=76,
                height=38,
                corner_radius=10,
                fg_color="transparent",
                hover_color=CHIP,
                border_width=1,
                border_color=BORDER,
                text_color=TEXT,
                font=self.font_small,
                state="disabled",
                command=self._open_output_folder,
            )
        )
        self.output_open_button.grid(row=0, column=2, padx=(8, 0))

        ctk.CTkLabel(
            card,
            text="NAZWA PLIKU",
            font=self.font_tiny,
            text_color=ACCENT,
            anchor="w",
        ).grid(row=6, column=0, sticky="ew", padx=20)

        name_row = ctk.CTkFrame(card, fg_color="transparent")
        name_row.grid(row=7, column=0, sticky="ew", padx=20, pady=(6, 4))
        name_row.grid_columnconfigure(0, weight=1)

        self.name_entry = ctk.CTkEntry(
            name_row,
            textvariable=self.name_var,
            height=38,
            corner_radius=10,
            fg_color=SOFT,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text="np. raport końcowy",
            font=self.font_body,
            state="disabled",
        )
        self.name_entry.grid(row=0, column=0, sticky="ew")

        self.suffix_label = ctk.CTkLabel(
            name_row,
            text="—",
            width=72,
            height=38,
            corner_radius=10,
            fg_color=CHIP,
            text_color=TEXT,
            font=ctk.CTkFont(family=_font_family()[0], size=13, weight="bold"),
        )
        self.suffix_label.grid(row=0, column=1, padx=(8, 0))

        self.preview_label = ctk.CTkLabel(
            card,
            text="Rozszerzenie zostanie dodane automatycznie.",
            font=self.font_small,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=380,
        )
        self.preview_label.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 18))

        self.output_var.trace_add("write", lambda *_: self._on_output_changed())
        self.name_var.trace_add("write", lambda *_: self._update_preview())

    def _build_convert_button(self, parent: ctk.CTkFrame) -> None:
        self.convert_button = _balance_button_text(
            ctk.CTkButton(
                parent,
                text="Konwertuj teraz",
                height=50,
                corner_radius=14,
                border_width=1,
                border_color=("#e9b6c8", "#c98ba1"),
                fg_color=BUTTON,
                hover_color=BUTTON_HOVER,
                text_color=BUTTON_TEXT,
                font=ctk.CTkFont(family=_font_family()[0], size=16, weight="bold"),
                text_color_disabled=BUTTON_TEXT_DISABLED,
                state="disabled",
                command=self._start_conversion,
            ),
            lift=4,
        )
        self.convert_button.grid(row=2, column=0, sticky="ew", pady=(16, 0))

    def _build_status_card(self, parent: ctk.CTkFrame) -> None:
        self.status_card = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
        )
        self.status_card.grid(row=0, column=0, sticky="nsew")
        self.status_card.grid_columnconfigure(0, weight=1)
        self.status_card.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self.status_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        header.grid_columnconfigure(1, weight=1)

        self.status_dot = ctk.CTkFrame(
            header,
            width=10,
            height=10,
            corner_radius=5,
            fg_color=MUTED,
        )
        self.status_dot.grid(row=0, column=0, padx=(0, 8))
        self.status_dot.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="Status",
            font=self.font_h2,
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        self.status_title = ctk.CTkLabel(
            self.status_card,
            text="No to zaczynamy!",
            font=self.font_h3,
            text_color=TEXT,
            anchor="w",
            justify="left",
            wraplength=300,
        )
        self.status_title.grid(row=1, column=0, sticky="ew", padx=20)

        self.status_detail = ctk.CTkLabel(
            self.status_card,
            text="",
            font=self.font_body,
            text_color=MUTED,
            anchor="nw",
            justify="left",
            wraplength=300,
        )
        self.status_detail.grid(row=2, column=0, sticky="new", padx=20, pady=(6, 10))

        branch = self._image("sakura_branch_small.png", (250, 89))
        if branch is not None:
            ctk.CTkLabel(self.status_card, image=branch, text="").grid(
                row=3, column=0, sticky="se", padx=16, pady=(0, 8)
            )

        self.result_actions = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.result_actions.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 18))
        self.result_actions.grid_columnconfigure((0, 1), weight=1)

        _balance_button_text(
            ctk.CTkButton(
                self.result_actions,
                text="Otwórz wynik",
                height=38,
                corner_radius=10,
                fg_color=BUTTON,
                hover_color=BUTTON_HOVER,
                text_color=BUTTON_TEXT,
                font=self.font_button,
                command=self._open_result,
            )
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        _balance_button_text(
            ctk.CTkButton(
                self.result_actions,
                text="Pokaż w folderze",
                height=34,
                corner_radius=10,
                fg_color=SECONDARY,
                hover_color=SECONDARY_HOVER,
                text_color=TEXT,
                font=self.font_small,
                command=self._reveal_result,
            )
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4))

        _balance_button_text(
            ctk.CTkButton(
                self.result_actions,
                text="Otwórz folder",
                height=34,
                corner_radius=10,
                fg_color="transparent",
                hover_color=CHIP,
                border_width=1,
                border_color=BORDER,
                text_color=TEXT,
                font=self.font_small,
                command=self._open_result_folder,
            )
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))
        self.result_actions.grid_remove()

        self.progress = ctk.CTkProgressBar(
            self.status_card,
            height=8,
            corner_radius=4,
            mode="indeterminate",
            progress_color=ACCENT,
            fg_color=SOFT,
        )
        self.progress.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 18))
        self.progress.grid_remove()

    def _build_help_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=HELP_CARD,
            corner_radius=18,
            border_width=1,
            border_color=GOLD,
        )
        card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Jak to działa?",
            font=self.font_h2,
            text_color=HELP_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))

        steps = (
            "1   Wybierz plik lub otwórz jego folder.\n"
            "2   Ustaw format, miejsce zapisu i nazwę.\n"
            "3   Kliknij „Konwertuj teraz”.\n"
            "4   Otwórz wynik z panelu statusu."
        )
        ctk.CTkLabel(
            card,
            text=steps,
            font=self.font_small,
            text_color=HELP_MUTED,
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.available_label = ctk.CTkLabel(
            card,
            text="Dostępne formaty pojawią się po wybraniu pliku.",
            font=self.font_small,
            text_color=GOLD,
            anchor="w",
            justify="left",
            wraplength=230,
        )
        self.available_label.grid(
            row=2, column=0, sticky="ew", padx=(20, 76), pady=(0, 18)
        )

        cat = self._image("cat_small.png", (52, 70))
        if cat is not None:
            ctk.CTkLabel(card, image=cat, text="").place(
                relx=1.0, rely=1.0, x=-16, y=-14, anchor="se"
            )

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=28, pady=(10, 16))
        footer.grid_columnconfigure(0, weight=1)

        if soffice_available():
            libreoffice_text = "LibreOffice wykryty — PDF i konwersje biurowe dostępne"
        else:
            libreoffice_text = "LibreOffice nie wykryty — PDF i konwersje biurowe wyłączone"

        ctk.CTkLabel(
            footer,
            text=libreoffice_text,
            font=self.font_tiny,
            text_color=MUTED,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        env_text = f"Python {platform.python_version()}  ·  Tk {tk.TkVersion}"
        ctk.CTkLabel(
            footer,
            text=env_text,
            font=self.font_tiny,
            text_color=MUTED,
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(12, 12))

        _balance_button_text(
            ctk.CTkButton(
                footer,
                text="Dziennik",
                width=84,
                height=28,
                corner_radius=8,
                fg_color="transparent",
                hover_color=CHIP,
                border_width=1,
                border_color=BORDER,
                text_color=MUTED,
                font=self.font_tiny,
                command=self._open_log,
            ),
            lift=2,
        ).grid(row=0, column=2, sticky="e")

    def _image(self, filename: str, size: tuple[int, int]):
        key = (filename, size)
        if key in self._images:
            return self._images[key]
        path = IMAGES_DIR / filename
        if Image is None or not path.is_file():
            return None
        try:
            with Image.open(path) as source:
                picture = source.convert("RGBA")
            image = ctk.CTkImage(
                light_image=picture,
                dark_image=picture,
                size=size,
            )
        except Exception:
            logger.exception("Nie można wczytać obrazu: %s", path)
            return None
        self._images[key] = image
        return image

    def _change_theme(self, value: str) -> None:
        mode = THEME_MODES.get(value, "System")
        ctk.set_appearance_mode(mode)
        self._sync_gradient()
        logger.info("Motyw interfejsu: %s", mode)

    def _sync_gradient(self) -> None:
        appearance = ctk.get_appearance_mode()
        if appearance != self._appearance:
            self._appearance = appearance
            self.gradient.set_mode(appearance == "Dark")

    def _choose_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz plik do konwersji", filetypes=SUPPORTED_FILETYPES
        )
        if path:
            self._set_source(Path(path))

    def _set_source(self, path: Path) -> None:
        self.source_path = Path(path)
        self.last_result = None
        try:
            meta = f"{_human_size(self.source_path)}  ·  {_shorten_path(self.source_path.parent)}"
        except OSError:
            meta = _shorten_path(self.source_path.parent)

        suffix = self.source_path.suffix.lower().lstrip(".")
        self.file_name_label.configure(text=_shorten_name(self.source_path.name))
        self.file_meta_label.configure(text=f"{suffix.upper() or 'PLIK'}  ·  {meta}")
        self.open_input_button.configure(state="normal")

        if self._output_auto or not self.output_var.get().strip():
            self._set_output_dir(self.source_path.parent, auto=True)

        targets = available_targets(self.source_path)
        safe_name = _safe_stem(self.source_path.stem)
        self.name_var.set(safe_name)

        if targets:
            self.file_badge.configure(text="Obsługiwany", text_color=SUCCESS)
            self._set_targets(targets)
            self._set_status(
                "Plik gotowy",
                f"Wybierz format docelowy dla pliku {self.source_path.name}.",
            )
        else:
            self.file_badge.configure(text="Nieobsługiwany", text_color=ERROR)
            self._set_targets([])
            self._show_error(
                ConversionFailedError(
                    f"Format {self.source_path.suffix or 'bez rozszerzenia'} nie jest obsługiwany.",
                    "Wybierz plik CSV, JSON, TXT, DOCX lub ODT.",
                )
            )
        self._update_preview()

    def _set_targets(self, targets: list[str]) -> None:
        self._targets = targets
        self._format_lookup = {target[1:].upper(): target for target in targets}
        if targets:
            displays = list(self._format_lookup)
            self.format_segmented.configure(values=displays, state="normal")
            self.format_segmented.set(displays[0])
            suffix = self._format_lookup[displays[0]]
            self.suffix_label.configure(text=suffix)
            self.name_entry.configure(state="normal")
            self.available_label.configure(
                text=f"Dostępne dla tego pliku: {', '.join(displays)}"
            )
        else:
            self.format_segmented.configure(values=["—"], state="disabled")
            self.format_segmented.set("—")
            self.suffix_label.configure(text="—")
            self.name_entry.configure(state="disabled")
            self.available_label.configure(text="Brak obsługiwanych formatów.")

    def _current_format(self) -> str:
        return self._format_lookup.get(self.format_segmented.get(), "")

    def _on_format_changed(self, value: str) -> None:
        target = self._format_lookup.get(value, "")
        if target:
            self.suffix_label.configure(text=target)
        self._update_preview()

    def _update_preview(self) -> None:
        stem = self.name_var.get().strip()
        target = self._current_format()
        if stem and target:
            final_name = normalize_output_name(stem, target)
            try:
                validate_output_name(stem, target)
                color = MUTED
                text = f"Zapiszę jako: {final_name}"
            except ConverterError as exc:
                color = ERROR
                text = exc.message
            self.preview_label.configure(text=text, text_color=color)
        elif target:
            self.preview_label.configure(
                text="Wpisz nazwę pliku — rozszerzenie dodam automatycznie.",
                text_color=MUTED,
            )
        else:
            self.preview_label.configure(
                text="Rozszerzenie zostanie dodane automatycznie.",
                text_color=MUTED,
            )
        self._update_convert_state()

    def _update_convert_state(self) -> None:
        if getattr(self, "convert_button", None) is None:
            return
        ready = bool(
            not self.busy
            and self.source_path
            and self.source_path.is_file()
            and self._current_format()
            and self.output_var.get().strip()
            and self.name_var.get().strip()
        )
        if ready:
            try:
                validate_output_name(
                    self.name_var.get().strip(), self._current_format()
                )
            except ConverterError:
                ready = False
        self.convert_button.configure(state="normal" if ready else "disabled")

    def _choose_output(self) -> None:
        initial = self.output_var.get().strip() or str(Path.home())
        path = filedialog.askdirectory(
            title="Wybierz katalog zapisu", initialdir=initial
        )
        if path:
            self._set_output_dir(Path(path), auto=False)

    def _set_output_dir(self, path: Path, auto: bool) -> None:
        self._setting_output = True
        self.output_var.set(str(path))
        self._output_auto = auto
        self._setting_output = False
        self._refresh_output_state()

    def _on_output_changed(self) -> None:
        if not self._setting_output:
            self._output_auto = False
        self._refresh_output_state()

    def _refresh_output_state(self) -> None:
        text = self.output_var.get().strip()
        enabled = False
        if text:
            try:
                path = Path(text).expanduser()
                enabled = path.exists() and path.is_dir()
            except (OSError, ValueError):
                enabled = False
        self.output_open_button.configure(state="normal" if enabled else "disabled")
        self._update_convert_state()

    def _conflict_policy(self, request: ConversionRequest) -> str | None:
        target = Path(request.output_dir) / request.target_name()
        if not target.exists():
            return "error"
        dialog = ConflictDialog(self, target)
        self.wait_window(dialog)
        return dialog.result

    def _start_conversion(self) -> None:
        if self.busy:
            return

        source = self.source_path
        target_format = self._current_format()
        output_text = self.output_var.get().strip()
        name = self.name_var.get().strip()

        if source is None or not source.is_file():
            self._show_error(
                ConversionFailedError(
                    "Nie wybrano pliku wejściowego.",
                    "Kliknij „Wybierz plik” i wskaż plik do konwersji.",
                )
            )
            return
        if not target_format:
            self._show_error(
                ConversionFailedError(
                    "Nie wybrano formatu docelowego.",
                    "Wybierz jeden z dostępnych formatów.",
                )
            )
            return
        if not output_text:
            self._show_error(
                ConversionFailedError(
                    "Nie wybrano katalogu zapisu.",
                    "Wpisz ścieżkę lub kliknij „Zmień”.",
                )
            )
            return
        if not name:
            self._show_error(
                ConversionFailedError(
                    "Nie wpisano nazwy pliku.",
                    "Wpisz nazwę bez rozszerzenia, np. raport.",
                )
            )
            return

        request = ConversionRequest(
            source=source,
            target_format=target_format,
            output_dir=Path(output_text).expanduser(),
            output_name=name,
        )

        try:
            request.validate()
        except ConverterError as exc:
            self._show_error(exc)
            return

        policy = self._conflict_policy(request)
        if policy is None:
            self._set_status(
                "Anulowano",
                "Plik nie został nadpisany ani zapisany.",
            )
            return
        if policy != "error":
            request = replace(request, on_exists=policy)

        self._set_busy(True)
        self._set_status(
            "Konwertuję…",
            "Trwa przygotowywanie pliku. To może potrwać kilka sekund.",
            kind="busy",
        )
        thread = threading.Thread(target=self._worker, args=(request,), daemon=True)
        thread.start()

    def _worker(self, request: ConversionRequest) -> None:
        try:
            result = execute(request)
        except ConverterError as exc:
            self.queue.put(("error", exc))
        except Exception as exc:
            self.queue.put(
                (
                    "error",
                    ConversionFailedError(
                        f"Nieoczekiwany błąd: {exc}",
                        "Sprawdź dziennik zdarzeń.",
                    ),
                )
            )
        else:
            self.queue.put(("ok", result))

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.choose_file_button.configure(state=state)
        self.output_entry.configure(state=state)
        self.output_browse_button.configure(state=state)
        self.name_entry.configure(
            state="disabled" if busy or not self._targets else "normal"
        )
        self.format_segmented.configure(
            state="disabled" if busy or not self._targets else "normal"
        )
        self.open_input_button.configure(
            state="normal" if not busy and self.source_path else "disabled"
        )
        if busy:
            self.output_open_button.configure(state="disabled")
            self.convert_button.configure(state="disabled")
            self.progress.grid()
            self.progress.start()
            self.result_actions.grid_remove()
        else:
            self.progress.stop()
            self.progress.grid_remove()
            self._refresh_output_state()
        self._update_convert_state()

    def _set_status(
        self,
        title: str,
        detail: str,
        kind: str = "idle",
        show_actions: bool = False,
    ) -> None:
        colors = {
            "idle": GOLD,
            "busy": ACCENT,
            "success": SUCCESS,
            "error": ERROR,
        }
        dot_colors = {
            "idle": GOLD,
            "busy": ACCENT,
            "success": SUCCESS,
            "error": ERROR,
        }
        self.status_card.configure(border_color=colors.get(kind, BORDER))
        self.status_dot.configure(fg_color=dot_colors.get(kind, MUTED))
        self.status_title.configure(
            text=title,
            text_color=TEXT if kind != "error" else ERROR,
        )
        self.status_detail.configure(text=detail)
        if show_actions and self.last_result is not None:
            self.result_actions.grid()
        else:
            self.result_actions.grid_remove()

    def _show_error(self, error: ConverterError) -> None:
        detail = error.message
        if error.hint:
            detail = f"{detail}\n\n{error.hint}"
        self._set_status("Nie udało się", detail, kind="error")

    def _show_success(self, result: Path) -> None:
        self.last_result = result
        self._set_status(
            "Gotowe!",
            f"Zapisano plik:\n{_shorten_path(result, 70)}",
            kind="success",
            show_actions=True,
        )

    def _poll_queue(self) -> None:
        self._sync_gradient()
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "ok":
                self._set_busy(False)
                self._show_success(payload)
            else:
                self._set_busy(False)
                self._show_error(payload)
        self.after(120, self._poll_queue)

    def _open_input_folder(self) -> None:
        if self.source_path is None:
            return
        self._run_system_action(reveal_in_file_manager, self.source_path)

    def _open_output_folder(self) -> None:
        text = self.output_var.get().strip()
        if not text:
            return
        self._run_system_action(open_path, Path(text).expanduser())

    def _open_result(self) -> None:
        if self.last_result is not None:
            self._run_system_action(open_path, self.last_result)

    def _reveal_result(self) -> None:
        if self.last_result is not None:
            self._run_system_action(reveal_in_file_manager, self.last_result)

    def _open_result_folder(self) -> None:
        if self.last_result is not None:
            self._run_system_action(open_path, self.last_result.parent)

    def _open_log(self) -> None:
        self._run_system_action(open_path, self.log_path)

    def _run_system_action(self, action, path: Path) -> None:
        try:
            action(path)
        except ConverterError as exc:
            self._show_error(exc)
        except Exception as exc:
            self._show_error(
                ConversionFailedError(
                    f"Nie można wykonać operacji systemowej: {exc}",
                    "Spróbuj otworzyć plik ręcznie w menedżerze plików.",
                )
            )

    def _on_return(self, event) -> None:
        if self.convert_button.cget("state") == "normal":
            self._start_conversion()


def _check_macos_tk() -> None:
    if platform.system() != "Darwin" or tk.TkVersion >= 8.6:
        return
    message = (
        "Wykryto Tk 8.5 z systemowego Pythona. Na współczesnym macOS ten Tk "
        "potrafi pokazywać puste, szare okno.\n"
        "Zainstaluj nowszy Python i Tk przez Homebrew:\n"
        "  brew install python@3.12 python-tk@3.12\n"
        "  /opt/homebrew/bin/python3.12 -m venv .venv\n"
        "  source .venv/bin/activate\n"
        "  python -m pip install -r requirements.txt\n"
        "albo uruchom aplikację interpreterem, który ma Tk 8.6+."
    )
    print(message, file=sys.stderr)
    raise SystemExit(1)


def run_gui() -> None:
    setup_logging()
    _check_macos_tk()
    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")
    app = ConverterApp()
    app.mainloop()
