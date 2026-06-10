from orari_agent.generator import generate_weekly_schedule
from orari_agent.weekly_input import parse_weekly_instruction

GIAMMARCO = "Giammarco Mengozzi"


def _people_for(day, activity):
    return [
        assignment.person
        for assignment in day.assignments()
        if assignment.activity == activity
    ]


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
        if any(
            assignment.person == "Lorenzo Sansavini" for assignment in day.assignments()
        )
    ]
    assert lorenzo_days == ["Martedì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def test_parser_supports_example_sentence_in_english():
    instruction = parse_weekly_instruction(
        "Next week Lorenzo must open the lake on Tuesday. "
        "On Thursday Giammarco must stay in the shop for invoices. "
        "On Sunday the lake has many bookings."
    )

    assert instruction.lorenzo_must_open_lake_days == {"Martedì"}
    assert instruction.giammarco_shop_days == {"Giovedì"}
    assert instruction.high_lake_booking_days == {"Domenica"}


def test_giammarco_requested_shop_day_count_assigns_two_shop_days():
    instruction = parse_weekly_instruction(
        "Giammarco deve stare due giorni in negozio questa settimana"
    )

    assert instruction.giammarco_requested_shop_day_count == 2

    schedule = generate_weekly_schedule(
        "Giammarco deve stare due giorni in negozio questa settimana"
    )
    giammarco_shop_days = {
        day.day
        for day in schedule.days
        if any(
            assignment.person == GIAMMARCO and assignment.activity == "shop"
            for assignment in day.assignments()
        )
    }

    assert giammarco_shop_days == {"Mercoledì", "Giovedì"}
    assert all(day.warnings == [] for day in schedule.days)


def test_parser_supports_absence_and_giammarco_lake_instruction():
    instruction = parse_weekly_instruction(
        "Domenica Lorenzo è assente. "
        "Sabato Angelo è in ferie. "
        "Venerdì Giammarco deve stare al lago."
    )

    assert instruction.lorenzo_absent_days == {"Domenica"}
    assert instruction.angelo_absent_days == {"Sabato"}
    assert instruction.giammarco_lake_days == {"Venerdì"}


def test_giammarco_shop_instruction_rebalances_lake_closing_with_angelo():
    schedule = generate_weekly_schedule(
        "Giovedì Giammarco deve stare in negozio per fatture"
    )
    thursday = next(day for day in schedule.days if day.day == "Giovedì")

    assert thursday.warnings == []
    assert any(
        assignment.person == GIAMMARCO
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
        if any(
            assignment.person == "Lorenzo Sansavini" for assignment in day.assignments()
        )
    ]
    assert lorenzo_days == ["Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
    sunday = next(day for day in schedule.days if day.day == "Domenica")
    assert _people_for(sunday, "lake") == [GIAMMARCO]


def test_angelo_absent_on_saturday_reports_infeasible_lake_closing_gap():
    schedule = generate_weekly_schedule("Sabato Angelo è in ferie")
    saturday = next(day for day in schedule.days if day.day == "Sabato")

    assert any(
        "16:30" in warning and "18:30" in warning for warning in saturday.warnings
    )
    assert any(
        assignment.person == GIAMMARCO
        and assignment.activity == "shop"
        and assignment.start == "15:30"
        and assignment.end == "19:30"
        for assignment in saturday.assignments()
    )


def test_giammarco_lake_instruction_keeps_shop_covered_by_angelo():
    schedule = generate_weekly_schedule("Venerdì Giammarco deve stare al lago")
    friday = next(day for day in schedule.days if day.day == "Venerdì")

    assert friday.warnings == []
    assert GIAMMARCO in _people_for(friday, "lake")
    assert "Angelo Antonelli" in _people_for(friday, "shop")


def test_giammarco_external_work_is_not_fixed_coverage():
    schedule = generate_weekly_schedule("Giovedì Giammarco è dal commercialista")
    thursday = next(day for day in schedule.days if day.day == "Giovedì")

    assert any(
        assignment.person == GIAMMARCO and assignment.activity == "company_work"
        for assignment in thursday.company_work
    )
    assert not any(
        assignment.person == GIAMMARCO and assignment.activity in {"lake", "shop"}
        for assignment in thursday.assignments()
    )
    assert any(
        "commercialista" in note and "non conta come copertura fissa" in note
        for note in thursday.notes
    )


def test_giammarco_morning_external_work_allows_later_coverage():
    schedule = generate_weekly_schedule(
        "Domenica Lorenzo è assente. Domenica Giammarco mattina è in banca"
    )
    sunday = next(day for day in schedule.days if day.day == "Domenica")

    assert any(
        assignment.person == GIAMMARCO
        and assignment.activity == "lake"
        and assignment.start == "14:00"
        and assignment.end == "18:30"
        for assignment in sunday.assignments()
    )
    assert not any(
        assignment.person == GIAMMARCO
        and assignment.activity == "lake"
        and assignment.start == "07:30"
        for assignment in sunday.assignments()
    )


def test_wife_calendar_m_blocks_only_giammarco_lake_opening():
    schedule = generate_weekly_schedule(
        "Domenica Lorenzo è assente",
        week_start_date="2026-06-08",
        wife_calendar_codes={"2026-06-14": "M"},
    )
    sunday = next(day for day in schedule.days if day.day == "Domenica")

    assert any(
        warning == "Conflitto: Giammarco non può aprire il lago il 2026-06-14 perché nel calendario moglie c’è M."
        for warning in sunday.warnings
    )
    assert not any(
        assignment.person == GIAMMARCO
        and assignment.activity == "lake"
        and assignment.start == "07:30"
        for assignment in sunday.assignments()
    )


def test_wife_calendar_p_is_ignored():
    schedule = generate_weekly_schedule(
        "Domenica Lorenzo è assente",
        week_start_date="2026-06-08",
        wife_calendar_codes={"2026-06-14": "P"},
    )
    sunday = next(day for day in schedule.days if day.day == "Domenica")

    assert sunday.warnings == []
    assert any(
        assignment.person == GIAMMARCO
        and assignment.activity == "lake"
        and assignment.start == "07:30"
        for assignment in sunday.assignments()
    )


def test_parser_supports_date_ranges_and_half_day_absences():
    instruction = parse_weekly_instruction(
        "Lorenzo non c'è da giovedì a domenica. Angelo è assente sabato pomeriggio."
    )

    assert instruction.lorenzo_absent_days == {
        "Giovedì",
        "Venerdì",
        "Sabato",
        "Domenica",
    }
    assert instruction.afternoon_absence_days_for("Angelo Antonelli") == {"Sabato"}


def test_lorenzo_morning_absence_reassigns_coverage_and_warns_about_hours():
    schedule = generate_weekly_schedule("Lorenzo non è disponibile venerdì mattina")
    friday = next(day for day in schedule.days if day.day == "Venerdì")

    assert not any(
        assignment.person == "Lorenzo Sansavini" and assignment.start == "07:30"
        for assignment in friday.assignments()
    )
    assert any(
        assignment.person == GIAMMARCO
        and assignment.activity == "lake"
        and assignment.start == "07:30"
        for assignment in friday.assignments()
    )
    assert any("Lorenzo ha" in warning for warning in schedule.global_warnings)
    assert any(
        "Venerdì" in warning and "devono essere 8 ore" in warning
        for warning in schedule.global_warnings
    )


def test_forced_lake_closing_and_extra_lake_coverage_are_applied():
    schedule = generate_weekly_schedule(
        "Giammarco deve fare chiusura lago domenica. Sabato pomeriggio serve più copertura al lago."
    )
    sunday = next(day for day in schedule.days if day.day == "Domenica")
    saturday = next(day for day in schedule.days if day.day == "Sabato")

    assert any(
        assignment.person == GIAMMARCO
        and assignment.activity == "lake"
        and assignment.start == "14:00"
        and assignment.end == "18:30"
        for assignment in sunday.assignments()
    )
    assert any("attenzione extra" in note for note in saturday.notes)
    assert any(
        assignment.person == GIAMMARCO and assignment.activity == "lake"
        for assignment in saturday.assignments()
    )


def test_exceptional_closure_and_opening_change_required_coverage():
    schedule = generate_weekly_schedule(
        "Il negozio resta chiuso giovedì pomeriggio. Apertura straordinaria del lago lunedì."
    )
    monday = next(day for day in schedule.days if day.day == "Lunedì")
    thursday = next(day for day in schedule.days if day.day == "Giovedì")

    assert monday.lake_required_ranges == [("07:30", "18:30")]
    assert any(assignment.activity == "lake" for assignment in monday.assignments())
    assert thursday.shop_required_ranges == [("09:00", "12:30")]
    assert thursday.shop_afternoon == []
    assert not any("negozio pomeriggio" in warning for warning in thursday.warnings)


def test_structured_weekly_planning_yaml_file_generates_schedule(tmp_path):
    from orari_agent.weekly_input import load_structured_weekly_planning

    planning_file = tmp_path / "weekly_plan.yaml"
    planning_file.write_text(
        """
week_start: 2026-06-15
absences:
  Lorenzo Sansavini:
    - day: venerdì
      period: full_day
      reason: ferie
giammarco:
  preferred_shop_days:
    - mercoledì
  company_work:
    - day: martedì
      period: morning
      reason: commercialista
lake:
  exceptional_openings:
    - day: lunedì
      period: full_day
      reason: apertura straordinaria
  extra_coverage:
    - day: domenica
      period: full_day
      reason: lago pieno di prenotazioni
  exceptional_closures:
    - day: mercoledì
      period: afternoon
      reason: manutenzione
shop:
  exceptional_closures:
    - day: giovedì
      period: afternoon
      reason: inventario
notes:
  - PDF pronto per WhatsApp.
""".strip(),
        encoding="utf-8",
    )

    planning = load_structured_weekly_planning(planning_file)
    schedule = generate_weekly_schedule(
        planning.instruction, week_start_date=planning.week_start
    )
    monday = next(day for day in schedule.days if day.day == "Lunedì")
    wednesday = next(day for day in schedule.days if day.day == "Mercoledì")
    thursday = next(day for day in schedule.days if day.day == "Giovedì")
    friday = next(day for day in schedule.days if day.day == "Venerdì")
    sunday = next(day for day in schedule.days if day.day == "Domenica")

    assert planning.week_start == "2026-06-15"
    assert schedule.global_notes == ["PDF pronto per WhatsApp."]
    assert monday.lake_required_ranges == [("07:30", "18:30")]
    assert any(
        assignment.person == GIAMMARCO and assignment.activity == "shop"
        for assignment in wednesday.assignments()
    )
    assert wednesday.lake_required_ranges == [("07:30", "14:00")]
    assert thursday.shop_required_ranges == [("09:00", "12:30")]
    assert friday.day in planning.instruction.lorenzo_absent_days
    assert any("Copertura extra lago" in note for note in sunday.notes)


def test_structured_weekly_planning_json_supports_manual_coverage(tmp_path):
    from orari_agent.weekly_input import load_structured_weekly_planning

    planning_file = tmp_path / "weekly_plan.json"
    planning_file.write_text(
        '{"week_start":"2026-06-15","manual_coverage":[{"day":"sabato","activity":"shop","person":"Giammarco","period":"afternoon","reason":"supporto vendita"}]}',
        encoding="utf-8",
    )

    planning = load_structured_weekly_planning(planning_file)
    saturday_schedule = generate_weekly_schedule(
        planning.instruction, week_start_date=planning.week_start
    )
    saturday = next(day for day in saturday_schedule.days if day.day == "Sabato")

    assert any(
        assignment.person == GIAMMARCO
        and assignment.activity == "shop"
        and assignment.start == "15:30"
        and assignment.end == "19:30"
        for assignment in saturday.assignments()
    )
