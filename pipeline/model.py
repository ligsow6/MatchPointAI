from dataclasses import dataclass
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from pipeline.features import (
    feature_names,
    loser_perspective,
    symmetric_training_set,
    winner_perspective,
)

MAX_ROUNDS = 6000
EARLY_STOPPING_ROUNDS = 150
BASE_PARAMETERS: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "verbosity": -1,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 4,
    "bagging_freq": 1,
}
DATASET_PARAMETERS: dict[str, Any] = {"feature_pre_filter": False, "verbosity": -1}
SEARCH_SPACE: dict[str, tuple[float | int, ...]] = {
    "learning_rate": (0.03, 0.05, 0.08),
    "num_leaves": (7, 15, 31, 63),
    "min_data_in_leaf": (50, 100, 200, 400, 800),
    "feature_fraction": (0.5, 0.7, 0.9),
    "bagging_fraction": (0.7, 0.85, 1.0),
    "lambda_l2": (0.0, 1.0, 5.0, 20.0),
}


@dataclass(frozen=True)
class TrainedModel:
    booster: lgb.Booster
    parameters: dict[str, Any]
    rounds: int
    validation_log_loss: float


@dataclass(frozen=True)
class Trial:
    parameters: dict[str, Any]
    rounds: int
    validation_log_loss: float


def sample_configurations(count: int, seed: int) -> list[dict[str, Any]]:
    generator = np.random.default_rng(seed)
    configurations: list[dict[str, Any]] = []
    seen: set[tuple[float | int, ...]] = set()
    while len(configurations) < count:
        choice = {
            name: values[generator.integers(len(values))] for name, values in SEARCH_SPACE.items()
        }
        signature = tuple(choice.values())
        if signature in seen:
            continue
        seen.add(signature)
        configurations.append({name: to_python(value) for name, value in choice.items()})
    return configurations


def to_python(value: float | int) -> float | int:
    return value.item() if isinstance(value, np.generic) else value


def build_datasets(
    train: pd.DataFrame, validation: pd.DataFrame
) -> tuple[lgb.Dataset, lgb.Dataset]:
    train_features, train_labels = symmetric_training_set(train)
    validation_features, validation_labels = symmetric_training_set(validation)
    training_set = lgb.Dataset(
        train_features, label=train_labels, params=DATASET_PARAMETERS, free_raw_data=False
    )
    validation_set = lgb.Dataset(
        validation_features,
        label=validation_labels,
        reference=training_set,
        params=DATASET_PARAMETERS,
        free_raw_data=False,
    )
    return training_set, validation_set


def train_with_early_stopping(
    parameters: dict[str, Any], training: lgb.Dataset, validation: lgb.Dataset, seed: int
) -> TrainedModel:
    merged = {**BASE_PARAMETERS, **parameters, "seed": seed}
    evaluation: dict[str, dict[str, list[float]]] = {}
    booster = lgb.train(
        merged,
        training,
        num_boost_round=MAX_ROUNDS,
        valid_sets=[validation],
        valid_names=["validation"],
        callbacks=[
            lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
            lgb.record_evaluation(evaluation),
        ],
    )
    rounds = int(booster.best_iteration)
    losses = evaluation["validation"]["binary_logloss"]
    return TrainedModel(booster, parameters, rounds, float(losses[rounds - 1]))


def search_hyperparameters(
    train: pd.DataFrame, validation: pd.DataFrame, trials: int, seed: int
) -> tuple[TrainedModel, list[Trial]]:
    """Recherche aléatoire : entraînement sur le passé, sélection sur la période suivante."""
    training_set, validation_set = build_datasets(train, validation)
    history: list[Trial] = []
    best: TrainedModel | None = None
    for configuration in sample_configurations(trials, seed):
        candidate = train_with_early_stopping(configuration, training_set, validation_set, seed)
        history.append(Trial(configuration, candidate.rounds, candidate.validation_log_loss))
        if best is None or candidate.validation_log_loss < best.validation_log_loss:
            best = candidate
    if best is None:
        raise ValueError("Aucune configuration évaluée")
    return best, history


def predict_winner_probability(model: TrainedModel, matches: pd.DataFrame) -> np.ndarray:
    """Probabilité de victoire du vainqueur réel, symétrisée : (p(A, B) + 1 - p(B, A)) / 2."""
    as_winner = np.asarray(
        model.booster.predict(winner_perspective(matches), num_iteration=model.rounds)
    )
    as_loser = np.asarray(
        model.booster.predict(loser_perspective(matches), num_iteration=model.rounds)
    )
    return np.asarray(0.5 * (as_winner + 1.0 - as_loser), dtype=float)


def feature_importance(model: TrainedModel) -> pd.Series:
    gains = model.booster.feature_importance(importance_type="gain", iteration=model.rounds)
    importance = pd.Series(gains, index=feature_names(), dtype=float)
    return (importance / importance.sum()).sort_values(ascending=False)
