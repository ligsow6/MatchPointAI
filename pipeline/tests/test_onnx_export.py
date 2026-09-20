from dataclasses import replace
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from pipeline import onnx_export
from pipeline.data import clean_matches
from pipeline.elo import attach_elo
from pipeline.features import attach_player_features, loser_perspective, winner_perspective
from pipeline.model import TrainedModel, build_datasets, train_with_early_stopping
from pipeline.onnx_export import (
    PARITY_TOLERANCE,
    OnnxParityError,
    check_parity,
    convert,
    export_onnx,
    onnx_probabilities,
    trimmed_booster,
)
from pipeline.tests.factories import synthetic_history

PARAMETERS = {
    "learning_rate": 0.1,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 1.0,
    "lambda_l2": 1.0,
}


@pytest.fixture(scope="module")
def trained() -> tuple[TrainedModel, np.ndarray]:
    history = attach_player_features(
        attach_elo(clean_matches(synthetic_history(players=40, tournaments=300, seed=9)))
    )
    middle, end = int(len(history) * 0.7), int(len(history) * 0.85)
    training, validation = build_datasets(history.iloc[:middle], history.iloc[middle:end])
    model = train_with_early_stopping(PARAMETERS, training, validation, seed=3)
    sample = pd.concat([history.iloc[:300], history.iloc[end:]])
    features = pd.concat([winner_perspective(sample), loser_perspective(sample)])
    return model, features.to_numpy(dtype=float)


def test_onnx_matches_lightgbm_within_tolerance(trained: tuple[TrainedModel, np.ndarray]) -> None:
    model, features = trained
    booster = trimmed_booster(model)
    converted = convert(booster)
    assert np.isnan(features).any()
    difference = np.max(np.abs(onnx_probabilities(converted, features) - booster.predict(features)))
    assert difference <= PARITY_TOLERANCE


def test_export_writes_verified_model(
    trained: tuple[TrainedModel, np.ndarray], tmp_path: Path
) -> None:
    model, features = trained
    report = export_onnx(model, features, tmp_path / "model.onnx")
    assert report.path.exists()
    assert report.size_bytes == report.path.stat().st_size
    assert report.rows == len(features)
    assert report.max_difference <= PARITY_TOLERANCE
    assert report.rewritten is True


def test_an_equivalent_model_is_not_republished(
    trained: tuple[TrainedModel, np.ndarray], tmp_path: Path
) -> None:
    model, features = trained
    target = tmp_path / "model.onnx"
    export_onnx(model, features, target)
    stamp = target.stat().st_mtime_ns
    again = export_onnx(model, features, target)
    assert again.rewritten is False
    assert target.stat().st_mtime_ns == stamp


def test_a_different_model_is_republished(
    trained: tuple[TrainedModel, np.ndarray], tmp_path: Path
) -> None:
    model, features = trained
    target = tmp_path / "model.onnx"
    export_onnx(model, features, target)
    shorter = replace(model, rounds=max(model.rounds // 2, 1))
    assert export_onnx(shorter, features, target).rewritten is True


def test_parity_check_rejects_a_different_model(trained: tuple[TrainedModel, np.ndarray]) -> None:
    model, features = trained
    converted = convert(trimmed_booster(model))
    rng = np.random.default_rng(1)
    labels = rng.integers(0, 2, len(features))
    other = lgb.train(
        {"objective": "binary", "verbosity": -1, "num_leaves": 7},
        lgb.Dataset(np.nan_to_num(features), labels),
        num_boost_round=20,
    )
    with pytest.raises(OnnxParityError, match="Écart"):
        check_parity(converted, other, features)


def test_conversion_rejects_mismatched_trees(trained: tuple[TrainedModel, np.ndarray]) -> None:
    model, features = trained
    booster = trimmed_booster(model)
    rng = np.random.default_rng(2)
    other = lgb.train(
        {"objective": "binary", "verbosity": -1, "num_leaves": 15},
        lgb.Dataset(np.nan_to_num(features), rng.integers(0, 2, len(features))),
        num_boost_round=booster.num_trees(),
    )
    converted = onnx_export.float_conversion(booster)
    with pytest.raises(OnnxParityError, match="ne correspond pas"):
        onnx_export.promote_to_double(converted, other)
