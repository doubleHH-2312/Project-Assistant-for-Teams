from project_assistant.modules.actions.parser import ParsedCommand, parse_command


def test_parse_plain_slash_command() -> None:
    assert parse_command("/daily", None) == ParsedCommand(name="daily", arguments=())


def test_parse_bot_mention_normalizes_case_whitespace_and_arguments() -> None:
    assert parse_command(
        "  @Project Assistant   /WEEKLY-TEAM   team-a   team-b  ",
        "@Project Assistant",
    ) == ParsedCommand(name="weekly-team", arguments=("team-a", "team-b"))


def test_ignore_ordinary_or_other_bot_text() -> None:
    assert parse_command("hello project assistant", None) is None
    assert parse_command("@Other Bot /daily", "@Project Assistant") is None

