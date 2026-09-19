import math
from collections import defaultdict, deque
from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pipeline.data import OUTCOME_COMPLETED, OUTCOME_RETIREMENT

SHORT_FORM = 10
LONG_FORM = 20
SERVE_WINDOW = 30
REST_CAP_DAYS = 60.0
SURFACE_CATEGORIES = ("Hard", "Clay", "Grass")
LEVEL_CATEGORIES = ("G", "M", "A", "F", "D", "O")

PLAYER_FEATURES = (
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


@dataclass
class ServeRecord:
    serve_points: float
    serve_won: float
    return_points: float
    return_won: float


@dataclass
class PlayerState:
    results: deque[bool] = field(default_factory=lambda: deque(maxlen=LONG_FORM))
    surface_results: dict[str, deque[bool]] = field(
        default_factory=lambda: defaultdict(lambda: deque(maxlen=LONG_FORM))
    )
    serve_history: deque[ServeRecord] = field(default_factory=lambda: deque(maxlen=SERVE_WINDOW))
    last_played: pd.Timestamp | None = None
    tourney_id: str | None = None
    tourney_matches: int = 0


def win_rate(results: deque[bool], window: int) -> float:
    recent = list(results)[-window:]
    if not recent:
        return math.nan
    return sum(recent) / len(recent)


def serve_rates(history: deque[ServeRecord]) -> tuple[float, float]:
    serve_points = sum(record.serve_points for record in history)
    return_points = sum(record.return_points for record in history)
    serve = sum(record.serve_won for record in history) / serve_points if serve_points else math.nan
    returned = (
        sum(record.return_won for record in history) / return_points if return_points else math.nan
    )
    return serve, returned


def rest_days(state: PlayerState, match_date: pd.Timestamp) -> float:
    if state.last_played is None:
        return math.nan
    return min(float((match_date - state.last_played).days), REST_CAP_DAYS)


def matches_in_tourney(state: PlayerState, tourney_id: str) -> int:
    return state.tourney_matches if state.tourney_id == tourney_id else 0


def player_snapshot(
    state: PlayerState,
    surface: str | None,
    match_date: pd.Timestamp,
    tourney_id: str,
    h2h_wins: int,
) -> tuple[float, ...]:
    surface_results = state.surface_results[surface] if surface else deque()
    serve, returned = serve_rates(state.serve_history)
    return (
        win_rate(state.results, SHORT_FORM),
        win_rate(state.results, LONG_FORM),
        win_rate(surface_results, SHORT_FORM),
        win_rate(surface_results, LONG_FORM),
        rest_days(state, match_date),
        float(matches_in_tourney(state, tourney_id)),
        serve,
        returned,
        float(h2h_wins),
    )


def serve_record(row: Mapping[Hashable, object], own: str, opponent: str) -> ServeRecord | None:
    values = [
        row.get(f"{prefix}_{column}")
        for prefix in (own, opponent)
        for column in ("svpt", "1stWon", "2ndWon")
    ]
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    if len(numbers) != 6 or any(math.isnan(number) for number in numbers):
        return None
    own_points, own_first, own_second, opponent_points, opponent_first, opponent_second = numbers
    if own_points <= 0 or opponent_points <= 0:
        return None
    return ServeRecord(
        serve_points=own_points,
        serve_won=own_first + own_second,
        return_points=opponent_points,
        return_won=opponent_points - opponent_first - opponent_second,
    )


def register_played(state: PlayerState, match_date: pd.Timestamp, tourney_id: str) -> None:
    if state.tourney_id != tourney_id:
        state.tourney_id = tourney_id
        state.tourney_matches = 0
    state.tourney_matches += 1
    state.last_played = match_date


def register_result(
    state: PlayerState, won: bool, surface: str | None, record: ServeRecord | None
) -> None:
    state.results.append(won)
    if surface:
        state.surface_results[surface].append(won)
    if record is not None:
        state.serve_history.append(record)


def pair_key(first: int, second: int) -> tuple[int, int]:
    return (first, second) if first < second else (second, first)


def pre_match_player_features(matches: pd.DataFrame) -> pd.DataFrame:
    """Calcule, pour chaque match, l'état des deux joueurs avant la rencontre."""
    players: dict[int, PlayerState] = defaultdict(PlayerState)
    head_to_head: dict[tuple[int, int], dict[int, int]] = defaultdict(lambda: defaultdict(int))
    columns = [
        "winner_id",
        "loser_id",
        "surface",
        "match_date",
        "tourney_id",
        "outcome",
        "w_svpt",
        "w_1stWon",
        "w_2ndWon",
        "l_svpt",
        "l_1stWon",
        "l_2ndWon",
    ]
    rows: list[tuple[float, ...]] = []
    for row in matches[columns].to_dict("records"):
        winner_id = int(row["winner_id"])
        loser_id = int(row["loser_id"])
        surface = row["surface"] if isinstance(row["surface"], str) else None
        match_date = pd.Timestamp(row["match_date"])
        tourney_id = str(row["tourney_id"])
        duel = head_to_head[pair_key(winner_id, loser_id)]
        winner_state, loser_state = players[winner_id], players[loser_id]
        rows.append(
            player_snapshot(winner_state, surface, match_date, tourney_id, duel[winner_id])
            + player_snapshot(loser_state, surface, match_date, tourney_id, duel[loser_id])
        )
        if row["outcome"] in (OUTCOME_COMPLETED, OUTCOME_RETIREMENT):
            register_played(winner_state, match_date, tourney_id)
            register_played(loser_state, match_date, tourney_id)
        if row["outcome"] == OUTCOME_COMPLETED:
            register_result(winner_state, True, surface, serve_record(row, "w", "l"))
            register_result(loser_state, False, surface, serve_record(row, "l", "w"))
            duel[winner_id] += 1
    names = [f"{name}_w" for name in PLAYER_FEATURES] + [f"{name}_l" for name in PLAYER_FEATURES]
    return pd.DataFrame(np.array(rows, dtype=float), columns=names, index=matches.index)


def side_values(matches: pd.DataFrame, suffix: str, prefix: str) -> dict[str, pd.Series]:
    values: dict[str, pd.Series] = {
        "elo": matches[f"elo_{suffix}"],
        "surface_elo": matches[f"surface_elo_{suffix}"],
        "elo_played": matches[f"elo_played_{suffix}"],
        "surface_played": matches[f"surface_played_{suffix}"],
        "rank": matches[f"{prefix}_rank"],
        "rank_points": matches[f"{prefix}_rank_points"],
        "age": matches[f"{prefix}_age"],
        "height": matches[f"{prefix}_ht"],
        "left_handed": (matches[f"{prefix}_hand"] == "L").astype(float),
    }
    for name in PLAYER_FEATURES:
        values[name] = matches[f"{name}_{suffix}"]
    return values


DIFFERENCE_FEATURES = (
    "elo",
    "surface_elo",
    "form_short",
    "form_long",
    "surface_form_short",
    "surface_form_long",
    "rest_days",
    "serve_won",
    "return_won",
    "age",
    "height",
)
SIDE_FEATURES = (
    "elo",
    "surface_elo",
    "elo_played",
    "surface_played",
    "rank",
    "rank_points",
    "age",
    "form_short",
    "surface_form_short",
    "rest_days",
    "tourney_matches",
    "serve_won",
    "return_won",
    "left_handed",
    "h2h_wins",
)
CONTEXT_FEATURES = ("surface", "tourney_level", "round_order", "best_of", "draw_size")


def feature_names() -> list[str]:
    derived = ["elo_blend_diff", "log_rank_ratio", "log_points_ratio", "h2h_share"]
    differences = [f"{name}_diff" for name in DIFFERENCE_FEATURES]
    sides = [f"{name}_{side}" for name in SIDE_FEATURES for side in ("a", "b")]
    return derived + differences + sides + list(CONTEXT_FEATURES)


def oriented_features(
    matches: pd.DataFrame, player_a: dict[str, pd.Series], player_b: dict[str, pd.Series]
) -> pd.DataFrame:
    frame = pd.DataFrame(index=matches.index)
    frame["elo_blend_diff"] = 0.5 * (player_a["elo"] - player_b["elo"]) + 0.5 * (
        player_a["surface_elo"] - player_b["surface_elo"]
    )
    frame["log_rank_ratio"] = np.log(player_b["rank"]) - np.log(player_a["rank"])
    frame["log_points_ratio"] = np.log1p(player_a["rank_points"]) - np.log1p(
        player_b["rank_points"]
    )
    frame["h2h_share"] = (player_a["h2h_wins"] + 1.0) / (
        player_a["h2h_wins"] + player_b["h2h_wins"] + 2.0
    )
    for name in DIFFERENCE_FEATURES:
        frame[f"{name}_diff"] = player_a[name] - player_b[name]
    for name in SIDE_FEATURES:
        frame[f"{name}_a"] = player_a[name]
        frame[f"{name}_b"] = player_b[name]
    frame["surface"] = pd.Categorical(matches["surface"], categories=SURFACE_CATEGORIES)
    frame["tourney_level"] = pd.Categorical(matches["tourney_level"], categories=LEVEL_CATEGORIES)
    frame["round_order"] = matches["round_order"].astype(float)
    frame["best_of"] = matches["best_of"].astype(float)
    frame["draw_size"] = matches["draw_size"].astype(float)
    return frame[feature_names()]


def winner_perspective(matches: pd.DataFrame) -> pd.DataFrame:
    return oriented_features(
        matches, side_values(matches, "w", "winner"), side_values(matches, "l", "loser")
    )


def loser_perspective(matches: pd.DataFrame) -> pd.DataFrame:
    return oriented_features(
        matches, side_values(matches, "l", "loser"), side_values(matches, "w", "winner")
    )


def attach_player_features(matches: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([matches, pre_match_player_features(matches)], axis=1)


def symmetric_training_set(matches: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Chaque match apparaît deux fois (vainqueur puis perdant en joueur A) : jeu symétrique."""
    features = pd.concat(
        [winner_perspective(matches), loser_perspective(matches)], ignore_index=True
    )
    labels = np.concatenate([np.ones(len(matches)), np.zeros(len(matches))])
    return features, labels
