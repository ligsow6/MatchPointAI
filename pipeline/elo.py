from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pipeline.data import completed_mask

INITIAL_RATING = 1500.0
K_NUMERATOR = 250.0
K_OFFSET = 5.0
K_SHAPE = 0.4
SURFACE_WEIGHT = 0.5


def expected_score(rating: float, opponent_rating: float) -> float:
    """Probabilité de victoire Elo : 1 / (1 + 10^((R_adversaire - R_joueur) / 400))."""
    return float(1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / 400.0)))


def k_factor(matches_played: int) -> float:
    """Facteur K dégressif (FiveThirtyEight) : K = 250 / (n + 5)^0.4."""
    return float(K_NUMERATOR / (matches_played + K_OFFSET) ** K_SHAPE)


def updated_ratings(
    winner_rating: float, loser_rating: float, winner_played: int, loser_played: int
) -> tuple[float, float]:
    """Mise à jour Elo : R' = R + K(n) * (S - E), S valant 1 (vainqueur) ou 0 (perdant)."""
    winner_expectation = expected_score(winner_rating, loser_rating)
    delta_winner = k_factor(winner_played) * (1.0 - winner_expectation)
    delta_loser = k_factor(loser_played) * (0.0 - (1.0 - winner_expectation))
    return winner_rating + delta_winner, loser_rating + delta_loser


@dataclass
class RatingPool:
    ratings: dict[int, float] = field(default_factory=lambda: defaultdict(lambda: INITIAL_RATING))
    played: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def snapshot(self, player_id: int) -> tuple[float, int]:
        return self.ratings[player_id], self.played[player_id]

    def record(self, winner_id: int, loser_id: int) -> None:
        winner_rating, loser_rating = updated_ratings(
            self.ratings[winner_id],
            self.ratings[loser_id],
            self.played[winner_id],
            self.played[loser_id],
        )
        self.ratings[winner_id] = winner_rating
        self.ratings[loser_id] = loser_rating
        self.played[winner_id] += 1
        self.played[loser_id] += 1


@dataclass
class EloTracker:
    overall: RatingPool = field(default_factory=RatingPool)
    by_surface: dict[str, RatingPool] = field(default_factory=lambda: defaultdict(RatingPool))

    def surface_pool(self, surface: str | None) -> RatingPool | None:
        return self.by_surface[surface] if surface else None

    def record(self, winner_id: int, loser_id: int, surface: str | None) -> None:
        self.overall.record(winner_id, loser_id)
        pool = self.surface_pool(surface)
        if pool is not None:
            pool.record(winner_id, loser_id)


ELO_COLUMNS = (
    "elo_w",
    "elo_l",
    "elo_played_w",
    "elo_played_l",
    "surface_elo_w",
    "surface_elo_l",
    "surface_played_w",
    "surface_played_l",
)


def rate_history(
    winners: Iterable[int],
    losers: Iterable[int],
    surfaces: Iterable[str | None],
    updates: Iterable[bool],
) -> tuple[np.ndarray, EloTracker]:
    tracker = EloTracker()
    rows: list[tuple[float, float, int, int, float, float, int, int]] = []
    for winner_id, loser_id, surface, should_update in zip(
        winners, losers, surfaces, updates, strict=True
    ):
        winner_rating, winner_played = tracker.overall.snapshot(winner_id)
        loser_rating, loser_played = tracker.overall.snapshot(loser_id)
        pool = tracker.surface_pool(surface)
        winner_surface, winner_surface_played = (
            pool.snapshot(winner_id) if pool else (winner_rating, 0)
        )
        loser_surface, loser_surface_played = pool.snapshot(loser_id) if pool else (loser_rating, 0)
        rows.append(
            (
                winner_rating,
                loser_rating,
                winner_played,
                loser_played,
                winner_surface,
                loser_surface,
                winner_surface_played,
                loser_surface_played,
            )
        )
        if should_update:
            tracker.record(winner_id, loser_id, surface)
    return np.array(rows, dtype=float), tracker


def rate_matches(matches: pd.DataFrame) -> tuple[np.ndarray, EloTracker]:
    surfaces = [surface if isinstance(surface, str) else None for surface in matches["surface"]]
    return rate_history(
        matches["winner_id"].tolist(),
        matches["loser_id"].tolist(),
        surfaces,
        completed_mask(matches).tolist(),
    )


def final_ratings(matches: pd.DataFrame) -> EloTracker:
    """Elo global et par surface de chaque joueur après le dernier match connu."""
    return rate_matches(matches)[1]


def attach_elo(matches: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les Elo global et par surface connus avant chaque match (ordre chronologique)."""
    values, _ = rate_matches(matches)
    enriched = matches.copy()
    for index, column in enumerate(ELO_COLUMNS):
        enriched[column] = values[:, index]
    return enriched


def elo_probabilities(matches: pd.DataFrame) -> dict[str, np.ndarray]:
    overall = matches["elo_w"].to_numpy() - matches["elo_l"].to_numpy()
    surface = matches["surface_elo_w"].to_numpy() - matches["surface_elo_l"].to_numpy()
    blended = (1.0 - SURFACE_WEIGHT) * overall + SURFACE_WEIGHT * surface
    return {
        "elo_global": logistic_from_difference(overall),
        "elo_surface": logistic_from_difference(surface),
        "elo_blend": logistic_from_difference(blended),
    }


def logistic_from_difference(difference: np.ndarray) -> np.ndarray:
    return np.asarray(1.0 / (1.0 + np.power(10.0, -difference / 400.0)), dtype=float)
