from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.eval.runner import evaluate, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute metrics on a user-provided evaluation set"
    )
    parser.add_argument("dataset", type=Path, help="Directory containing cases.json and the images")
    args = parser.parse_args(argv)
    root = args.dataset.expanduser().resolve()
    try:
        results = evaluate(root)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        print(
            "You can run the bundled set directly: uv run python -m app.eval app/eval/dataset",
            file=sys.stderr,
        )
        return 2
    print(render(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
