"""Layer AI per trasformare messaggi Telegram liberi in tool call sicure."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from orari_agent.ai_tools import AiToolExecutor, DESTRUCTIVE_TOOLS, ToolExecutionResult
from orari_agent.storage.ai_repository import AiConversationRepository
from orari_agent.ai.audit import AiAuditRepository
from orari_agent.ai.agent_runtime import AgentRuntime

LOGGER = logging.getLogger(__name__)
MISSING_AI_KEY_MESSAGE = "Modalità AI non configurata: manca OPENAI_API_KEY."
CONFIRMATION_MESSAGE = "Confermi? Rispondi ‘confermo’."


@dataclass(frozen=True)
class AiToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AiDecision:
    user_message: str
    action: str | None
    tool_calls: list[AiToolCall]
    needs_confirmation: bool
    confidence: str


@dataclass(frozen=True)
class AiHandleResult:
    user_message: str
    tool_results: list[ToolExecutionResult] = field(default_factory=list)
    invalid_json: bool = False


class OpenAiResponder(Protocol):
    def respond(self, user_message: str) -> str:
        """Ritorna JSON strutturato per il messaggio utente."""


class OpenAiResponsesClient:
    """Wrapper isolato dell'SDK OpenAI Responses API, facile da mockare nei test."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", reasoning_effort: str | None = None) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.reasoning_effort = reasoning_effort

    def respond(self, user_message: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_message},
            ],
            text={"format": _response_json_schema()},
        )
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text
        # Fallback difensivo per SDK/risposte con shape diversa.
        return str(response)


