"""Router deterministico/strutturato per italiano operativo comune."""
from __future__ import annotations

import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from orari_agent.ai.schemas import InterpretedAction

PEOPLE = {
    "angelo": "Angelo Antonelli",
    "lorenzo": "Lorenzo Sansavini",
    "gianmarco": "Giammarco Mengozzi",
    "giammarco": "Giammarco Mengozzi",
    "io": "Giammarco Mengozzi",
    "me": "Giammarco Mengozzi",
}

class AiIntentRouter:
    """Interpreta frasi naturali frequenti in azioni strutturate e sicure."""

    def __init__(self, today: date | None = None) -> None:
        self.today = today or date.today()

    def interpret(self, text: str) -> InterpretedAction:
        raw = text.strip()
        lower = raw.lower().replace("’", "'")
        if not lower:
            return InterpretedAction("unknown", "low", False, human_summary="Messaggio vuoto.")
        if re.search(r"\b(lui|lei)\b", lower):
            return InterpretedAction(
                "clarification_required", "low", True, location=_location(lower),
                human_summary="Chi intendi? Angelo, Lorenzo o Gianmarco?",
            )
        if any(w in lower for w in ("che note", "note hai usato", "quali note")):
            return InterpretedAction("explain_schedule", "high", False, tool_name="explain_last_schedule", tool_arguments={"question": raw}, human_summary="Controllo le note usate nell'ultimo orario.")
        if any(w in lower for w in ("perché", "perche", "chi chiude", "problemi", "non ti torna", "ultimo orario")):
            return InterpretedAction("ask_schedule_question", "high", False, tool_name="explain_last_schedule", tool_arguments={"question": raw}, human_summary="Controllo l'ultimo orario generato.")
        if "memori" in lower or lower.startswith(("ricordati", "da adesso", "sempre", "da luglio")):
            return InterpretedAction("save_memory", "high", False, scope="persistent", tool_name="add_operational_memory", tool_arguments={"text": raw}, human_summary=f"Ok, salvo memoria operativa: {raw}")
        if any(w in lower for w in ("genera", "generami", "orario")):
            week_request = _week_request(lower)
            return InterpretedAction("generate_schedule", "high", False, week_request=week_request, tool_name="generate_schedule", tool_arguments={"week_request": week_request}, human_summary=f"Genero l'orario {week_request or 'della settimana richiesta'}." )
        if lower.startswith(("cancella", "elimina", "rimuovi")):
            return InterpretedAction("delete_constraint", "medium", True, human_summary="Per cancellare un vincolo serve conferma.")
        if any(day in lower for day in _DAYS) or any(word in lower for word in ("oggi", "domani", "dopodomani")):
            return self._constraint(raw, lower)
        return InterpretedAction("unknown", "low", False, human_summary="Non ho capito abbastanza bene: puoi riformulare?")

    def _constraint(self, raw: str, lower: str) -> InterpretedAction:
        person = _person(lower)
        if person is None and re.search(r"\b(viene|va|andare|venire)\b", lower):
            return InterpretedAction("clarification_required", "low", True, location=_location(lower), human_summary="Mi manca una cosa: chi deve andare al lago o essere assegnato?")
        resolved_date = _resolve_date(lower, self.today)
        location = _location(lower)
        start, end = _times(lower)
        ctype = _constraint_type(lower, location)
        text = _normalized_note(raw, person, location, start, end, ctype)
        week_request = _week_request(lower) or "settimana prossima"
        summary = f"Ok, salvo vincolo settimanale: {text}."
        return InterpretedAction("save_constraint", "high", False, person=person, date=resolved_date, start_time=start, end_time=end, location=location, constraint_type=ctype, scope="weekly", week_request=week_request, human_summary=summary, tool_name="add_weekly_note", tool_arguments={"text": text, "week_request": week_request})

_DAYS = ["lunedì","lunedi","martedì","martedi","mercoledì","mercoledi","giovedì","giovedi","venerdì","venerdi","sabato","domenica"]
_DAY_INDEX = {d:i for i, names in enumerate([["lunedì","lunedi"],["martedì","martedi"],["mercoledì","mercoledi"],["giovedì","giovedi"],["venerdì","venerdi"],["sabato"],["domenica"]]) for d in names}

def _person(text: str) -> str | None:
    if re.search(r"\b(io|me|sono|devo|vado)\b", text):
        return "Giammarco Mengozzi"
    for key, value in PEOPLE.items():
        if re.search(rf"\b{key}\b", text):
            return value
    return None

def _location(text: str) -> str | None:
    if "lago" in text or "tenuta" in text:
        return "Tenuta del Germano"
    if "negozio" in text or "store" in text or "carp" in text:
        return "CarpEvolution Store"
    return None

def _constraint_type(text: str, location: str | None) -> str:
    if any(w in text for w in ("commercialista", "metro", "spesa", "banca")):
        return "external_work"
    if any(w in text for w in ("lascialo a casa", "non c", "esce", "assente")):
        return "unavailable"
    if location == "Tenuta del Germano":
        return "lake_support"
    if location == "CarpEvolution Store":
        return "shop_assignment"
    return "generic_constraint"

def _times(text: str) -> tuple[str | None, str | None]:
    if "dopo il negozio" in text and "angelo" in text:
        if re.search(r"fino (?:alle|a)\s*23", text):
            return "19:30", "23:00"
        return "20:00", "22:00"
    m = re.search(r"(?:dalle|da)\s*(\d{1,2})(?::(\d{2}))?\s*(?:alle|a|-)\s*(\d{1,2})(?::(\d{2}))?", text)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2) or '00'}", f"{int(m.group(3)):02d}:{m.group(4) or '00'}"
    m = re.search(r"fino (?:alle|a)\s*(\d{1,2})(?::(\d{2}))?", text)
    if m:
        return None, f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return None, None

def _week_request(text: str) -> str:
    if "settimana prossima" in text or "prossima settimana" in text:
        return "settimana prossima"
    if "questa settimana" in text:
        return "questa settimana"
    if "dal " in text and " al " in text:
        return text
    return ""

def _resolve_date(text: str, today: date) -> str | None:
    if "oggi" in text: return today.isoformat()
    if "domani" in text and "dopodomani" not in text: return (today + timedelta(days=1)).isoformat()
    if "dopodomani" in text: return (today + timedelta(days=2)).isoformat()
    for day, idx in _DAY_INDEX.items():
        if day in text:
            days_ahead = (idx - today.weekday()) % 7
            if days_ahead == 0 or "prossim" in text:
                days_ahead = 7 if "prossim" in text else 0
            return (today + timedelta(days=days_ahead)).isoformat()
    return None

def _normalized_note(raw: str, person: str | None, location: str | None, start: str | None, end: str | None, ctype: str) -> str:
    parts = []
    if person: parts.append(person)
    parts.append(raw)
    if location and location.lower() not in raw.lower(): parts.append(location)
    if ctype == "lake_support" and person == "Angelo Antonelli" and "dopo il negozio" in raw.lower():
        parts.append("copre il negozio 09:00-12:30 / 15:30-19:30 poi supporta il lago")
    if start or end: parts.append(f"{start or '?'}-{end or '?'}")
    return " | ".join(parts)
