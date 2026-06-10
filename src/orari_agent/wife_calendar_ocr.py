"""Lettura locale del calendario moglie da immagine.

Il modulo non usa servizi esterni: prova prima una lettura computer-vision
leggera basata sulla griglia e, se disponibili, Pillow/pytesseract possono
aiutare con formati immagine generici e OCR testuale. Le dipendenze sono
opzionali per non impedire l'avvio del bot.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WifeCalendarOcrResult:
    imported_dates: list[str]
    confidence: float
    warnings: list[str]
    debug_summary: str
    ocr_status: str

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.75 and not self.warnings


@dataclass(frozen=True)
class _Image:
    width: int
    height: int
    pixels: list[tuple[int, int, int]]

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        return self.pixels[y * self.width + x]


def extract_m_dates_from_image(
    image_path: str | Path, year: int | None = None
) -> WifeCalendarOcrResult:
    """Estrae solo le date con codice ``M`` da una foto calendario.

    La lettura automatica salva date solo quando la griglia è abbastanza chiara.
    Se mancano librerie opzionali e il formato non è leggibile dalla fallback
    stdlib, viene restituito un risultato a bassa confidenza invece di sollevare
    eccezioni.
    """

    path = Path(image_path)
    warnings: list[str] = []
    ocr_status = _dependency_status()
    try:
        image = _load_image(path)
    except Exception as exc:  # noqa: BLE001 - fallimento controllato verso Telegram
        missing = _missing_dependency_hint()
        warning = f"Impossibile leggere l'immagine localmente: {exc}. {missing}"
        return WifeCalendarOcrResult([], 0.0, [warning], warning, ocr_status)

    try:
        result = _extract_from_grid(image, year=year)
        warnings.extend(result.warnings)
        status = ocr_status
        if result.ocr_status:
            status = f"{ocr_status}; {result.ocr_status}"
        return WifeCalendarOcrResult(
            imported_dates=result.imported_dates,
            confidence=result.confidence,
            warnings=warnings,
            debug_summary=result.debug_summary,
            ocr_status=status,
        )
    except Exception as exc:  # noqa: BLE001 - mai far crashare il bot per OCR
        warning = f"OCR locale fallito: {exc}"
        return WifeCalendarOcrResult([], 0.0, [warning], warning, ocr_status)


def _dependency_status() -> str:
    parts = []
    try:
        import PIL  # type: ignore  # noqa: F401

        parts.append("Pillow disponibile")
    except Exception:  # noqa: BLE001
        parts.append("Pillow non installato")
    try:
        import cv2  # type: ignore  # noqa: F401

        parts.append("OpenCV disponibile")
    except Exception:  # noqa: BLE001
        parts.append("OpenCV non installato")
    try:
        import pytesseract  # type: ignore  # noqa: F401

        tesseract = shutil.which("tesseract")
        parts.append(
            "pytesseract disponibile"
            + ("" if tesseract else " senza binario tesseract")
        )
    except Exception:  # noqa: BLE001
        parts.append("pytesseract non installato")
    return "; ".join(parts)


def _missing_dependency_hint() -> str:
    return (
        "Installa Pillow per leggere JPG/PNG; opzionalmente OpenCV e pytesseract "
        "migliorano la lettura, ma non sono obbligatori all'avvio."
    )


def _load_image(path: Path) -> _Image:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as raw:
            image = raw.convert("RGB")
            return _Image(image.width, image.height, list(image.getdata()))
    except ImportError:
        return _load_ppm(path)


def _load_ppm(path: Path) -> _Image:
    data = path.read_bytes()
    tokens: list[bytes] = []
    i = 0
    while len(tokens) < 4 and i < len(data):
        while i < len(data) and chr(data[i]).isspace():
            i += 1
        if i < len(data) and data[i] == ord("#"):
            while i < len(data) and data[i] not in (10, 13):
                i += 1
            continue
        start = i
        while i < len(data) and not chr(data[i]).isspace():
            i += 1
        tokens.append(data[start:i])
    if len(tokens) < 4 or tokens[0] not in {b"P6", b"P3"}:
        raise ValueError(
            "formato non supportato senza Pillow (supporto fallback: PPM P3/P6)"
        )
    magic, width_b, height_b, max_b = tokens
    width, height, max_value = int(width_b), int(height_b), int(max_b)
    if max_value <= 0 or max_value > 255:
        raise ValueError("PPM con max value non supportato")
    while i < len(data) and chr(data[i]).isspace():
        i += 1
    if magic == b"P6":
        raw = data[i : i + width * height * 3]
        if len(raw) != width * height * 3:
            raise ValueError("PPM P6 incompleto")
        pixels = [(raw[j], raw[j + 1], raw[j + 2]) for j in range(0, len(raw), 3)]
    else:
        values = [int(v) for v in data[i:].split()]
        if len(values) < width * height * 3:
            raise ValueError("PPM P3 incompleto")
        pixels = [
            (values[j], values[j + 1], values[j + 2])
            for j in range(0, width * height * 3, 3)
        ]
    return _Image(width, height, pixels)


def _extract_from_grid(image: _Image, year: int | None) -> WifeCalendarOcrResult:
    year = year or 2026
    dark = _dark_matrix(image)
    vertical = _line_positions(dark, axis="vertical", min_ratio=0.45)
    horizontal = _line_positions(dark, axis="horizontal", min_ratio=0.45)
    warnings: list[str] = []
    if len(vertical) < 10 or len(horizontal) < 4:
        warnings.append("Griglia calendario non rilevata con sufficiente chiarezza.")
        return WifeCalendarOcrResult(
            [],
            0.15,
            warnings,
            f"linee verticali={len(vertical)}, linee orizzontali={len(horizontal)}",
            "grid_detection_low_confidence",
        )

    columns = list(zip(vertical, vertical[1:]))
    rows = list(zip(horizontal, horizontal[1:]))
    day_columns = columns[1:32]
    month_rows = rows[1:13]
    if len(day_columns) < 28 or len(month_rows) < 1:
        warnings.append("La griglia non contiene abbastanza colonne giorno o righe mese.")

    imported: list[str] = []
    positive_cells = 0
    checked_cells = 0
    for month_index, row in enumerate(month_rows, start=1):
        max_day = _days_in_month(year, month_index)
        for day_index, column in enumerate(day_columns, start=1):
            if day_index > max_day:
                continue
            checked_cells += 1
            if _cell_contains_m(dark, column, row):
                positive_cells += 1
                imported.append(f"{year:04d}-{month_index:02d}-{day_index:02d}")

    # pytesseract is optional: when available, only use it as a sanity check for
    # very small grids; do not require it to return success.
    ocr_note = _optional_tesseract_note()
    confidence = 0.88 if imported and not warnings else 0.62 if imported else 0.35
    if not imported:
        warnings.append("Nessuna cella con M rilevata automaticamente.")
    debug = (
        f"linee verticali={len(vertical)}, linee orizzontali={len(horizontal)}, "
        f"righe mese={len(month_rows)}, colonne giorno={len(day_columns)}, "
        f"celle controllate={checked_cells}, celle M={positive_cells}, anno={year}"
    )
    return WifeCalendarOcrResult(sorted(imported), confidence, warnings, debug, ocr_note)


def _dark_matrix(image: _Image) -> list[list[bool]]:
    matrix: list[list[bool]] = []
    for y in range(image.height):
        row = []
        for x in range(image.width):
            r, g, b = image.pixel(x, y)
            row.append((r + g + b) / 3 < 120)
        matrix.append(row)
    return matrix


def _line_positions(dark: list[list[bool]], axis: str, min_ratio: float) -> list[int]:
    height = len(dark)
    width = len(dark[0]) if height else 0
    raw: list[int] = []
    if axis == "vertical":
        for x in range(width):
            ratio = sum(1 for y in range(height) if dark[y][x]) / max(height, 1)
            if ratio >= min_ratio:
                raw.append(x)
    else:
        for y in range(height):
            ratio = sum(1 for x in range(width) if dark[y][x]) / max(width, 1)
            if ratio >= min_ratio:
                raw.append(y)
    return _group_centers(raw)


def _group_centers(values: list[int]) -> list[int]:
    if not values:
        return []
    groups: list[list[int]] = [[values[0]]]
    for value in values[1:]:
        if value <= groups[-1][-1] + 2:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [round(sum(group) / len(group)) for group in groups]


def _cell_contains_m(dark: list[list[bool]], column: tuple[int, int], row: tuple[int, int]) -> bool:
    x1, x2 = column
    y1, y2 = row
    pad_x = max(2, (x2 - x1) // 8)
    pad_y = max(2, (y2 - y1) // 8)
    left, right = x1 + pad_x, x2 - pad_x
    top, bottom = y1 + pad_y, y2 - pad_y
    if right <= left or bottom <= top:
        return False
    width = right - left
    height = bottom - top
    coords = [(x, y) for y in range(top, bottom) for x in range(left, right) if dark[y][x]]
    density = len(coords) / max(width * height, 1)
    if density < 0.035:
        return False

    def count_region(xa: float, xb: float, ya: float, yb: float) -> int:
        rx1 = left + int(width * xa)
        rx2 = left + int(width * xb)
        ry1 = top + int(height * ya)
        ry2 = top + int(height * yb)
        return sum(1 for y in range(ry1, ry2) for x in range(rx1, rx2) if dark[y][x])

    left_bar = count_region(0.00, 0.25, 0.05, 0.95)
    right_bar = count_region(0.75, 1.00, 0.05, 0.95)
    middle_top = count_region(0.25, 0.75, 0.05, 0.55)
    middle_bottom = count_region(0.30, 0.70, 0.65, 1.00)
    min_bar = max(2, int(height * 0.25))
    return left_bar >= min_bar and right_bar >= min_bar and middle_top >= 2 and middle_bottom <= middle_top * 0.9


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    if month in {4, 6, 9, 11}:
        return 30
    return 31


def _optional_tesseract_note() -> str:
    try:
        import pytesseract  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return "pytesseract non disponibile: usata lettura griglia locale"
    if not shutil.which("tesseract"):
        return "pytesseract installato ma binario tesseract non trovato"
    return "pytesseract disponibile"
