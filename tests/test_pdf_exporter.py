from pathlib import Path

from orari_agent.cli import main
from orari_agent.generator import generate_weekly_schedule
from orari_agent.pdf_exporter import default_pdf_filename, export_weekly_schedule_pdf
from orari_agent.presentation import operational_day_views


def test_default_pdf_filename_uses_week_start_date():
    assert (
        default_pdf_filename("2026-06-08")
        == "Orario_CarpeEvolution_Tenuta_2026-06-08.pdf"
    )


def test_export_weekly_schedule_pdf_creates_landscape_pdf_with_polished_layout(
    tmp_path,
):
    schedule = generate_weekly_schedule(
        "Sabato Angelo è in ferie", week_start_date="2026-06-08"
    )

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)

    assert pdf_path == tmp_path / "Orario_CarpeEvolution_Tenuta_2026-06-08.pdf"
    content = pdf_path.read_bytes()
    assert content.startswith(b"%PDF-1.4")
    assert b"/MediaBox [0 0 841.89 595.28]" in content
    assert b"Orario settimanale" in content
    assert b"CarpeEvolution Store & Tenuta del Germano" in content
    assert b"Settimana: 2026-06-08 / 2026-06-14" in content
    assert b"MARTEDI" in content
    assert b"SABATO" in content
    assert b"Persona" in content
    assert b"Timeline / Orario" in content
    assert b"Compito" in content
    assert b"Lago mattina" not in content
    assert b"Negozio pomeriggio" not in content
    assert b"Conflitti critici / alert" in content
    assert b"ATTENZIONE" in content


def test_export_weekly_schedule_pdf_includes_no_conflict_message(tmp_path):
    schedule = generate_weekly_schedule("", week_start_date="2026-06-08")

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)

    content = pdf_path.read_bytes()
    assert b"Nessun conflitto critico rilevato" in content


def test_export_weekly_schedule_pdf_does_not_crash_with_many_notes(tmp_path):
    schedule = generate_weekly_schedule("", week_start_date="2026-06-08")
    notes = [f"Nota operativa numero {index}" for index in range(1, 16)]

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path, weekly_notes=notes)

    content = pdf_path.read_bytes()
    assert pdf_path.exists()
    assert b"Note operative" in content
    assert b"Pagina 2" in content


