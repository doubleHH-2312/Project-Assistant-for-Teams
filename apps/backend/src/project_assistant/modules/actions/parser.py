import re
from dataclasses import dataclass

_COMMAND = re.compile(r"^/([a-z0-9][a-z0-9-]*)(?:\s+(.*))?$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    arguments: tuple[str, ...]


def parse_command(text: str, bot_mention_text: str | None) -> ParsedCommand | None:
    normalized = text.strip()
    if bot_mention_text:
        mention = bot_mention_text.strip()
        if normalized[: len(mention)].casefold() == mention.casefold():
            remainder = normalized[len(mention) :]
            if not remainder or remainder[0].isspace():
                normalized = remainder.strip()
    match = _COMMAND.fullmatch(normalized)
    if match is None:
        return None
    arguments = tuple(match.group(2).split()) if match.group(2) else ()
    return ParsedCommand(name=match.group(1).lower(), arguments=arguments)