class AiAgent:
    """Orchestra OpenAI, conferme e tool deterministici."""

    def __init__(
        self,
        responder: OpenAiResponder | None,
        tools: AiToolExecutor,
        repository: AiConversationRepository,
        audit_repository: AiAuditRepository | None = None,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self.responder = responder
        self.tools = tools
        self.repository = repository
        self.audit_repository = audit_repository
        self.runtime = runtime or AgentRuntime(tools, audit_repository)

    @property
    def configured(self) -> bool:
        return self.responder is not None

    def handle_message(self, user_id: int, text: str) -> AiHandleResult:
        clean_text = text.strip()
        if not self.configured and not hasattr(self.tools, "execute"):
            return AiHandleResult(MISSING_AI_KEY_MESSAGE)

        pending = self.repository.get_pending_action(user_id)
        if pending is not None:
            if clean_text.lower() == "confermo":
                try:
                    results = self._execute_tool_calls(
                        pending.payload.get("tool_calls", [])
                    )
                except Exception as exc:  # noqa: BLE001 - errore sicuro lato chat
                    LOGGER.exception("Errore esecuzione azione AI confermata")
                    self.repository.clear_pending_action(user_id)
                    return AiHandleResult(
                        f"Non sono riuscito a eseguire l'azione confermata: {exc}"
                    )
                self.repository.clear_pending_action(user_id)
                return AiHandleResult(
                    _compose_results_message("Azione confermata ed eseguita.", results),
                    results,
                )
            return AiHandleResult(CONFIRMATION_MESSAGE)

        action = self.runtime.interpret(clean_text)
        if self.runtime.can_handle(action):
            if action.requires_confirmation and action.tool_name and self.runtime.is_destructive(action):
                self.repository.save_pending_action(
                    user_id,
                    action.intent,
                    {"tool_calls": [{"name": action.tool_name, "arguments": action.tool_arguments}], "original_message": clean_text},
                )
                return AiHandleResult(action.human_summary)
            runtime_result = self.runtime.handle_action(user_id, clean_text, action)
            return AiHandleResult(runtime_result.message, runtime_result.tool_results)

        if not self.configured:
            return AiHandleResult(MISSING_AI_KEY_MESSAGE)

        assert self.responder is not None
        try:
            raw_response = self.responder.respond(clean_text)
            decision = parse_ai_decision(raw_response)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            LOGGER.exception("Risposta AI non valida: %s", exc)
            return AiHandleResult(
                "Non sono riuscito a interpretare in modo sicuro la risposta AI. Non ho eseguito nessuna azione.",
                invalid_json=True,
            )

        tool_calls_payload = [
            {"name": call.name, "arguments": call.arguments}
            for call in decision.tool_calls
        ]
        if self._requires_confirmation(decision):
            self.repository.save_pending_action(
                user_id,
                decision.action or "ai_tool_calls",
                {"tool_calls": tool_calls_payload, "original_message": clean_text},
            )
            prefix = decision.user_message.strip()
            message = (
                f"{prefix}\n{CONFIRMATION_MESSAGE}" if prefix else CONFIRMATION_MESSAGE
            )
            return AiHandleResult(message)

        try:
            results = self._execute_tool_calls(tool_calls_payload)
        except Exception as exc:  # noqa: BLE001 - errore sicuro lato chat
            LOGGER.exception("Errore esecuzione tool AI")
            return AiHandleResult(
                f"Ho capito la richiesta, ma non sono riuscito a completarla: {exc}"
            )

        final_message = _compose_results_message(
            _safe_user_message_for_results(
                clean_text, decision.user_message, tool_calls_payload
            ),
            results,
        )
        self._audit(user_id, clean_text, decision, tool_calls_payload, results, final_message)
        return AiHandleResult(final_message, results)

    def _requires_confirmation(self, decision: AiDecision) -> bool:
        if decision.needs_confirmation:
            return True
        return any(call.name in DESTRUCTIVE_TOOLS for call in decision.tool_calls)

    def _execute_tool_calls(
        self, calls: list[dict[str, Any]]
    ) -> list[ToolExecutionResult]:
        results: list[ToolExecutionResult] = []
        for call in calls:
            name = str(call.get("name", ""))
            arguments = call.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ValueError(f"Argomenti non validi per {name}")
            results.append(self.tools.execute(name, arguments))
        return results


    def _audit(
        self,
        user_id: int,
        text: str,
        decision: AiDecision,
        tool_calls_payload: list[dict[str, Any]],
        results: list[ToolExecutionResult],
        bot_response: str,
    ) -> None:
        if self.audit_repository is None:
            return
        first_call = tool_calls_payload[0] if tool_calls_payload else {}
        first_result = results[0].data if results else {}
        try:
            self.audit_repository.add_event(
                telegram_user_id=user_id,
                raw_user_text=text,
                normalized_text=text.lower(),
                detected_intent=decision.action or "unknown",
                confidence=decision.confidence,
                requires_confirmation=self._requires_confirmation(decision),
                tool_called=str(first_call.get("name", "")),
                tool_arguments=first_call.get("arguments", {}) if isinstance(first_call.get("arguments", {}), dict) else {},
                tool_result=first_result,
                bot_response=bot_response,
            )
        except Exception:  # noqa: BLE001 - audit non deve rompere il bot
            LOGGER.exception("Errore salvataggio audit AI")

def parse_ai_decision(raw_json: str) -> AiDecision:
    payload = json.loads(raw_json)
    if not isinstance(payload, dict):
        raise ValueError("La risposta AI non è un oggetto JSON.")
    raw_calls = payload.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raise ValueError("tool_calls deve essere una lista.")
    calls: list[AiToolCall] = []
    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            raise ValueError("Tool call non valida.")
        name = str(raw_call.get("name") or raw_call.get("tool") or "").strip()
        if not name:
            raise ValueError("Nome tool mancante.")
        arguments = raw_call.get("arguments") or raw_call.get("args") or {}
        if not isinstance(arguments, dict):
            raise ValueError("Argomenti tool non validi.")
        calls.append(AiToolCall(name, arguments))
    confidence = str(payload.get("confidence", "low")).lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return AiDecision(
        user_message=str(payload.get("user_message", "")).strip(),
        action=str(payload["action"]).strip() if payload.get("action") else None,
        tool_calls=calls,
        needs_confirmation=bool(payload.get("needs_confirmation", False)),
        confidence=confidence,
    )


def _safe_user_message_for_results(
    original_message: str,
    user_message: str,
    tool_calls: list[dict[str, Any]],
) -> str:
    """Evita riepiloghi incoerenti quando il testo in prima persona è stato parsato."""

    if not _has_first_person_reference(original_message):
        return user_message

    weekly_note_texts = [
        str((call.get("arguments") or {}).get("text", "")).strip()
        for call in tool_calls
        if call.get("name") == "add_weekly_note"
        and isinstance(call.get("arguments"), dict)
    ]
    if not weekly_note_texts:
        return user_message

    has_gianmarco_constraint = any(
        re.search(r"\b(?:gianmarco|giammarco|mengozzi)\b", text, re.IGNORECASE)
        for text in weekly_note_texts
    )
    if not has_gianmarco_constraint:
        return user_message

    if not re.search(r"\blorenzo\b", user_message, re.IGNORECASE):
        return user_message

    lines = ["Ho interpretato e salvo questi vincoli separati:"]
    lines.extend(f"- {text}" for text in weekly_note_texts if text)
    return "\n".join(lines)


def _has_first_person_reference(text: str) -> bool:
    normalized = text.lower().replace("’", "'")
    return any(
        re.search(pattern, normalized)
        for pattern in (
            r"\bio\b",
            r"\bsono\b",
            r"\bsaro\b",
            r"\bsarò\b",
            r"\bdevo\b",
            r"\bvado\b",
            r"\bnon\s+ci\s+sono\b",
        )
    )


def _compose_results_message(
    user_message: str, results: list[ToolExecutionResult]
) -> str:
    parts = [user_message.strip()] if user_message.strip() else []
    parts.extend(result.message for result in results if result.message.strip())
    return "\n\n".join(parts) if parts else "Fatto."


def _response_json_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "orari_agent_decision",
        "strict": False,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "user_message": {
                    "type": "string",
                    "description": "Breve riepilogo in italiano dei vincoli interpretati. Deve usare la stessa persona indicata negli arguments.text delle tool call; i riferimenti in prima persona dell'utente autorizzato sono sempre Gianmarco Mengozzi.",
                },
                "action": {"type": ["string", "null"]},
                "tool_calls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "arguments": {
                                "type": "object",
                                "additionalProperties": True,
                                "description": "Per add_weekly_note, text deve contenere un solo vincolo atomico con persona esplicita quando nota (es. Gianmarco Mengozzi, Lorenzo Sansavini, Angelo Antonelli) e week_request separato.",
                            },
                        },
                        "required": ["name", "arguments"],
                    },
                },
                "needs_confirmation": {"type": "boolean"},
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                },
            },
            "required": [
                "user_message",
                "action",
                "tool_calls",
                "needs_confirmation",
                "confidence",
            ],
        },
    }


