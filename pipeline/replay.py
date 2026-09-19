import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.data import completed_mask
from pipeline.markov import MatchModel, serve_probabilities_for
from pipeline.scoring import (
    FinalSetRule,
    MatchFormat,
    ScoreState,
    advance,
    other,
    points_display,
)

SERVE_WINDOW_YEARS = 3
POINT_COLUMNS = ["match_id", "Pt", "Set1", "Set2", "Gm1", "Gm2", "Pts", "Svr", "PtWinner"]


@dataclass(frozen=True)
class ReplaySelection:
    slug: str
    charting_id: str
    title: str
    tourney_name: str
    year: int
    final_set: FinalSetRule
    points_file: str


REPLAY_SELECTIONS = (
    ReplaySelection(
        slug="wimbledon-2008",
        charting_id="20080706-M-Wimbledon-F-Roger_Federer-Rafael_Nadal",
        title="Finale de Wimbledon 2008",
        tourney_name="Wimbledon",
        year=2008,
        final_set=FinalSetRule.ADVANTAGE,
        points_file="charting-m-points-to-2009.csv",
    ),
    ReplaySelection(
        slug="open-australie-2012",
        charting_id="20120129-M-Australian_Open-F-Novak_Djokovic-Rafael_Nadal",
        title="Finale de l'Open d'Australie 2012",
        tourney_name="Australian Open",
        year=2012,
        final_set=FinalSetRule.ADVANTAGE,
        points_file="charting-m-points-2010s.csv",
    ),
    ReplaySelection(
        slug="wimbledon-2019",
        charting_id="20190714-M-Wimbledon-F-Roger_Federer-Novak_Djokovic",
        title="Finale de Wimbledon 2019",
        tourney_name="Wimbledon",
        year=2019,
        final_set=FinalSetRule.TIEBREAK_AT_TWELVE,
        points_file="charting-m-points-2010s.csv",
    ),
    ReplaySelection(
        slug="roland-garros-2025",
        charting_id="20250608-M-Roland_Garros-F-Jannik_Sinner-Carlos_Alcaraz",
        title="Finale de Roland-Garros 2025",
        tourney_name="Roland Garros",
        year=2025,
        final_set=FinalSetRule.MATCH_TIEBREAK,
        points_file="charting-m-points-2020s.csv",
    ),
    ReplaySelection(
        slug="open-australie-2026",
        charting_id="20260201-M-Australian_Open-F-Novak_Djokovic-Carlos_Alcaraz",
        title="Finale de l'Open d'Australie 2026",
        tourney_name="Australian Open",
        year=2026,
        final_set=FinalSetRule.MATCH_TIEBREAK,
        points_file="charting-m-points-2020s.csv",
    ),
)


class ReplayDataError(ValueError):
    pass


@dataclass(frozen=True)
class PointEvent:
    number: int
    server: int
    winner: int
    probability: float
    sets: tuple[int, int]
    games: tuple[int, int]
    points: tuple[str, str]
    tiebreak: bool
    opportunities: tuple[str, ...]
    outcome: str | None


@dataclass(frozen=True)
class MatchReplay:
    selection: ReplaySelection
    players: tuple[str, str]
    match_format: MatchFormat
    surface: str
    match_date: str
    winner: int
    set_scores: tuple[tuple[int, int], ...]
    tiebreak_scores: tuple[tuple[int, int] | None, ...]
    pre_match: dict[str, float]
    serve_win: tuple[float, float]
    tour_serve_win: float
    events: list[PointEvent] = field(default_factory=list)


def normalized_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(ascii_name.lower().replace("-", " ").split())


def read_points(path: Path, charting_id: str) -> pd.DataFrame:
    chunks = pd.read_csv(path, usecols=POINT_COLUMNS, chunksize=200_000, low_memory=False)
    selected = pd.concat(chunk.loc[chunk["match_id"] == charting_id] for chunk in chunks)
    if selected.empty:
        raise ReplayDataError(f"Aucun point pour {charting_id}")
    return selected.sort_values("Pt").reset_index(drop=True)


