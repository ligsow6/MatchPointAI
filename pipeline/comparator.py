import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from pipeline.calibration import Calibration
from pipeline.features import SURFACE_CATEGORIES, winner_perspective

Predictor = Callable[[np.ndarray], np.ndarray]

NEUTRAL_REST_DAYS = 7.0
MIN_MATCHES = 5
RELIABLE_MATCHES = 15
INACTIVE_DAYS = 365


@dataclass(frozen=True)
class MatchContext:
    """Match hypothétique : premier tour d'un tournoi, les deux joueurs reposés depuis 7 jours."""

    surface: str
    level: str
    round_order: int
    best_of: int
    draw_size: int
    rest_days: float = NEUTRAL_REST_DAYS
    tourney_matches: float = 0.0


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    level: str
    round_order: int
    best_of: int
    draw_size: int

    def context(self, surface: str) -> MatchContext:
        return MatchContext(surface, self.level, self.round_order, self.best_of, self.draw_size)


PRESETS = (
    Preset("atp", "ATP 250 ou 500 (3 sets)", "A", 3, 3, 32),
    Preset("masters", "Masters 1000 (3 sets)", "M", 2, 3, 96),
    Preset("grand-chelem", "Grand Chelem (5 sets)", "G", 1, 5, 128),
)


@dataclass(frozen=True)
class PlayerRecord:
    """État d'un joueur à l'issue de son dernier match connu."""

    player_id: int
    name: str
    country: str | None
    hand: str | None
    height: float | None
    birth_date: str | None
    age: float | None
    rank: float | None
    rank_points: float | None
    elo: float
    played: int
    surface_elo: Mapping[str, float]
    surface_played: Mapping[str, int]
    form_short: float | None
    form_long: float | None
    surface_form_short: Mapping[str, float | None]
    surface_form_long: Mapping[str, float | None]
    serve_won: float | None
    return_won: float | None
    last_match: date


def missing(value: float | None) -> float:
    return math.nan if value is None else float(value)


def side_columns(record: PlayerRecord, context: MatchContext, suffix: str) -> dict[str, object]:
    prefix = "winner" if suffix == "w" else "loser"
    surface = context.surface
    return {
        f"elo_{suffix}": record.elo,
        f"surface_elo_{suffix}": record.surface_elo[surface],
        f"elo_played_{suffix}": float(record.played),
        f"surface_played_{suffix}": float(record.surface_played[surface]),
        f"{prefix}_rank": missing(record.rank),
        f"{prefix}_rank_points": missing(record.rank_points),
        f"{prefix}_age": missing(record.age),
        f"{prefix}_ht": missing(record.height),
        f"{prefix}_hand": record.hand,
        f"form_short_{suffix}": missing(record.form_short),
        f"form_long_{suffix}": missing(record.form_long),
        f"surface_form_short_{suffix}": missing(record.surface_form_short[surface]),
        f"surface_form_long_{suffix}": missing(record.surface_form_long[surface]),
        f"rest_days_{suffix}": context.rest_days,
        f"tourney_matches_{suffix}": context.tourney_matches,
        f"serve_won_{suffix}": missing(record.serve_won),
        f"return_won_{suffix}": missing(record.return_won),
    }


def comparator_features(
    player_a: PlayerRecord,
    player_b: PlayerRecord,
    context: MatchContext,
    head_to_head: tuple[int, int],
) -> pd.DataFrame:
    """Variables du match hypothétique A contre B, calculées par le code d'entraînement."""
    if context.surface not in SURFACE_CATEGORIES:
        raise ValueError(f"Surface inconnue : {context.surface}")
    row: dict[str, object] = {
        "surface": context.surface,
        "tourney_level": context.level,
        "round_order": context.round_order,
        "best_of": context.best_of,
        "draw_size": context.draw_size,
        "h2h_wins_w": float(head_to_head[0]),
        "h2h_wins_l": float(head_to_head[1]),
        **side_columns(player_a, context, "w"),
        **side_columns(player_b, context, "l"),
    }
    return winner_perspective(pd.DataFrame([row])).astype(float)


def symmetric_probability(
    predict: Predictor,
    player_a: PlayerRecord,
    player_b: PlayerRecord,
    *,
    context: MatchContext,
    head_to_head: tuple[int, int],
    calibration: Calibration,
) -> float:
    """P(A bat B) = calibration((p(A, B) + 1 - p(B, A)) / 2), comme pour l'évaluation."""
    forward = comparator_features(player_a, player_b, context, head_to_head)
    backward = comparator_features(player_b, player_a, context, (head_to_head[1], head_to_head[0]))
    probabilities = predict(pd.concat([forward, backward]).to_numpy(dtype=float))
    raw = 0.5 * (probabilities[0] + 1.0 - probabilities[1])
    return float(calibration(np.array([raw]))[0])


def reliability_issues(record: PlayerRecord, data_through: date) -> list[str]:
    issues: list[str] = []
    if record.played < RELIABLE_MATCHES:
        issues.append("historique insuffisant")
    if (data_through - record.last_match).days > INACTIVE_DAYS:
        issues.append("inactif depuis plus d'un an")
    return issues
