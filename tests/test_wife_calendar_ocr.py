from pathlib import Path

from orari_agent.wife_calendar_ocr import extract_m_dates_from_image


def _write_synthetic_calendar(path: Path, marks: list[tuple[int, int]]) -> None:
    cell_w = 24
    cell_h = 18
    rows = 13  # header + 12 months
    cols = 32  # month label + days 1..31
    width = cols * cell_w + 1
    height = rows * cell_h + 1
    pixels = [255] * (width * height * 3)

    def set_pixel(x: int, y: int, color: tuple[int, int, int] = (0, 0, 0)) -> None:
        index = (y * width + x) * 3
        pixels[index : index + 3] = list(color)

    for x in range(0, width, cell_w):
        for y in range(height):
            set_pixel(x, y)
    for y in range(0, height, cell_h):
        for x in range(width):
            set_pixel(x, y)

    def draw_line(x1: int, y1: int, x2: int, y2: int) -> None:
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        while True:
            for ox in range(-1, 2):
                for oy in range(-1, 2):
                    if 0 <= x1 + ox < width and 0 <= y1 + oy < height:
                        set_pixel(x1 + ox, y1 + oy)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy

    for month, day in marks:
        x0 = day * cell_w
        y0 = month * cell_h
        left = x0 + 6
        right = x0 + cell_w - 6
        top = y0 + 4
        bottom = y0 + cell_h - 4
        middle = x0 + cell_w // 2
        draw_line(left, bottom, left, top)
        draw_line(left, top, middle, y0 + cell_h // 2)
        draw_line(middle, y0 + cell_h // 2, right, top)
        draw_line(right, top, right, bottom)

    path.write_bytes(b"P6\n%d %d\n255\n" % (width, height) + bytes(pixels))


def test_ocr_module_extracts_m_from_clean_generated_table(tmp_path):
    image_path = tmp_path / "calendario.ppm"
    _write_synthetic_calendar(image_path, marks=[(1, 3), (9, 10)])

    result = extract_m_dates_from_image(image_path, year=2026)

    assert result.imported_dates == ["2026-01-03", "2026-09-10"]
    assert result.confidence >= 0.75
    assert result.warnings == []
    assert "celle M=2" in result.debug_summary


def test_ocr_module_low_confidence_returns_warning(tmp_path):
    image_path = tmp_path / "vuota.ppm"
    image_path.write_bytes(b"P6\n20 20\n255\n" + bytes([255] * 20 * 20 * 3))

    result = extract_m_dates_from_image(image_path, year=2026)

    assert result.imported_dates == []
    assert result.confidence < 0.75
    assert result.warnings
    assert "Griglia" in result.warnings[0]
