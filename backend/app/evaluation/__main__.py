"""uv run python -m app.evaluation ml | returns | chatbot [--limit N] [--pause S] | uat"""

import argparse
import sys

from app.core.database import SessionLocal
from app.evaluation import ml_report, report, return_models, uat


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.evaluation")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ml", help="ML models against naive baselines")
    commands.add_parser("returns", help="chance of success under the 4 return models")
    chatbot = commands.add_parser("chatbot", help="question set against the live assistant")
    chatbot.add_argument("--limit", type=int, default=None, help="only the first N questions")
    chatbot.add_argument("--pause", type=float, default=4.0, help="seconds between questions")
    chatbot.add_argument("--ids", default=None, help="only these question ids, e.g. G06,G07")
    chatbot.add_argument("--name", default="chatbot-evaluation", help="report file name")
    commands.add_parser("uat", help="results table from docs/evaluation/uat/responses.csv")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.command == "ml":
            markdown, data = ml_report.build(db)
            path = report.write("ml-evaluation", markdown, data)
        elif args.command == "returns":
            markdown, data = return_models.build(db)
            path = report.write("return-models", markdown, data)
        elif args.command == "uat":
            markdown, data = uat.build()
            path = report.write("uat-results", markdown, data)
        else:
            from app.evaluation import chatbot_eval  # needs the Gemini key

            ids = set(args.ids.split(",")) if args.ids else None
            markdown, data = chatbot_eval.run(db, limit=args.limit, pause=args.pause, ids=ids)
            path = report.write(args.name, markdown, data)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
