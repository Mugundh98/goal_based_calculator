"""Command line for the ML models.

uv run python -m app.ml train all          # train, validate, register, activate, then score
uv run python -m app.ml train ranker       # or clusters / inflation
uv run python -m app.ml score              # score the latest month with the active models
"""

import argparse
import logging

from app.core.database import SessionLocal
from app.ml import dataset, train

MODELS = ("ranker", "clusters", "inflation")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.ml")
    commands = parser.add_subparsers(dest="command", required=True)
    train_parser = commands.add_parser("train", help="train and activate new model versions")
    train_parser.add_argument("model", choices=[*MODELS, "all"])
    commands.add_parser("score", help="re-score with the active models")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with SessionLocal() as db:
        if args.command == "train":
            chosen = MODELS if args.model == "all" else (args.model,)
            data = dataset.load(db) if {"ranker", "clusters"} & set(chosen) else None
            if "ranker" in chosen:
                train.train_ranker(db, data)
            if "clusters" in chosen:
                train.train_clusters(db, data)
            if "inflation" in chosen:
                train.train_inflation(db)
            if data is not None:
                logging.info("scored: %s", train.score(db, data))
        else:
            logging.info("scored: %s", train.score(db))


if __name__ == "__main__":
    main()
