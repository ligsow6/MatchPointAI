import math

import numpy as np
import pandas as pd
import pytest

from pipeline.data import clean_matches
from pipeline.elo import attach_elo
from pipeline.features import (
    attach_player_features,
    feature_names,
    loser_perspective,
    symmetric_training_set,
    winner_perspective,
)
from pipeline.tests.factories import raw_frame, raw_match, synthetic_history


def enrich(raw: pd.DataFrame) -> pd.DataFrame:
    return attach_player_features(attach_elo(clean_matches(raw)))


def model_inputs(matches: pd.DataFrame) -> pd.DataFrame:
    return winner_perspective(matches).astype({"surface": str, "tourney_level": str})


def test_features_ignore_future_matches() -> None:
    raw = synthetic_history()
    cutoff = len(raw) // 2
    full = enrich(raw)
    truncated = enrich(raw.iloc[:cutoff])
    expected = full.loc[full["match_key"].isin(truncated["match_key"])]
    assert len(expected) == cutoff
    pd.testing.assert_frame_equal(
        model_inputs(truncated).reset_index(drop=True),
        model_inputs(expected).reset_index(drop=True),
    )


def test_features_do_not_depend_on_future_results() -> None:
    raw = clean_matches(synthetic_history())
    cutoff = len(raw) // 2
    flipped = raw.copy()
    future = flipped.index >= cutoff
    for column in ("id", "name", "hand", "ht", "age", "rank", "rank_points"):
        winners = flipped.loc[future, f"winner_{column}"].copy()
        flipped.loc[future, f"winner_{column}"] = flipped.loc[future, f"loser_{column}"]
        flipped.loc[future, f"loser_{column}"] = winners
    original = attach_player_features(attach_elo(raw))
    altered = attach_player_features(attach_elo(flipped))
    pd.testing.assert_frame_equal(
        model_inputs(altered.iloc[:cutoff]), model_inputs(original.iloc[:cutoff])
    )
    assert not model_inputs(altered.iloc[cutoff:]).equals(model_inputs(original.iloc[cutoff:]))


def test_first_match_has_no_history() -> None:
    first = enrich(raw_frame(raw_match())).iloc[0]
    for column in ("form_short_w", "surface_form_short_w", "rest_days_w", "serve_won_w"):
        assert math.isnan(first[column])
    assert first["h2h_wins_w"] == 0
    assert first["tourney_matches_w"] == 0


def test_form_head_to_head_and_fatigue_accumulate() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2),
        raw_match(match_num=2, round="R16", winner_id=1, loser_id=3),
        raw_match(match_num=3, round="QF", winner_id=2, loser_id=1),
        raw_match(
            tourney_id="2024-0002",
            tourney_date=20240115,
            match_num=1,
            round="R32",
            winner_id=1,
            loser_id=2,
        ),
    )
    features = enrich(raw)
    third, fourth = features.iloc[2], features.iloc[3]
    assert third["form_short_l"] == pytest.approx(1.0)
    assert third["tourney_matches_l"] == 2
    assert third["h2h_wins_l"] == 1
    assert third["h2h_wins_w"] == 0
    assert third["rest_days_l"] == pytest.approx(1.0)
    assert fourth["form_short_w"] == pytest.approx(2 / 3)
    assert fourth["tourney_matches_w"] == 0
    assert fourth["h2h_wins_w"] == 1
    assert fourth["h2h_wins_l"] == 1
    assert fourth["rest_days_w"] == pytest.approx(5.0)


def test_walkovers_are_not_counted_as_played() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2, score="W/O"),
        raw_match(match_num=2, round="R16", winner_id=1, loser_id=3),
    )
    second = enrich(raw).iloc[1]
    assert second["tourney_matches_w"] == 0
    assert math.isnan(second["form_short_w"])


def test_serve_statistics_use_previous_matches_only() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", w_svpt=50, w_1stWon=25, w_2ndWon=10),
        raw_match(match_num=2, round="R16", loser_id=3, w_svpt=80, w_1stWon=60, w_2ndWon=15),
    )
    second = enrich(raw).iloc[1]
    assert second["serve_won_w"] == pytest.approx(35 / 50)
    assert second["return_won_w"] == pytest.approx((62 - 25 - 9) / 62)


def test_perspectives_are_mirror_images() -> None:
    matches = enrich(synthetic_history())
    as_winner = winner_perspective(matches)
    as_loser = loser_perspective(matches)
    for column in ("elo_diff", "elo_blend_diff", "form_short_diff", "age_diff"):
        np.testing.assert_allclose(as_winner[column], -as_loser[column])
    np.testing.assert_allclose(as_winner["elo_a"], as_loser["elo_b"])


def test_symmetric_training_set_is_balanced() -> None:
    matches = enrich(synthetic_history())
    features, labels = symmetric_training_set(matches)
    assert list(features.columns) == feature_names()
    assert len(features) == 2 * len(matches)
    assert labels.mean() == pytest.approx(0.5)