def read_players(path: Path, charting_id: str) -> tuple[str, str]:
    catalogue = pd.read_csv(path, low_memory=False)
    row = catalogue.loc[catalogue["match_id"] == charting_id]
    if row.empty:
        raise ReplayDataError(f"Match introuvable dans le catalogue : {charting_id}")
    return str(row.iloc[0]["Player 1"]), str(row.iloc[0]["Player 2"])


def server_view(state: ScoreState) -> str:
    own, opposing = points_display(state)
    if state.server == 1:
        own, opposing = opposing, own
    return f"{own}-{opposing}".replace("AV", "AD")


def tiebreak_points_played(notation: str) -> int:
    first, second = notation.split("-")
    return int(first) + int(second)


def check_point(state: ScoreState, row: pd.Series) -> list[str]:
    notation = str(row["Pts"]).strip()
    expected: dict[str, object] = {
        "sets": (int(row["Set1"]), int(row["Set2"])),
        "games": (int(row["Gm1"]), int(row["Gm2"])),
        "server": int(row["Svr"]) - 1,
        "points": tiebreak_points_played(notation) if state.in_tiebreak else notation,
    }
    observed: dict[str, object] = {
        "sets": state.sets,
        "games": state.games,
        "server": state.server,
        "points": sum(state.points) if state.in_tiebreak else server_view(state),
    }
    return [key for key in expected if expected[key] != observed[key]]


def point_opportunities(state: ScoreState, match_format: MatchFormat) -> tuple[str, ...]:
    labels: list[str] = []
    for player in (0, 1):
        after = advance(state, player, match_format)
        if after.winner == player:
            labels.append(f"match_point_{player}")
        elif after.sets != state.sets:
            labels.append(f"set_point_{player}")
        elif not state.in_tiebreak and player != state.server and after.games != state.games:
            labels.append(f"break_point_{player}")
    return tuple(labels)


def point_outcome(before: ScoreState, after: ScoreState, winner: int) -> str | None:
    if after.winner is not None:
        return "match"
    if after.sets != before.sets:
        return "set"
    if after.games != before.games and not before.in_tiebreak and winner != before.server:
        return "break"
    return None


def replay_points(
    points: pd.DataFrame, match_format: MatchFormat, model: MatchModel
) -> tuple[list[PointEvent], ScoreState, list[tuple[int, int] | None]]:
    state = ScoreState(server=int(points.iloc[0]["Svr"]) - 1)
    events: list[PointEvent] = []
    tiebreaks: list[tuple[int, int] | None] = []
    for _, row in points.iterrows():
        mismatches = check_point(state, row)
        if mismatches:
            raise ReplayDataError(f"Point {row['Pt']} incohérent : {', '.join(mismatches)}")
        winner = int(row["PtWinner"]) - 1
        opportunities = point_opportunities(state, match_format)
        after = advance(state, winner, match_format)
        if after.sets != state.sets:
            tiebreaks.append(
                (state.points[0] + (winner == 0), state.points[1] + (winner == 1))
                if state.in_tiebreak
                else None
            )
        events.append(
            PointEvent(
                number=int(row["Pt"]),
                server=state.server,
                winner=winner,
                probability=model.win_probability(after),
                sets=after.sets,
                games=after.games,
                points=points_display(after),
                tiebreak=after.in_tiebreak,
                opportunities=opportunities,
                outcome=point_outcome(state, after, winner),
            )
        )
        state = after
    return events, state, tiebreaks


def tour_serve_average(matches: pd.DataFrame, surface: str, year: int) -> float:
    """Part des points gagnés au service sur la surface lors des saisons précédant le match."""
    seasons = matches["tourney_date"].dt.year
    window = (
        completed_mask(matches)
        & (matches["surface"] == surface)
        & (seasons < year)
        & (seasons >= year - SERVE_WINDOW_YEARS)
    )
    frame = matches.loc[window]
    won = frame[["w_1stWon", "w_2ndWon", "l_1stWon", "l_2ndWon"]].sum().sum()
    played = frame[["w_svpt", "l_svpt"]].sum().sum()
    return float(won / played)


