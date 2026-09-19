from collections.abc import Iterable

import pytest

from pipeline.scoring import (
    FinalSetRule,
    MatchFormat,
    ScoreState,
    advance,
    points_display,
    tiebreak_point_server,
)

BEST_OF_THREE = MatchFormat(3, FinalSetRule.TIEBREAK)


def play(state: ScoreState, winners: Iterable[int], match_format: MatchFormat) -> ScoreState:
    for winner in winners:
        state = advance(state, winner, match_format)
    return state


def hold_games(state: ScoreState, count: int, match_format: MatchFormat) -> ScoreState:
    for _ in range(count):
        state = play(state, [state.server] * 4, match_format)
    return state


def test_love_game_changes_server() -> None:
    state = play(ScoreState(), [0, 0, 0, 0], BEST_OF_THREE)
    assert state.games == (1, 0)
    assert state.points == (0, 0)
    assert state.server == 1


def test_deuce_and_advantage_are_displayed() -> None:
    state = play(ScoreState(), [0, 1, 0, 1, 0, 1], BEST_OF_THREE)
    assert points_display(state) == ("40", "40")
    state = advance(state, 1, BEST_OF_THREE)
    assert points_display(state) == ("40", "AV")
    state = play(state, [0, 0, 0], BEST_OF_THREE)
    assert state.games == (1, 0)


def test_set_is_won_seven_five() -> None:
    state = hold_games(ScoreState(), 10, BEST_OF_THREE)
    assert state.games == (5, 5)
    state = play(state, [0] * 8, BEST_OF_THREE)
    assert state.sets == (1, 0)
    assert state.completed_sets == ((7, 5),)


def test_tiebreak_serving_order_and_next_set_server() -> None:
    state = hold_games(ScoreState(), 12, BEST_OF_THREE)
    assert state.games == (6, 6)
    assert state.in_tiebreak
    first_server = state.tiebreak_server
    assert first_server == 0
    servers = []
    for _ in range(6):
        servers.append(state.server)
        state = advance(state, state.server, BEST_OF_THREE)
    assert servers == [0, 1, 1, 0, 0, 1]
    state = play(state, [0] * 4, BEST_OF_THREE)
    assert state.sets == (1, 0)
    assert state.completed_sets == ((7, 6),)
    assert state.server == 1


def test_tiebreak_point_server_pattern() -> None:
    assert [tiebreak_point_server(1, points) for points in range(7)] == [1, 0, 0, 1, 1, 0, 0]


@pytest.mark.parametrize(
    ("rule", "games_before_tiebreak", "target"),
    [
        (FinalSetRule.TIEBREAK, 12, 7),
        (FinalSetRule.TIEBREAK_AT_TWELVE, 24, 7),
        (FinalSetRule.MATCH_TIEBREAK, 12, 10),
    ],
)
def test_final_set_tiebreak_rules(
    rule: FinalSetRule, games_before_tiebreak: int, target: int
) -> None:
    match_format = MatchFormat(3, rule)
    state = ScoreState(sets=(1, 1))
    state = hold_games(state, games_before_tiebreak, match_format)
    assert state.in_tiebreak
    state = play(state, [0] * (target - 1), match_format)
    assert not state.finished
    state = advance(state, 0, match_format)
    assert state.winner == 0


def test_advantage_final_set_has_no_tiebreak() -> None:
    match_format = MatchFormat(5, FinalSetRule.ADVANTAGE)
    state = hold_games(ScoreState(sets=(2, 2)), 30, match_format)
    assert state.games == (15, 15)
    assert not state.in_tiebreak
    state = play(state, [0] * 8, match_format)
    assert state.winner == 0
    assert state.completed_sets[-1] == (17, 15)


def test_finished_match_rejects_more_points() -> None:
    state = play(ScoreState(), [0] * 48, BEST_OF_THREE)
    assert state.winner == 0
    assert state.completed_sets == ((6, 0), (6, 0))
    with pytest.raises(ValueError, match="terminé"):
        advance(state, 0, BEST_OF_THREE)
