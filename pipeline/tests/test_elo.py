import math

import pytest

from pipeline.data import clean_matches
from pipeline.elo import (
    INITIAL_RATING,
    attach_elo,
    elo_probabilities,
    expected_score,
    k_factor,
    updated_ratings,
)
from pipeline.tests.factories import raw_frame, raw_match


def test_expected_score_is_one_half_for_equal_ratings() -> None:
    assert expected_score(1500, 1500) == pytest.approx(0.5)


def test_expected_score_matches_classic_formula() -> None:
    assert expected_score(1900, 1500) == pytest.approx(10 / 11)
    assert expected_score(1500, 1900) == pytest.approx(1 / 11)


def test_expected_scores_of_both_players_sum_to_one() -> None:
    assert expected_score(1732, 1611) + expected_score(1611, 1732) == pytest.approx(1.0)


def test_k_factor_decreases_with_experience() -> None:
    assert k_factor(0) == pytest.approx(250 / 5**0.4)
    assert k_factor(0) > k_factor(10) > k_factor(200)
    assert k_factor(1000) > 0


def test_update_moves_ratings_in_opposite_directions() -> None:
    winner, loser = updated_ratings(1500, 1500, 50, 50)
    assert winner > 1500 > loser
    assert (winner - 1500) == pytest.approx(1500 - loser)
    assert winner - 1500 == pytest.approx(k_factor(50) * 0.5)


def test_upset_moves_ratings_more_than_expected_win() -> None:
    favorite_gain = updated_ratings(1800, 1500, 100, 100)[0] - 1800
    underdog_gain = updated_ratings(1500, 1800, 100, 100)[0] - 1500
    assert underdog_gain > favorite_gain > 0


def test_update_is_zero_sum_when_experience_is_equal() -> None:
    winner, loser = updated_ratings(1620, 1580, 30, 30)
    assert winner + loser == pytest.approx(1620 + 1580)


def test_attach_elo_uses_only_prior_matches() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2),
        raw_match(match_num=2, round="R16", winner_id=1, loser_id=3),
    )
    rated = attach_elo(clean_matches(raw))
    first, second = rated.iloc[0], rated.iloc[1]
    assert first["elo_w"] == INITIAL_RATING
    assert first["elo_l"] == INITIAL_RATING
    assert first["elo_played_w"] == 0
    assert second["elo_w"] > INITIAL_RATING
    assert second["elo_played_w"] == 1
    assert second["elo_l"] == INITIAL_RATING


def test_walkovers_and_retirements_do_not_change_ratings() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2, score="W/O"),
        raw_match(match_num=2, round="R16", winner_id=1, loser_id=3, score="6-1 2-0 RET"),
        raw_match(match_num=3, round="QF", winner_id=1, loser_id=4),
    )
    rated = attach_elo(clean_matches(raw))
    assert rated.iloc[2]["elo_w"] == INITIAL_RATING
    assert rated.iloc[2]["elo_played_w"] == 0


def test_surface_ratings_are_independent() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2, surface="Clay"),
        raw_match(
            tourney_id="2024-0002",
            tourney_date=20240115,
            match_num=1,
            round="R32",
            winner_id=2,
            loser_id=1,
            surface="Grass",
        ),
    )
    rated = attach_elo(clean_matches(raw))
    grass_match = rated.iloc[1]
    assert grass_match["surface_elo_w"] == INITIAL_RATING
    assert grass_match["surface_elo_l"] == INITIAL_RATING
    assert grass_match["elo_l"] > INITIAL_RATING


def test_elo_probabilities_follow_logistic_curve() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2, surface="Clay"),
        raw_match(match_num=2, round="R16", winner_id=1, loser_id=3, surface="Clay"),
        raw_match(
            tourney_id="2024-0002",
            tourney_date=20240115,
            match_num=1,
            winner_id=1,
            loser_id=4,
            surface="Hard",
        ),
    )
    rated = attach_elo(clean_matches(raw))
    probabilities = elo_probabilities(rated)
    assert probabilities["elo_global"][0] == pytest.approx(0.5)
    difference = rated.iloc[2]["elo_w"] - rated.iloc[2]["elo_l"]
    assert probabilities["elo_global"][2] == pytest.approx(
        1 / (1 + math.pow(10, -difference / 400))
    )
    assert probabilities["elo_surface"][2] == pytest.approx(0.5)
    assert 0.5 < probabilities["elo_blend"][2] < probabilities["elo_global"][2]
