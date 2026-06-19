"""Runtime multi-stage: router, tool executor, audit e risposte Telegram."""
from __future__ import annotations

from orari_agent.ai.intent_router import AiIntentRouter
from orari_agent.ai.audit import AiAuditRepository
from orari_agent.ai_tools import AiToolExecutor, ToolExecutionResult

class AgentRuntime:
    def __init__(self, tools: AiToolExecutor, audit: AiAuditRepository | None = None, router: AiIntentRouter | None = None) -> None:
        self.tools = tools
        self.audit = audit
        self.router = router or AiIntentRouter()

    def handle(self, user_id: int, text: str) -> tuple[str, list[ToolExecutionResult]]:
        action = self.router.interpret(text)
        results: list[ToolExecutionResult] = []
        response = action.human_summary
        error = ""
        if action.tool_name and not action.requires_confirmation:
            try:
                results.append(self.tools.execute(action.tool_name, action.tool_arguments))
                if results[-1].message:
                    response = f"{response}\n\n{results[-1].message}"
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                response = f"Ho capito, ma non sono riuscito a completare l'azione: {exc}"
        if self.audit is not None:
            self.audit.add_event(telegram_user_id=user_id, raw_user_text=text, normalized_text=text.strip().lower(), detected_intent=action.intent, confidence=action.confidence, requires_confirmation=action.requires_confirmation, tool_called=action.tool_name or "", tool_arguments=action.tool_arguments, tool_result=results[-1].data if results else {}, bot_response=response, error=error)
        return response, results