def locate_match(
    matches: pd.DataFrame, selection: ReplaySelection, players: tuple[str, str]
) -> pd.Series:
    names = {normalized_name(player) for player in players}
    candidates = matches.loc[
        (matches["tourney_name"] == selection.tourney_name)
        & (matches["tourney_date"].dt.year == selection.year)
        & (matches["round"] == "F")
    ]
    for index in candidates.index:
        row: pd.Series = candidates.loc[index]
        if {normalized_name(row["winner_name"]), normalized_name(row["loser_name"])} == names:
            return row
    raise ReplayDataError(f"Résultat officiel introuvable pour {selection.slug}")


def parse_set_scores(score: str) -> list[tuple[int, int, int | None]]:
    sets: list[tuple[int, int, int | None]] = []
    for token in score.split():
        games, _, tiebreak = token.partition("(")
        winner_games, loser_games = games.split("-")
        loser_tiebreak = int(tiebreak.rstrip(")")) if tiebreak else None
        sets.append((int(winner_games), int(loser_games), loser_tiebreak))
    return sets


def oriented_sets(
    sets: tuple[tuple[int, int], ...], tiebreaks: list[tuple[int, int] | None], winner: int
) -> list[tuple[int, int, int | None]]:
    oriented: list[tuple[int, int, int | None]] = []
    for games, tiebreak in zip(sets, tiebreaks, strict=True):
        set_winner = 0 if games[0] > games[1] else 1
        loser_points = tiebreak[other(set_winner)] if tiebreak else None
        own, opposing = games[winner], games[other(winner)]
        oriented.append((own, opposing, loser_points))
    return oriented


def player_one_probability(winner_probability: float, player_one_won: bool) -> float:
    return winner_probability if player_one_won else 1.0 - winner_probability


def build_replay(
    selection: ReplaySelection,
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    charting_dir: Path,
) -> MatchReplay:
    """Rejoue un match : probabilité d'avant-match du modèle puis chaîne de Markov par point."""
    players = read_players(charting_dir / "charting-m-matches.csv", selection.charting_id)
    points = read_points(charting_dir / selection.points_file, selection.charting_id)
    official = locate_match(matches, selection, players)
    player_one_won = normalized_name(str(official["winner_name"])) == normalized_name(players[0])
    prediction = predictions.loc[predictions["match_key"] == official["match_key"]]
    if prediction.empty:
        raise ReplayDataError(f"Aucune prédiction hors échantillon pour {selection.slug}")
    pre_match = {
        key: player_one_probability(float(prediction.iloc[0][key]), player_one_won)
        for key in ("model", "elo")
    }
    match_format = MatchFormat(int(official["best_of"]), selection.final_set)
    surface = str(official["surface"])
    tour_serve = tour_serve_average(matches, surface, selection.year)
    first_server = int(points.iloc[0]["Svr"]) - 1
    serve_win = serve_probabilities_for(pre_match["model"], tour_serve, first_server, match_format)
    model = MatchModel(serve_win, match_format)
    events, final_state, tiebreaks = replay_points(points, match_format, model)
    expected_winner = 0 if player_one_won else 1
    if final_state.winner != expected_winner:
        raise ReplayDataError(f"Vainqueur incohérent pour {selection.slug}")
    oriented = oriented_sets(final_state.completed_sets, tiebreaks, expected_winner)
    if oriented != parse_set_scores(str(official["score"])):
        raise ReplayDataError(f"Score final incohérent pour {selection.slug}")
    return MatchReplay(
        selection=selection,
        players=players,
        match_format=match_format,
        surface=surface,
        match_date=str(pd.Timestamp(official["match_date"]).date()),
        winner=expected_winner,
        set_scores=final_state.completed_sets,
        tiebreak_scores=tuple(tiebreaks),
        pre_match=pre_match,
        serve_win=serve_win,
        tour_serve_win=tour_serve,
        events=events,
    )


def probability_path(replay: MatchReplay) -> np.ndarray:
    return np.array([replay.pre_match["model"], *(event.probability for event in replay.events)])
