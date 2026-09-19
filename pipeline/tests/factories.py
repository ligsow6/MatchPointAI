from typing import Any

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
