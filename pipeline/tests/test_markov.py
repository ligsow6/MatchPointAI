import random

import pytest

from pipeline.markov import MatchModel, game_hold_probability, serve_probabilities_for
from pipeline.scoring import FinalSetRule, MatchFormat, ScoreState, advance

FIVE_SETS = MatchFormat(5, FinalSetRule.TIEBREAK)


def simulate(model: MatchModel, state: ScoreState, runs: int, seed: int) -> float:
    generator = random.Random(seed)
    wins = 0
    for _ in range(runs):
        current = state
        while current.winner is None:
            point_win = model.point_probability(current.server)
            winner = 0 if generator.random() < point_win else 1
            current = advance(current, winner, model.match_format)
        wins += current.winner == 0
    return wins / runs


def test_game_hold_probability_known_values() -> None:
    assert game_hold_probability(0.5) == pytest.approx(0.5)
    assert game_hold_probability(0.6) == pytest.approx(0.735729, abs=1e-6)
    assert game_hold_probability(0.6, 3, 3) == pytest.approx(0.36 / 0.52)
    assert game_hold_probability(0.6, 4, 2) == 1.0
    assert game_hold_probability(0.6, 2, 4) == 0.0


def test_equal_players_are_even() -> None:
    model = MatchModel((0.64, 0.64), FIVE_SETS)
    assert model.win_probability(ScoreState()) == pytest.approx(0.5)


def test_first_server_does_not_change_pre_match_probability() -> None:
    model = MatchModel((0.67, 0.61), FIVE_SETS)
    assert model.win_probability(ScoreState(server=0)) == pytest.approx(
        model.win_probability(ScoreState(server=1))
    )


def test_tiebreak_probability_ignores_first_server() -> None:
    model = MatchModel((0.7, 0.62), FIVE_SETS)
    assert model.tiebreak_probability((0, 0), 0, 7) == pytest.approx(
        model.tiebreak_probability((0, 0), 1, 7)
    )


def test_finished_matches_are_certain() -> None:
    model = MatchModel((0.6, 0.6), FIVE_SETS)
    assert model.win_probability(ScoreState(sets=(3, 1), winner=0)) == 1.0
    assert model.win_probability(ScoreState(sets=(0, 3), winner=1)) == 0.0


def test_better_server_is_favored() -> None:
    weaker = MatchModel((0.62, 0.64), FIVE_SETS).win_probability(ScoreState())
    stronger = MatchModel((0.66, 0.64), FIVE_SETS).win_probability(ScoreState())
    assert weaker < 0.5 < stronger


@pytest.mark.parametrize(
    ("rule", "state"),
    [
        (FinalSetRule.ADVANTAGE, ScoreState(sets=(2, 2), games=(5, 5), points=(1, 2), server=1)),
        (FinalSetRule.TIEBREAK, ScoreState(sets=(1, 1), games=(3, 4), points=(3, 3))),
        (
            FinalSetRule.TIEBREAK_AT_TWELVE,
            ScoreState(sets=(2, 2), games=(12, 12), points=(3, 4), tiebreak_server=0),
        ),
        (
            FinalSetRule.MATCH_TIEBREAK,
            ScoreState(sets=(2, 2), games=(6, 6), points=(5, 5), tiebreak_server=1, server=0),
        ),
    ],
)
def test_markov_chain_agrees_with_simulation(rule: FinalSetRule, state: ScoreState) -> None:
    model = MatchModel((0.68, 0.65), MatchFormat(5, rule))
    runs = 12_000
    exact = model.win_probability(state)
    simulated = simulate(model, state, runs, seed=17)
    standard_error = (exact * (1 - exact) / runs) ** 0.5
    assert abs(simulated - exact) < 4 * standard_error


@pytest.mark.parametrize("target", [0.2, 0.5, 0.73, 0.95])
def test_serve_probabilities_reproduce_pre_match_probability(target: float) -> None:
    first, second = serve_probabilities_for(target, 0.64, 0, FIVE_SETS)
    assert first + second == pytest.approx(1.28)
    model = MatchModel((first, second), FIVE_SETS)
    assert model.win_probability(ScoreState()) == pytest.approx(target, abs=1e-6)
