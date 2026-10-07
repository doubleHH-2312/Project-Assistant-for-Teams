import logging
import time
from typing import Any

logger = logging.getLogger("project_assistant.teams.bot")


class BotExecutionTrace:
    """Tracks step-by-step execution log of a Teams activity for debugging."""

    def __init__(self, conversation_id: str = "unknown", from_id: str = "unknown") -> None:
        self.conversation_id = conversation_id
        self.from_id = from_id
        self.start_time = time.perf_counter()
        self.logs: list[str] = []

    def log(self, step: str, details: Any = "") -> None:
        elapsed = time.perf_counter() - self.start_time
        detail_str = f": {details}" if details else ""
        msg = f"[{elapsed:0.2f}s] {step}{detail_str}"
        self.logs.append(msg)
        logger.info(
            "[BOT_TRACE] conv=%s user=%s | %s", self.conversation_id[:8], self.from_id[:8], msg
        )

    def log_error(self, step: str, error: Any) -> None:
        elapsed = time.perf_counter() - self.start_time
        msg = f"[{elapsed:0.2f}s] ❌ {step}: {error}"
        self.logs.append(msg)
        logger.error(
            "[BOT_TRACE_ERROR] conv=%s user=%s | %s",
            self.conversation_id[:8],
            self.from_id[:8],
            msg,
        )

    def render_markdown(self) -> str:
        header = "🛠️ **Bot Processing Log:**"
        items = "\n".join(f"- `{line}`" for line in self.logs)
        return f"{header}\n{items}"
