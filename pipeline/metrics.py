from dataclasses import dataclass
from itertools import pairwise

import numpy as np

PROBABILITY_FLOOR = 1e-6
CALIBRATION_EDGES = np.linspace(0.5, 1.0, 11)
BOOTSTRAP_SAMPLES = 2000


@dataclass(frozen=True)
class Scores:
    matches: int
    accuracy: float
    log_loss: float
    brier: float
    calibration_error: float


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    matches: int
    mean_predicted: float
    observed: float


@dataclass(frozen=True)
class PairedDifference:
    metric: str
    mean: float
    lower: float
    upper: float


def clipped(probabilities: np.ndarray) -> np.ndarray:
    return np.asarray(np.clip(probabilities, PROBABILITY_FLOOR, 1.0 - PROBABILITY_FLOOR))


def per_match_losses(winner_probabilities: np.ndarray) -> dict[str, np.ndarray]:
    """Pertes par match à partir de la probabilité attribuée au vainqueur réel.

    exactitude = 1 si p > 0.5 (0.5 si p = 0.5), log loss = -ln(p), Brier = (1 - p)^2.
    """
    probabilities = clipped(winner_probabilities)
    correct = np.where(probabilities > 0.5, 1.0, np.where(probabilities == 0.5, 0.5, 0.0))
    return {
        "accuracy": correct,
        "log_loss": -np.log(probabilities),
        "brier": (1.0 - probabilities) ** 2,
    }


def favorite_view(winner_probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    favorite_probability = np.maximum(winner_probabilities, 1.0 - winner_probabilities)
    favorite_won = (winner_probabilities >= 0.5).astype(float)
    return favorite_probability, favorite_won


def calibration_bins(winner_probabilities: np.ndarray) -> list[CalibrationBin]:
    """Courbe de fiabilité vue du favori : probabilité prédite vs taux de victoire observé."""
    predicted, observed = favorite_view(winner_probabilities)
    bins: list[CalibrationBin] = []
    last_index = len(CALIBRATION_EDGES) - 2
    for index, (lower, upper) in enumerate(pairwise(CALIBRATION_EDGES)):
        upper_ok = predicted <= upper if index == last_index else predicted < upper
        members = (predicted >= lower) & upper_ok
        count = int(members.sum())
        if count == 0:
            continue
        bins.append(
            CalibrationBin(
                lower=float(lower),
                upper=float(upper),
                matches=count,
                mean_predicted=float(predicted[members].mean()),
                observed=float(observed[members].mean()),
            )
        )
    return bins


def expected_calibration_error(bins: list[CalibrationBin]) -> float:
    total = sum(item.matches for item in bins)
    if total == 0:
        return 0.0
    return sum(item.matches * abs(item.mean_predicted - item.observed) for item in bins) / total


def score(winner_probabilities: np.ndarray) -> Scores:
    losses = per_match_losses(winner_probabilities)
    return Scores(
        matches=len(winner_probabilities),
        accuracy=float(losses["accuracy"].mean()),
        log_loss=float(losses["log_loss"].mean()),
        brier=float(losses["brier"].mean()),
        calibration_error=expected_calibration_error(calibration_bins(winner_probabilities)),
    )


def paired_bootstrap(
    candidate: np.ndarray, reference: np.ndarray, seed: int
) -> list[PairedDifference]:
    """Intervalle de confiance à 95 % (bootstrap apparié) de l'écart candidat - référence."""
    candidate_losses = per_match_losses(candidate)
    reference_losses = per_match_losses(reference)
    generator = np.random.default_rng(seed)
    size = len(candidate)
    samples = generator.integers(0, size, size=(BOOTSTRAP_SAMPLES, size))
    differences: list[PairedDifference] = []
    for metric in ("accuracy", "log_loss", "brier"):
        delta = candidate_losses[metric] - reference_losses[metric]
        resampled = delta[samples].mean(axis=1)
        differences.append(
            PairedDifference(
                metric=metric,
                mean=float(delta.mean()),
                lower=float(np.quantile(resampled, 0.025)),
                upper=float(np.quantile(resampled, 0.975)),
            )
        )
    return differences
