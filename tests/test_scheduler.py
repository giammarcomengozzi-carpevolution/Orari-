from orari_agent.generator import generate_weekly_schedule
from orari_agent.weekly_input import parse_weekly_instruction


def test_default_schedule_has_no_warnings():
    schedule = generate_weekly_schedule("")

    assert schedule.global_warnings == []
    assert all(day.warnings == [] for day in schedule.days)


def test_lorenzo_forced_tuesday_keeps_forty_hours_and_five_days():
    schedule = generate_weekly_schedule("Lorenzo deve aprire il lago martedì")

    assert schedule.global_warnings == []
    lorenzo_days = [
        day.day
        for day in schedule.days
        if any(assignment.person == "Lorenzo Sansavini" for assignment in day.assignments())
    ]
    assert lorenzo_days == ["Martedì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def test_parser_supports_example_sentence_in_english():
    instruction = parse_weekly_instruction(
        "Next week Lorenzo must open the lake on Tuesday. "
        "On Thursday Gianmarco must stay in the shop for invoices. "
        "On Sunday the lake has many bookings."
    )

    assert instruction.lorenzo_must_open_lake_days == {"Martedì"}
    assert instruction.gianmarco_shop_days == {"Giovedì"}
    assert instruction.high_lake_booking_days == {"Domenica"}


def test_gianmarco_shop_instruction_reports_lake_closing_gap():
    schedule = generate_weekly_schedule("Giovedì Gianmarco deve stare in negozio per fatture")
    thursday = next(day for day in schedule.days if day.day == "Giovedì")

    assert any("16:30" in warning and "18:30" in warning for warning in thursday.warnings)
