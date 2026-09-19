from dataclasses import dataclass, replace
from enum import StrEnum

GAME_POINT_LABELS = ("0", "15", "30", "40")


class FinalSetRule(StrEnum):
    ADVANTAGE = "advantage"
    TIEBREAK = "tiebreak"
    TIEBREAK_AT_TWELVE = "tiebreak_12"
    MATCH_TIEBREAK = "tiebreak_10"


@dataclass(frozen=True)
class MatchFormat:
    best_of: int
    final_set: FinalSetRule

    @property
    def sets_to_win(self) -> int:
        return self.best_of // 2 + 1


@dataclass(frozen=True)
class SetRule:
    tiebreak_at: int | None
    tiebreak_target: int


REGULAR_SET = SetRule(tiebreak_at=6, tiebreak_target=7)
SET_RULES = {
    FinalSetRule.ADVANTAGE: SetRule(tiebreak_at=None, tiebreak_target=7),
    FinalSetRule.TIEBREAK: REGULAR_SET,
    FinalSetRule.TIEBREAK_AT_TWELVE: SetRule(tiebreak_at=12, tiebreak_target=7),
    FinalSetRule.MATCH_TIEBREAK: SetRule(tiebreak_at=6, tiebreak_target=10),
}


@dataclass(frozen=True)
class ScoreState:
    sets: tuple[int, int] = (0, 0)
    games: tuple[int, int] = (0, 0)
    points: tuple[int, int] = (0, 0)
    server: int = 0
    tiebreak_server: int | None = None
    completed_sets: tuple[tuple[int, int], ...] = ()
    winner: int | None = None

    @property
    def in_tiebreak(self) -> bool:
        return self.tiebreak_server is not None

    @property
    def finished(self) -> bool:
        return self.winner is not None


def other(player: int) -> int:
    return 1 - player


def with_point(pair: tuple[int, int], player: int) -> tuple[int, int]:
    return (pair[0] + 1, pair[1]) if player == 0 else (pair[0], pair[1] + 1)


def set_rule(state: ScoreState, match_format: MatchFormat) -> SetRule:
    deciding = state.sets[0] == state.sets[1] == match_format.sets_to_win - 1
    return SET_RULES[match_format.final_set] if deciding else REGULAR_SET


def tiebreak_point_server(first_server: int, points_played: int) -> int:
    """Au tie-break, le premier serveur sert un point, puis le service alterne tous les deux."""
    return first_server if ((points_played + 1) // 2) % 2 == 0 else other(first_server)


def race_won(scores: tuple[int, int], player: int, target: int) -> bool:
    return scores[player] >= target and scores[player] - scores[other(player)] >= 2


def game_won(points: tuple[int, int], player: int) -> bool:
    return race_won(points, player, 4)


def set_won(games: tuple[int, int], player: int, rule: SetRule) -> bool:
    won_tiebreak = (
        rule.tiebreak_at is not None
        and games[player] == rule.tiebreak_at + 1
        and games[other(player)] == rule.tiebreak_at
    )
    return won_tiebreak or race_won(games, player, 6)


def close_set(
    state: ScoreState, games: tuple[int, int], player: int, next_server: int, sets_to_win: int
) -> ScoreState:
    sets = with_point(state.sets, player)
    return ScoreState(
        sets=sets,
        games=(0, 0),
        points=(0, 0),
        server=next_server,
        tiebreak_server=None,
        completed_sets=(*state.completed_sets, games),
        winner=player if sets[player] == sets_to_win else None,
    )


def close_game(state: ScoreState, player: int, match_format: MatchFormat) -> ScoreState:
    rule = set_rule(state, match_format)
    games = with_point(state.games, player)
    if state.in_tiebreak or set_won(games, player, rule):
        first_server = state.tiebreak_server if state.tiebreak_server is not None else state.server
        next_server = other(first_server) if state.in_tiebreak else other(state.server)
        return close_set(state, games, player, next_server, match_format.sets_to_win)
    starts_tiebreak = rule.tiebreak_at is not None and games == (rule.tiebreak_at, rule.tiebreak_at)
    next_server = other(state.server)
    return replace(
        state,
        games=games,
        points=(0, 0),
        server=next_server,
        tiebreak_server=next_server if starts_tiebreak else None,
    )


def advance(state: ScoreState, point_winner: int, match_format: MatchFormat) -> ScoreState:
    """Applique le gain d'un point au score (jeu, tie-break, set, match)."""
    if state.finished:
        raise ValueError("Le match est déjà terminé")
    points = with_point(state.points, point_winner)
    if state.in_tiebreak and state.tiebreak_server is not None:
        target = set_rule(state, match_format).tiebreak_target
        if race_won(points, point_winner, target):
            return close_game(state, point_winner, match_format)
        server = tiebreak_point_server(state.tiebreak_server, sum(points))
        return replace(state, points=points, server=server)
    if game_won(points, point_winner):
        return close_game(state, point_winner, match_format)
    return replace(state, points=points)


def point_label(points: tuple[int, int], player: int) -> str:
    own, opposing = points[player], points[other(player)]
    if own >= 3 and opposing >= 3:
        if own == opposing:
            return "40"
        return "AV" if own > opposing else "40"
    return GAME_POINT_LABELS[min(own, 3)]


def points_display(state: ScoreState) -> tuple[str, str]:
    if state.in_tiebreak:
        return str(state.points[0]), str(state.points[1])
    return point_label(state.points, 0), point_label(state.points, 1)
