from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from pipeline.metrics import clipped, score

IDENTITY = "aucune"
PLATT = "platt"
ISOTONIC = "isotonique"


@dataclass(frozen=True)
class Calibration:
    """Transformation appliquée à la probabilité symétrisée du modèle.

    platt : p' = 1 / (1 + exp(-(a × logit(p) + b)))
    isotonique : p' = (f(p) + 1 - f(1 - p)) / 2, f interpolation linéaire bornée
    """

    kind: str
    coefficient: float = 1.0
    intercept: float = 0.0
    knots_x: tuple[float, ...] = field(default_factory=tuple)
    knots_y: tuple[float, ...] = field(default_factory=tuple)

    def __call__(self, probabilities: np.ndarray) -> np.ndarray:
        if self.kind == PLATT:
            scores = self.coefficient * logit(probabilities) + self.intercept
            return np.asarray(1.0 / (1.0 + np.exp(-scores)))
        if self.kind == ISOTONIC:
            direct = np.interp(probabilities, self.knots_x, self.knots_y)
            mirrored = np.interp(1.0 - probabilities, self.knots_x, self.knots_y)
            return np.asarray(0.5 * (direct + 1.0 - mirrored))
        return np.asarray(probabilities, dtype=float)

    def parameters(self) -> dict[str, object]:
        if self.kind == PLATT:
            return {"kind": self.kind, "coefficient": self.coefficient, "intercept": self.intercept}
        if self.kind == ISOTONIC:
            return {"kind": self.kind, "x": list(self.knots_x), "y": list(self.knots_y)}
        return {"kind": self.kind}


@dataclass(frozen=True)
class CalibrationChoice:
    name: str
    transform: Calibration
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


def identity(winner_probabilities: np.ndarray) -> Calibration:
    return Calibration(IDENTITY)


def platt(winner_probabilities: np.ndarray) -> Calibration:
    probabilities, labels = symmetric_pairs(winner_probabilities)
    regression = LogisticRegression(C=1e6).fit(logit(probabilities).reshape(-1, 1), labels)
    return Calibration(
        PLATT,
        coefficient=float(regression.coef_[0][0]),
        intercept=float(regression.intercept_[0]),
    )


def isotonic(winner_probabilities: np.ndarray) -> Calibration:
    probabilities, labels = symmetric_pairs(winner_probabilities)
    regression = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    regression.fit(probabilities, labels)
    return Calibration(
        ISOTONIC,
        knots_x=tuple(float(value) for value in regression.X_thresholds_),
        knots_y=tuple(float(value) for value in regression.y_thresholds_),
    )


CALIBRATORS: dict[str, Callable[[np.ndarray], Calibration]] = {
    IDENTITY: identity,
    PLATT: platt,
    ISOTONIC: isotonic,
}


def cross_fitted_log_loss(
    fitter: Callable[[np.ndarray], Calibration], winner_probabilities: np.ndarray
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
