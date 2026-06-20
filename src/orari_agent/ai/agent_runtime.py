"""Runtime multi-stage: router, tool executor, audit e risposte Telegram."""
from __future__ import annotations

from dataclasses import dataclass

from orari_agent.ai.intent_router import AiIntentRouter
from orari_agent.ai.audit import AiAuditRepository
from orari_agent.ai.schemas import InterpretedAction
from orari_agent.ai.context_loader import AgentContextLoader, AgentContext
from orari_agent.ai_tools import AiToolExecutor, ToolExecutionResult, DESTRUCTIVE_TOOLS


@dataclass(frozen=True)
class AgentRuntimeResult:
    message: str
    tool_results: list[ToolExecutionResult]
    action: InterpretedAction
    handled: bool


class AgentRuntime:
    """Esegue il percorso deterministico strutturato prima dell'eventuale fallback OpenAI."""

    def __init__(
        self,
        tools: AiToolExecutor,
        audit: AiAuditRepository | None = None,
        router: AiIntentRouter | None = None,
    ) -> None:
        self.tools = tools
        self.audit = audit
        self.router = router or AiIntentRouter()
        self.context_loader = AgentContextLoader(tools)

    def can_handle(self, action: InterpretedAction) -> bool:
        return action.intent != "unknown"

    def load_context(self) -> AgentContext:
        return self.context_loader.load()

    def interpret(self, text: str) -> InterpretedAction:
        # Il contesto viene caricato prima del routing per rendere il runtime
        # realmente multi-stage anche nei casi deterministici.
        self.load_context()
        return self.router.interpret(text)

    def handle_action(self, user_id: int, text: str, action: InterpretedAction) -> AgentRuntimeResult:
        context = self.load_context()
        if action.requires_confirmation or not action.tool_name:
            self._audit(user_id, text, action, {"context": context.to_dict()}, {}, action.human_summary)
            return AgentRuntimeResult(action.human_summary, [], action, True)

        results: list[ToolExecutionResult] = []
        response = action.human_summary
        error = ""
        try:
            result = self.tools.execute(action.tool_name, action.tool_arguments)
            results.append(result)
            if result.message:
                response = f"{response}\n\n{result.message}"
        except Exception as exc:  # noqa: BLE001 - errore sicuro lato chat
            error = str(exc)
            response = f"Ho capito, ma non sono riuscito a completare l'azione: {exc}"
        self._audit(
            user_id,
            text,
            action,
            {**action.tool_arguments, "context": context.to_dict()},
            results[-1].data if results else {},
            response,
            error,
        )
        return AgentRuntimeResult(response, results, action, True)

    def is_destructive(self, action: InterpretedAction) -> bool:
        return bool(action.tool_name and action.tool_name in DESTRUCTIVE_TOOLS)

    def _audit(
        self,
        user_id: int,
        text: str,
        action: InterpretedAction,
        tool_arguments: dict,
        tool_result: dict,
        bot_response: str,
        error: str = "",
    ) -> None:
        if self.audit is None:
            return
        self.audit.add_event(
            telegram_user_id=user_id,
            raw_user_text=text,
            normalized_text=text.strip().lower(),
            detected_intent=action.intent,
            confidence=action.confidence,
            requires_confirmation=action.requires_confirmation,
            tool_called=action.tool_name or "",
            tool_arguments=tool_arguments,
            tool_result=tool_result,
            bot_response=bot_response,
            error=error,
        )
