from __future__ import annotations

import argparse
import json
from pathlib import Path

from project_assistant.main import app

OUTPUT = Path("docs/api/openapi.json")


def rendered_schema() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the canonical OpenAPI contract")
    parser.add_argument("--check", action="store_true", help="fail when the file has drifted")
    args = parser.parse_args()
    rendered = rendered_schema()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print("OpenAPI drift detected. Run: make openapi")
            return 1
        print(f"OpenAPI contract is current: {OUTPUT}")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
