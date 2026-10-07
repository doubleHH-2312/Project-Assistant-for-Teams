from project_assistant.integrations.teams.logger import BotExecutionTrace


def test_bot_execution_trace_logs_and_renders_markdown() -> None:
    trace = BotExecutionTrace(conversation_id="conv-123", from_id="user-456")
    trace.log("Step 1", "Started processing")
    trace.log("Step 2", "Context resolved")
    trace.log_error("Step 3", "Test error message")

    assert len(trace.logs) == 3
    markdown = trace.render_markdown()

    assert "🛠️ **Bot Processing Log:**" in markdown
    assert "Step 1: Started processing" in markdown
    assert "Step 2: Context resolved" in markdown
    assert "❌ Step 3: Test error message" in markdown
