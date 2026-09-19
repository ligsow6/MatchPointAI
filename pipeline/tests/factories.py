from typing import Any

import numpy as np
import pandas as pd

RAW_DEFAULTS: dict[str, Any] = {
    "tourney_id": "2024-0001",
    "tourney_name": "Test Open",
    "surface": "Hard",
    "draw_size": 32,
    "tourney_level": "A",
    "tourney_date": 20240108,
    "match_num": 1,
    "winner_id": 1,
    "winner_name": "Alpha",
    "winner_hand": "R",
    "winner_ht": 185,
    "winner_age": 25.0,
    "winner_rank": 10,
    "winner_rank_points": 3000,
    "loser_id": 2,
    "loser_name": "Beta",
    "loser_hand": "L",
    "loser_ht": 190,
    "loser_age": 27.0,
    "loser_rank": 20,
    "loser_rank_points": 1500,
    "score": "6-4 6-4",
    "best_of": 3,
    "round": "R32",
    "w_svpt": 60,
    "w_1stWon": 30,
    "w_2ndWon": 10,
    "l_svpt": 62,
    "l_1stWon": 25,
    "l_2ndWon": 9,
}


def raw_match(**overrides: Any) -> dict[str, Any]:
    return {**RAW_DEFAULTS, **overrides}


def raw_frame(*rows: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def synthetic_history(players: int = 24, tournaments: int = 40, seed: int = 11) -> pd.DataFrame:
    generator = np.random.default_rng(seed)
    skill = generator.normal(0.0, 1.0, players)
    rounds = ("R32", "R16", "QF", "SF", "F")
    surfaces = ("Hard", "Clay", "Grass")
    rows: list[dict[str, Any]] = []
    start = pd.Timestamp(2015, 1, 5)
    for tournament in range(tournaments):
        tourney_date = start + pd.Timedelta(weeks=tournament)
        surface = surfaces[tournament % len(surfaces)]
        for number, round_code in enumerate(rounds, start=1):
            first, second = generator.choice(players, size=2, replace=False)
            first_wins = generator.uniform() < 1 / (1 + np.exp(skill[second] - skill[first]))
            winner, loser = (first, second) if first_wins else (second, first)
            rows.append(
                raw_match(
                    tourney_id=f"2015-{tournament:04d}",
                    tourney_date=int(tourney_date.strftime("%Y%m%d")),
                    surface=surface,
                    match_num=number,
                    round=round_code,
                    winner_id=int(winner) + 100,
                    loser_id=int(loser) + 100,
                    winner_rank=int(players - skill.argsort().argsort()[winner]),
                    loser_rank=int(players - skill.argsort().argsort()[loser]),
                    score="W/O" if generator.uniform() < 0.03 else "6-4 6-4",
                )
            )
    return raw_frame(*rows)
