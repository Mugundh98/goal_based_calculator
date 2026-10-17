"""Command line: build the knowledge base, or search it.

uv run python -m app.chatbot ingest
uv run python -m app.chatbot search "what is an expense ratio"
"""

import argparse
import sys

from app.chatbot import rag
from app.chatbot.llm import default_llm
from app.core.database import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.chatbot")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest", help="embed new or changed knowledge-base articles")
    search = commands.add_parser("search", help="show the passages closest to a question")
    search.add_argument("question")
    args = parser.parse_args()

    llm = default_llm()
    if llm is None:
        print("GEMINI_API_KEY is not set (backend/.env).", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if args.command == "ingest":
            report = rag.ingest(db, llm)
            print(
                f"added {report.added}, updated {report.updated}, unchanged {report.unchanged}, "
                f"removed {report.removed}; {report.chunks} passages"
            )
        else:
            for p in rag.search(db, llm, args.question):
                print(f"{p.similarity:.3f}  {p.title} - {p.heading}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
