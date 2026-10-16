"""Model registry: versioned models in `ml_models`, files under backend/data/models.

Training (offline, `python -m app.ml train`) registers a new version and activates it; serving
(the scoring job and the API) only ever reads the ACTIVE version. Activating swaps the active
flag in one transaction, so readers never see zero or two active versions.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import lightgbm as lgb
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.ml import MLModel

MODELS_DIR = Path(__file__).resolve().parents[2] / "data" / "models"


def next_version(db: Session, name: str) -> int:
    latest = db.scalar(select(func.max(MLModel.version)).where(MLModel.name == name))
    return (latest or 0) + 1


def model_path(name: str, version: int, suffix: str = ".txt") -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / f"{name}-v{version}{suffix}"


def register(
    db: Session,
    *,
    name: str,
    version: int,
    algorithm: str,
    params: dict[str, Any],
    metrics: dict[str, Any],
    data_start: date,
    data_end: date,
    features: list[str] | None = None,
    file_path: Path | None = None,
    activate: bool = True,
) -> MLModel:
    model = MLModel(
        name=name,
        version=version,
        algorithm=algorithm,
        params=params,
        metrics=metrics,
        features=features or [],
        file_path=None if file_path is None else str(file_path),
        data_start=data_start,
        data_end=data_end,
    )
    db.add(model)
    db.flush()
    if activate:
        activate_model(db, model)
    db.commit()
    db.refresh(model)
    return model


def activate_model(db: Session, model: MLModel) -> None:
    """Deactivate the other versions first: the partial unique index allows one active row."""
    db.execute(
        update(MLModel)
        .where(MLModel.name == model.name, MLModel.id != model.id)
        .values(is_active=False)
    )
    db.flush()
    model.is_active = True
    db.flush()


def active(db: Session, name: str) -> MLModel | None:
    return db.scalar(select(MLModel).where(MLModel.name == name, MLModel.is_active))


@lru_cache(maxsize=4)
def load_booster(path: str) -> lgb.Booster:
    """The saved LightGBM model (a text file), loaded once per process."""
    return lgb.Booster(model_file=path)