def test_cli_pdf_option_writes_chosen_output_path(tmp_path, capsys):
    output_path = tmp_path / "orario.pdf"

    exit_code = main(
        [
            "--week-start",
            "2026-06-08",
            "--pdf",
            "--output",
            str(output_path),
            "Domenica Lorenzo",
            "è assente",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_path.exists()
    assert f"PDF generato: {output_path}" in captured.out


def test_operational_pdf_shows_effective_shift_rows_and_weekly_totals(tmp_path):
    schedule = generate_weekly_schedule(
        "Martedì Gianmarco apre il lago. Martedì Angelo in negozio.",
        week_start_date="2026-06-15",
    )

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    assert b"Persona" in content
    assert b"Timeline / Orario" in content
    assert b"Pausa" in content
    assert b"Compito" in content
    assert b"Lago mattina" not in content
    assert b"Lago pomeriggio" not in content
    assert b"Negozio mattina" not in content
    assert b"Negozio pomeriggio" not in content
    assert b"Gianmarco Mengozzi" in content
    assert b"07:30-16:30" in content
    assert b"14:00-15:00" in content
    assert b"APERTURA LAGO" in content
    assert b"Angelo Antonelli" in content
    assert b"09:00-12:30 / 15:30-19:30" in content
    assert b"12:30-15:30" in content
    assert b"NEGOZIO" in content
    assert b"Riepilogo monte ore settimanale" in content
    assert b"Lorenzo Sansavini" in content


def test_operational_pdf_can_show_lake_second_shift_with_break(tmp_path):
    schedule = generate_weekly_schedule(
        "Martedì Lorenzo chiude il lago", week_start_date="2026-06-15"
    )

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    assert b"09:30-18:30" in content
    assert b"13:30-14:30" in content
    assert b"CHIUSURA LAGO" in content


def test_operational_day_view_merges_same_person_day_location_segments():
    schedule = generate_weekly_schedule("", week_start_date="2026-06-22")

    views = operational_day_views(schedule)
    thursday = next(view for view in views if view.day == "Giovedì")
    lake = next(
        section for section in thursday.location_sections if section.location == "LAGO"
    )
    gianmarco = next(row for row in lake.rows if "Giammarco" in row.person)

    assert gianmarco.work_time == "14:00-15:00 / 16:30-18:30"
    assert gianmarco.break_time == "-"
    assert "14:00-15:00 / 16:30-18:30 | 14:00" in gianmarco.timeline


def test_operational_day_view_contains_lake_and_shop_sections_for_each_day():
    schedule = generate_weekly_schedule("", week_start_date="2026-06-22")

    for view in operational_day_views(schedule):
        section_names = [section.location for section in view.location_sections]
        assert "LAGO" in section_names
        assert "NEGOZIO" in section_names


def test_operational_pdf_uses_day_cards_and_keeps_weekly_totals(tmp_path):
    schedule = generate_weekly_schedule("", week_start_date="2026-10-05")

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    for day in (
        b"LUNEDI",
        b"MARTEDI",
        b"MERCOLEDI",
        b"GIOVEDI",
        b"VENERDI",
        b"SABATO",
        b"DOMENICA",
    ):
        assert day in content
    assert b"LAGO" in content
    assert b"NEGOZIO" in content
    assert b"Timeline / Orario" in content
    assert b"Riepilogo monte ore settimanale" in content
    assert b"OK 40h" in content


def test_pdf_day_card_headers_follow_standard_opening_days(tmp_path):
    schedule = generate_weekly_schedule("", week_start_date="2026-10-05")

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    assert b"Lago chiuso  |  Negozio chiuso" in content
    assert (
        b"Lago aperto 07:30-18:30  |  Negozio aperto 09:00-12:30 / 15:30-19:30"
        in content
    )
    assert b"Lago aperto 07:30-18:30  |  Negozio chiuso" in content


def test_pdf_day_card_headers_show_seasonal_evening_lake_opening(tmp_path):
    schedule = generate_weekly_schedule("", week_start_date="2026-06-22")

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    assert b"Lago aperto 07:30-23:00 \\(evento serale\\)" in content
    assert (
        b"Lago aperto 07:30-23:00 \\(evento serale\\)  |  Negozio aperto 09:00-12:30 / 15:30-19:30"
        in content
    )
    assert b"Lago aperto 07:30-23:00 \\(evento serale\\)  |  Negozio chiuso" in content
    assert b"EVENTO SERALE LAGO" in content
    assert b"CHIUSURA LAGO 23:00" in content
    assert b"SUPPORTO SERALE LAGO" in content
    assert b"20:00-22:00" in content
    assert b"09:00-12:30 / 15:30-19:30" in content


def test_seasonal_lake_presentation_keeps_real_long_shift_times_and_breaks():
    schedule = generate_weekly_schedule("", week_start_date="2026-06-22")
    views = {view.day: view for view in operational_day_views(schedule)}

    friday_lake = next(
        section
        for section in views["Venerdì"].location_sections
        if section.location == "LAGO"
    )
    friday_rows = {(row.person, row.work_time): row for row in friday_lake.rows}

    assert any(work_time == "07:30-21:30" for _, work_time in friday_rows)
    assert any(work_time == "10:00-23:00" for _, work_time in friday_rows)
    assert all(row.work_time != "09:30-18:30" for row in friday_lake.rows)
    assert (
        next(
            row for row in friday_lake.rows if row.work_time == "07:30-21:30"
        ).break_time
        == "14:00-15:00"
    )
    assert (
        next(
            row for row in friday_lake.rows if row.work_time == "10:00-23:00"
        ).break_time
        == "16:00-17:00"
    )


def test_friday_seasonal_presentation_includes_angelo_shop_and_evening_lake_support():
    schedule = generate_weekly_schedule("", week_start_date="2026-06-22")
    friday = next(
        view for view in operational_day_views(schedule) if view.day == "Venerdì"
    )

    shop = next(
        section for section in friday.location_sections if section.location == "NEGOZIO"
    )
    lake = next(
        section for section in friday.location_sections if section.location == "LAGO"
    )

    assert any(
        row.person == "Angelo Antonelli"
        and row.work_time == "09:00-12:30 / 15:30-19:30"
        for row in shop.rows
    )
    assert any(
        row.person == "Angelo Antonelli" and row.work_time == "20:00-22:00"
        for row in lake.rows
    )


def test_sunday_seasonal_presentation_includes_all_staggered_long_lake_shifts():
    schedule = generate_weekly_schedule("", week_start_date="2026-06-22")
    sunday = next(
        view for view in operational_day_views(schedule) if view.day == "Domenica"
    )
    lake = next(
        section for section in sunday.location_sections if section.location == "LAGO"
    )

    assert {row.work_time for row in lake.rows} == {
        "07:30-21:00",
        "09:00-22:00",
        "11:00-23:00",
    }
    assert all("18:30" not in row.work_time for row in lake.rows)


def _schedule_with_many_effective_shifts(count: int):
    from orari_agent.business_rules import ActivityId
    from orari_agent.models import Assignment, DaySchedule, WeeklySchedule

    assignments = [
        Assignment(
            "Giammarco Mengozzi",
            ActivityId.COMPANY_WORK,
            f"ESTERNO-{index:02d}",
            "07:00",
            "07:10",
            1 / 6,
        )
        for index in range(1, count + 1)
    ]
    return WeeklySchedule(
        days=[DaySchedule(day="Martedì", company_work=assignments)],
        week_start_date="2026-06-15",
    )


def test_operational_pdf_with_more_than_18_shifts_includes_all_shift_rows(tmp_path):
    schedule = _schedule_with_many_effective_shifts(12)

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    for index in range(1, 13):
        assert f"ESTERNO-{index:02d}".encode() in content


def test_operational_pdf_creates_continuation_page_when_needed(tmp_path):
    schedule = _schedule_with_many_effective_shifts(34)

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    assert b"Pagina 2" in content


def test_operational_pdf_does_not_claim_unprinted_detail_shifts(tmp_path):
    schedule = _schedule_with_many_effective_shifts(34)

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)
    content = pdf_path.read_bytes()

    assert b"turni disponibili nei dettagli" not in content