def _system_prompt() -> str:
    return """
Sei l'assistente AI privato di Gianmarco per gli orari di CarpeEvolution Store e Tenuta del Germano.
Rispondi esclusivamente con JSON valido con queste chiavi: user_message, action, tool_calls, needs_confirmation, confidence.
Non inventare dati salvati: usa list_* se devi consultare dati. Se non sei sicuro, fai una domanda e non chiamare tool.
Riassumi sempre i vincoli interpretati dopo un salvataggio e assicurati che user_message sia coerente con la persona salvata in ogni tool_call.
Regola identità fondamentale:
- I messaggi in prima persona dell'utente Telegram autorizzato si riferiscono sempre a Gianmarco Mengozzi.
- Frasi come “sono dal commercialista”, “io sono in negozio”, “devo andare in banca” e “non ci sono” sono vincoli di Gianmarco Mengozzi, non di Lorenzo o Angelo.
- Solo nomi espliciti sovrascrivono questa regola: “Lorenzo esce alle 15” è Lorenzo Sansavini; “Angelo non c’è venerdì mattina” è Angelo Antonelli.
- Se un messaggio contiene più vincoli per persone diverse, crea tool call add_weekly_note separate (una nota atomica per vincolo/persona) o sotto-note chiaramente separate; non mescolare mai la persona nel riepilogo.
Business context:
- Gianmarco Mengozzi: titolare/manager/jolly; può coprire negozio o lago, preferisci lago per copertura extra salvo istruzioni diverse.
- Angelo Antonelli: principalmente CarpeEvolution Store.
- Lorenzo Sansavini: principalmente Tenuta del Germano/lago; 40 ore/settimana è un target da monitorare, non un blocco. Può lavorare meno, esattamente o più di 40 ore, anche oltre 8 ore al giorno, se serve. Normalmente 5 giorni, mercoledì-domenica, lunedì chiuso, martedì riposo preferito.
- Tenuta del Germano: aperta martedì-domenica 07:30-18:30, lunedì chiuso. Il PDF finale deve mostrare turni reali persona -> sede -> orario -> pausa -> compito, non blocchi generici tipo lago mattina/pomeriggio.
- Regola stagionale Tenuta del Germano: dal 2026-06-22 al 2026-09-30 incluso, ogni venerdì e domenica il lago resta aperto fino alle 23:00 per eventi serali (aperitivi, cene, eventi dedicati) e serve copertura lago 18:30-23:00. Il venerdì Gianmarco e Lorenzo sono la copertura primaria lago; Angelo resta in negozio fino alle 19:30 e poi può supportare il lago, normalmente 20:00-22:00 oppure 19:30-23:00/20:00-23:00 se richiesto. La domenica negozio chiuso: Gianmarco, Angelo e Lorenzo possono essere tutti al lago con turni scaglionati. Frasi come “venerdì sera evento al lago”, “domenica sera aperitivo”, “cena al lago”, “tieni aperto fino alle 23”, “Angelo finito il negozio viene al lago”, “Domenica Angelo può arrivare alle 11 e chiudere” riguardano questa apertura serale. Se l'utente assegna una persona specifica per la sera, salva una nota atomica con quella persona e la copertura lago indicata (es. 20:00-22:00 per “Angelo dopo il negozio”, 18:30-23:00 o fascia esplicita per chiusura).
- CarpeEvolution Store: aperto martedì-sabato 09:00-12:30 e 15:30-19:30, domenica/lunedì chiuso. Se l'utente autorizza straordinario Lorenzo (es. “Lorenzo può fare straordinario/superare 40 ore/lavorare 12 ore”), salva una nota operativa tipo “Straordinario Lorenzo autorizzato”; non trattare lo straordinario come impossibile se questa frase manca.
- Calendario moglie: solo M conta; con M Gianmarco non può aprire il lago alle 07:30; dati luglio/agosto mancanti = nessun vincolo.
Tool disponibili: add_weekly_note(text, week_request), list_weekly_notes(week_request), delete_weekly_note(note_id), delete_weekly_notes_for_week(week_request), add_operational_memory(text), list_operational_memory(), generate_schedule(week_request), get_wife_calendar_info(), list_wife_calendar_m_dates(), backup_info(), create_backup().
Azioni distruttive come cancellare tutte le note/reset memoria/reset calendario richiedono conferma: imposta needs_confirmation=true e chiedi “Confermi? Rispondi ‘confermo’.”
""".strip()
