import numpy as np
import pandas as pd
import pytest

from pipeline.calibration import choose_calibration, isotonic, platt
from pipeline.data import clean_matches
from pipeline.elo import attach_elo
from pipeline.features import attach_player_features
from pipeline.metrics import score
from pipeline.model import (
    SEARCH_SPACE,
    feature_importance,
    predict_winner_probability,
    sample_configurations,
    search_hyperparameters,
)
from pipeline.tests.factories import synthetic_history

PLAYER_COLUMNS = ("id", "name", "hand", "ht", "age", "rank", "rank_points")
SIDE_SUFFIXES = (
    "elo",
    "elo_played",
    "surface_elo",
    "surface_played",
    "form_short",
    "form_long",
    "surface_form_short",
    "surface_form_long",
    "rest_days",
    "tourney_matches",
    "serve_won",
    "return_won",
    "h2h_wins",
)


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    raw = synthetic_history(players=40, tournaments=360, seed=5)
    return attach_player_features(attach_elo(clean_matches(raw)))


def swapped(matches: pd.DataFrame) -> pd.DataFrame:
    mirror = matches.copy()
    for column in PLAYER_COLUMNS:
        mirror[f"winner_{column}"] = matches[f"loser_{column}"]
        mirror[f"loser_{column}"] = matches[f"winner_{column}"]
    for column in SIDE_SUFFIXES:
        mirror[f"{column}_w"] = matches[f"{column}_l"]
        mirror[f"{column}_l"] = matches[f"{column}_w"]
    return mirror


def test_sample_configurations_are_unique_and_reproducible() -> None:
    first = sample_configurations(12, seed=3)
    assert first == sample_configurations(12, seed=3)
    assert len({tuple(item.values()) for item in first}) == 12
    for configuration in first:
        for name, value in configuration.items():
            assert value in SEARCH_SPACE[name]


def test_model_learns_signal_and_stays_symmetric(history: pd.DataFrame) -> None:
    middle = int(len(history) * 0.7)
    end = int(len(history) * 0.85)
    train, validation, test = history.iloc[:middle], history.iloc[middle:end], history.iloc[end:]
    model, trials = search_hyperparameters(train, validation, trials=2, seed=1)
    assert len(trials) == 2
    assert model.validation_log_loss == min(trial.validation_log_loss for trial in trials)
    probabilities = predict_winner_probability(model, test)
    assert score(probabilities).log_loss < np.log(2)
    mirrored = predict_winner_probability(model, swapped(test))
    np.testing.assert_allclose(probabilities + mirrored, 1.0)
    importance = feature_importance(model)
    assert importance.sum() == pytest.approx(1.0)


def overconfident_predictions(size: int, seed: int) -> np.ndarray:
    generator = np.random.default_rng(seed)
    truth = generator.uniform(0.5, 0.8, size)
    favorite_wins = generator.uniform(size=size) < truth
    stretched = np.clip(0.5 + (truth - 0.5) * 1.6, 0, 0.99)
    return np.where(favorite_wins, stretched, 1 - stretched)


def test_platt_scaling_fixes_overconfidence() -> None:
    fitting = overconfident_predictions(6000, seed=1)
    evaluation = overconfident_predictions(6000, seed=2)
    calibrated = platt(fitting)(evaluation)
    assert score(calibrated).log_loss < score(evaluation).log_loss
    assert score(calibrated).calibration_error < score(evaluation).calibration_error


def test_isotonic_calibration_is_symmetric() -> None:
    transform = isotonic(overconfident_predictions(4000, seed=4))
    values = np.linspace(0.05, 0.95, 19)
    np.testing.assert_allclose(transform(values) + transform(1 - values), 1.0)


def test_choose_calibration_rejects_identity_for_overconfident_model() -> None:
    choice = choose_calibration(overconfident_predictions(6000, seed=6))
    assert choice.name != "aucune"
    assert set(choice.cross_fitted_log_loss) == {"aucune", "platt", "isotonique"}
