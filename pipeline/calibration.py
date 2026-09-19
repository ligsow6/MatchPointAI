from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from pipeline.metrics import clipped, score

Transform = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class CalibrationChoice:
    name: str
    transform: Transform
    cross_fitted_log_loss: dict[str, float]


def symmetric_pairs(winner_probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    probabilities = np.concatenate([winner_probabilities, 1.0 - winner_probabilities])
    labels = np.concatenate(
        [np.ones(len(winner_probabilities)), np.zeros(len(winner_probabilities))]
    )
    return probabilities, labels


def logit(probabilities: np.ndarray) -> np.ndarray:
    bounded = clipped(probabilities)
    return np.asarray(np.log(bounded / (1.0 - bounded)))


def identity(winner_probabilities: np.ndarray) -> Transform:
    def transform(probabilities: np.ndarray) -> np.ndarray:
        return probabilities

    return transform


def platt(winner_probabilities: np.ndarray) -> Transform:
    """Calibration de Platt : p' = sigmoïde(a * logit(p) + b), ajustée par régression logistique."""
    probabilities, labels = symmetric_pairs(winner_probabilities)
    regression = LogisticRegression(C=1e6).fit(logit(probabilities).reshape(-1, 1), labels)

    def transform(values: np.ndarray) -> np.ndarray:
        return np.asarray(regression.predict_proba(logit(values).reshape(-1, 1))[:, 1])

    return transform


def isotonic(winner_probabilities: np.ndarray) -> Transform:
    probabilities, labels = symmetric_pairs(winner_probabilities)
    regression = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    regression.fit(probabilities, labels)

    def transform(values: np.ndarray) -> np.ndarray:
        return np.asarray(
            0.5 * (regression.predict(values) + 1.0 - regression.predict(1.0 - values))
        )

    return transform


CALIBRATORS: dict[str, Callable[[np.ndarray], Transform]] = {
    "aucune": identity,
    "platt": platt,
    "isotonique": isotonic,
}


def cross_fitted_log_loss(
    fitter: Callable[[np.ndarray], Transform], winner_probabilities: np.ndarray
) -> float:
    middle = len(winner_probabilities) // 2
    first, second = winner_probabilities[:middle], winner_probabilities[middle:]
    losses = [
        score(fitter(first)(second)).log_loss * len(second),
        score(fitter(second)(first)).log_loss * len(first),
    ]
    return float(sum(losses) / len(winner_probabilities))


def choose_calibration(validation_probabilities: np.ndarray) -> CalibrationChoice:
    """Retient la calibration de plus faible log loss en validation croisée sur deux moitiés."""
    losses = {
        name: cross_fitted_log_loss(fitter, validation_probabilities)
        for name, fitter in CALIBRATORS.items()
    }
    best_name = min(losses, key=lambda name: losses[name])
    transform = CALIBRATORS[best_name](validation_probabilities)
    return CalibrationChoice(best_name, transform, losses)
