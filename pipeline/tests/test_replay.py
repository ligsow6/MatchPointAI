import random

import pandas as pd
import pytest

from pipeline.markov import MatchModel
from pipeline.replay import (
    ReplayDataError,
    normalized_name,
    oriented_sets,
    parse_set_scores,
    point_opportunities,
    point_outcome,
    replay_points,
    server_view,
)
from pipeline.scoring import FinalSetRule, MatchFormat, ScoreState, advance

BEST_OF_THREE = MatchFormat(3, FinalSetRule.TIEBREAK)


def charted_match(seed: int) -> pd.DataFrame:
    generator = random.Random(seed)
    state = ScoreState()
    rows = []
    number = 1
    while state.winner is None:
        winner = 0 if generator.random() < (0.64 if state.server == 0 else 0.4) else 1
        rows.append(
            {
                "Pt": number,
                "Set1": state.sets[0],
                "Set2": state.sets[1],
                "Gm1": state.games[0],
                "Gm2": state.games[1],
                "Pts": f"{sum(state.points) - state.points[1]}-{state.points[1]}"
                if state.in_tiebreak
                else server_view(state),
                "Svr": state.server + 1,
                "PtWinner": winner + 1,
            }
        )
        state = advance(state, winner, BEST_OF_THREE)
        number += 1
    return pd.DataFrame(rows)


def test_normalized_name_ignores_accents_and_case() -> None:
    assert normalized_name("Gaël  Monfils") == normalized_name("gael monfils")
    assert normalized_name("Jo-Wilfried Tsonga") == "jo wilfried tsonga"


def test_parse_set_scores_reads_tiebreaks() -> None:
    assert parse_set_scores("7-6(5) 1-6 13-12(3)") == [(7, 6, 5), (1, 6, None), (13, 12, 3)]


def test_oriented_sets_uses_the_match_winner_view() -> None:
    sets = ((6, 7), (6, 1), (12, 13))
    tiebreaks = [(5, 7), None, (3, 7)]
    assert oriented_sets(sets, tiebreaks, winner=1) == [(7, 6, 5), (1, 6, None), (13, 12, 3)]


def test_opportunities_flag_break_set_and_match_points() -> None:
    break_point = ScoreState(games=(2, 2), points=(1, 3), server=0)
    assert point_opportunities(break_point, BEST_OF_THREE) == ("break_point_1",)
    set_point = ScoreState(games=(5, 3), points=(3, 0), server=0)
    assert point_opportunities(set_point, BEST_OF_THREE) == ("set_point_0",)
    match_point = ScoreState(sets=(1, 0), games=(5, 4), points=(3, 3), server=1)
    assert point_opportunities(advance(match_point, 0, BEST_OF_THREE), BEST_OF_THREE) == (
        "match_point_0",
    )


def test_point_outcome_detects_breaks_and_sets() -> None:
    before = ScoreState(games=(1, 1), points=(0, 3), server=0)
    assert point_outcome(before, advance(before, 1, BEST_OF_THREE), 1) == "break"
    hold = ScoreState(games=(1, 1), points=(3, 0), server=0)
    assert point_outcome(hold, advance(hold, 0, BEST_OF_THREE), 0) is None
    closing = ScoreState(games=(5, 2), points=(3, 0), server=0)
    assert point_outcome(closing, advance(closing, 0, BEST_OF_THREE), 0) == "set"


def test_replay_points_follows_a_consistent_chart() -> None:
    chart = charted_match(seed=3)
    model = MatchModel((0.64, 0.6), BEST_OF_THREE)
    events, final_state, tiebreaks = replay_points(chart, BEST_OF_THREE, model)
    assert len(events) == len(chart)
    assert final_state.winner is not None
    assert len(tiebreaks) == len(final_state.completed_sets)
    assert events[-1].probability == (1.0 if final_state.winner == 0 else 0.0)
    assert all(0.0 <= event.probability <= 1.0 for event in events)


def test_replay_points_rejects_inconsistent_chart() -> None:
    chart = charted_match(seed=4)
    chart["Gm1"] = chart["Gm1"].where(chart.index != 10, chart["Gm1"] + 1)
    with pytest.raises(ReplayDataError, match="incohérent"):
        replay_points(chart, BEST_OF_THREE, MatchModel((0.64, 0.6), BEST_OF_THREE))
