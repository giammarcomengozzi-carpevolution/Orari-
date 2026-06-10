from pathlib import Path

from orari_agent.cli import main
from orari_agent.generator import generate_weekly_schedule
from orari_agent.pdf_exporter import default_pdf_filename, export_weekly_schedule_pdf


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
    assert b"Lunedi" in content
    assert b"Domenica" in content
    assert b"Lago mattina" in content
    assert b"Negozio pomeriggio" in content
    assert b"Avvisi / conflitti" in content
    assert b"ATTENZIONE" in content


def test_export_weekly_schedule_pdf_includes_no_conflict_message(tmp_path):
    schedule = generate_weekly_schedule("", week_start_date="2026-06-08")

    pdf_path = export_weekly_schedule_pdf(schedule, tmp_path)

    content = pdf_path.read_bytes()
    assert b"Nessun conflitto rilevato." in content


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
