import math

import numpy as np
import pandas as pd
import pytest

from pipeline.metrics import calibration_bins, paired_bootstrap, score
from pipeline.splits import TEST, TRAIN, VALIDATION, assign_periods


def test_score_of_coin_flip_predictions() -> None:
    result = score(np.full(100, 0.5))
    assert result.accuracy == pytest.approx(0.5)
    assert result.log_loss == pytest.approx(math.log(2))
    assert result.brier == pytest.approx(0.25)


def test_score_rewards_confident_correct_predictions() -> None:
    confident = score(np.full(10, 0.9))
    assert confident.accuracy == 1.0
    assert confident.log_loss == pytest.approx(-math.log(0.9))
    assert confident.brier == pytest.approx(0.01)


def test_score_penalizes_confident_mistakes() -> None:
    wrong = score(np.array([0.1, 0.1]))
    assert wrong.accuracy == 0.0
    assert wrong.brier == pytest.approx(0.81)


def test_log_loss_stays_finite_for_certain_mistakes() -> None:
    assert math.isfinite(score(np.array([0.0])).log_loss)


def test_calibration_is_seen_from_favorite() -> None:
    probabilities = np.array([0.7, 0.7, 0.7, 0.3, 0.52, 0.48])
    bins = calibration_bins(probabilities)
    seventy = next(item for item in bins if item.lower == pytest.approx(0.7))
    assert seventy.matches == 4
    assert seventy.mean_predicted == pytest.approx(0.7)
    assert seventy.observed == pytest.approx(0.75)
    fifty = next(item for item in bins if item.lower == pytest.approx(0.5))
    assert fifty.matches == 2
    assert fifty.observed == pytest.approx(0.5)


def test_calibration_includes_certain_predictions_in_last_bin() -> None:
    bins = calibration_bins(np.array([1.0, 0.0]))
    assert len(bins) == 1
    assert bins[0].upper == pytest.approx(1.0)
    assert bins[0].observed == pytest.approx(0.5)


def test_perfectly_calibrated_predictions_have_small_error() -> None:
    generator = np.random.default_rng(3)
    favorite = generator.uniform(0.5, 0.95, 50_000)
    favorite_wins = generator.uniform(size=favorite.size) < favorite
    winner_probabilities = np.where(favorite_wins, favorite, 1 - favorite)
    assert score(winner_probabilities).calibration_error < 0.01


def test_paired_bootstrap_brackets_the_mean_difference() -> None:
    generator = np.random.default_rng(7)
    reference = generator.uniform(0.3, 0.9, 2000)
    candidate = np.clip(reference + 0.02, 0, 1)
    for difference in paired_bootstrap(candidate, reference, seed=1):
        assert difference.lower <= difference.mean <= difference.upper
    log_loss = next(
        item for item in paired_bootstrap(candidate, reference, 1) if item.metric == "log_loss"
    )
    assert log_loss.upper < 0


def test_assign_periods_is_strictly_chronological() -> None:
    dates = pd.Series(pd.to_datetime(["1985-05-01", "2010-01-01", "2024-03-01", "2025-01-06"]))
    assert assign_periods(dates).tolist() == ["history", TRAIN, VALIDATION, TEST]


def test_assign_periods_rejects_inverted_bounds() -> None:
    dates = pd.Series(pd.to_datetime(["2010-01-01"]))
    with pytest.raises(ValueError, match="croissantes"):
        assign_periods(dates, pd.Timestamp(2020, 1, 1).date(), pd.Timestamp(2019, 1, 1).date())
