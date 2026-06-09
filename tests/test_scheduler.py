from orari_agent.generator import generate_weekly_schedule
from orari_agent.weekly_input import parse_weekly_instruction


def _people_for(day, activity):
    return [assignment.person for assignment in day.assignments() if assignment.activity == activity]


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


def test_parser_supports_absence_and_gianmarco_lake_instruction():
    instruction = parse_weekly_instruction(
        "Domenica Lorenzo è assente. "
        "Sabato Angelo è in ferie. "
        "Venerdì Gianmarco deve stare al lago."
    )

    assert instruction.lorenzo_absent_days == {"Domenica"}
    assert instruction.angelo_absent_days == {"Sabato"}
    assert instruction.gianmarco_lake_days == {"Venerdì"}


def test_gianmarco_shop_instruction_rebalances_lake_closing_with_angelo():
    schedule = generate_weekly_schedule("Giovedì Gianmarco deve stare in negozio per fatture")
    thursday = next(day for day in schedule.days if day.day == "Giovedì")

    assert thursday.warnings == []
    assert any(
        assignment.person == "Gianmarco Mengozzi"
        and assignment.activity == "shop"
        and assignment.start == "15:30"
        and assignment.end == "19:30"
        for assignment in thursday.assignments()
    )
    assert any(
        assignment.person == "Angelo Antonelli"
        and assignment.activity == "lake"
        and assignment.start == "16:30"
        and assignment.end == "18:30"
        for assignment in thursday.assignments()
    )


def test_lorenzo_absent_on_sunday_moves_his_lake_day_to_tuesday():
    schedule = generate_weekly_schedule("Domenica Lorenzo è assente")

    assert schedule.global_warnings == []
    assert all(day.warnings == [] for day in schedule.days)
    lorenzo_days = [
        day.day
        for day in schedule.days
        if any(assignment.person == "Lorenzo Sansavini" for assignment in day.assignments())
    ]
    assert lorenzo_days == ["Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
    sunday = next(day for day in schedule.days if day.day == "Domenica")
    assert _people_for(sunday, "lake") == ["Gianmarco Mengozzi"]


def test_angelo_absent_on_saturday_reports_infeasible_lake_closing_gap():
    schedule = generate_weekly_schedule("Sabato Angelo è in ferie")
    saturday = next(day for day in schedule.days if day.day == "Sabato")

    assert any("16:30" in warning and "18:30" in warning for warning in saturday.warnings)
    assert any(
        assignment.person == "Gianmarco Mengozzi"
        and assignment.activity == "shop"
        and assignment.start == "15:30"
        and assignment.end == "19:30"
        for assignment in saturday.assignments()
    )


def test_gianmarco_lake_instruction_keeps_shop_covered_by_angelo():
    schedule = generate_weekly_schedule("Venerdì Gianmarco deve stare al lago")
    friday = next(day for day in schedule.days if day.day == "Venerdì")

    assert friday.warnings == []
    assert "Gianmarco Mengozzi" in _people_for(friday, "lake")
    assert "Angelo Antonelli" in _people_for(friday, "shop")
