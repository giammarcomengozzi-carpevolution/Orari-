"""Layer AI per trasformare messaggi Telegram liberi in tool call sicure."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from orari_agent.ai_tools import AiToolExecutor, DESTRUCTIVE_TOOLS, ToolExecutionResult
from orari_agent.storage.ai_repository import AiConversationRepository

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

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

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
    ) -> None:
        self.responder = responder
        self.tools = tools
        self.repository = repository

    @property
    def configured(self) -> bool:
        return self.responder is not None

    def handle_message(self, user_id: int, text: str) -> AiHandleResult:
        clean_text = text.strip()
        if not self.configured:
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

        return AiHandleResult(
            _compose_results_message(decision.user_message, results), results
        )

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
                "user_message": {"type": "string"},
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
Riassumi sempre i vincoli interpretati dopo un salvataggio.
Business context:
- Gianmarco Mengozzi: titolare/manager/jolly; può coprire negozio o lago, preferisci lago per copertura extra salvo istruzioni diverse.
- Angelo Antonelli: principalmente CarpeEvolution Store.
- Lorenzo Sansavini: principalmente Tenuta del Germano/lago; 40 ore/settimana, 5 giorni, normalmente mercoledì-domenica, lunedì chiuso, martedì riposo preferito.
- Tenuta del Germano: aperta martedì-domenica 07:30-18:30, lunedì chiuso.
- CarpeEvolution Store: aperto martedì-sabato 09:00-12:30 e 15:30-19:30, domenica/lunedì chiuso.
- Calendario moglie: solo M conta; con M Gianmarco non può aprire il lago alle 07:30; dati luglio/agosto mancanti = nessun vincolo.
Tool disponibili: add_weekly_note(text, week_request), list_weekly_notes(week_request), delete_weekly_note(note_id), delete_weekly_notes_for_week(week_request), add_operational_memory(text), list_operational_memory(), generate_schedule(week_request), get_wife_calendar_info(), list_wife_calendar_m_dates(), backup_info(), create_backup().
Azioni distruttive come cancellare tutte le note/reset memoria/reset calendario richiedono conferma: imposta needs_confirmation=true e chiedi “Confermi? Rispondi ‘confermo’.”
""".strip()
