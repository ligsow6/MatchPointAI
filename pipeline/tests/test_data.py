from datetime import date

import pandas as pd
import pytest

from pipeline.data import (
    OUTCOME_COMPLETED,
    OUTCOME_RETIREMENT,
    OUTCOME_UNKNOWN,
    OUTCOME_WALKOVER,
    DataQualityError,
    classify_outcome,
    clean_matches,
    completed_mask,
    estimated_day_offset,
    normalize_surface,
    playing_mask,
    summarize,
    validate_matches,
)
from pipeline.tests.factories import raw_frame, raw_match

TODAY = date(2026, 9, 19)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        ("6-4 6-4", OUTCOME_COMPLETED),
        ("6-7(5) 7-6(10) 7-6(3)", OUTCOME_COMPLETED),
        ("7-6(5) 1-6 7-6(4) 4-6 13-12(3)", OUTCOME_COMPLETED),
        ("6-3 6-4 6-7(2) [10-8]", OUTCOME_COMPLETED),
        ("6-2 3-1 RET", OUTCOME_RETIREMENT),
        ("W/O", OUTCOME_WALKOVER),
        ("Walkover", OUTCOME_WALKOVER),
        ("6-4 DEF", OUTCOME_RETIREMENT),
        ("Played and unfinished", OUTCOME_RETIREMENT),
        ("UNK", OUTCOME_UNKNOWN),
        ("6-4 ?-?", OUTCOME_UNKNOWN),
        (None, OUTCOME_UNKNOWN),
        ("", OUTCOME_UNKNOWN),
    ],
)
def test_classify_outcome(score: str | None, expected: str) -> None:
    assert classify_outcome(score) == expected


@pytest.mark.parametrize(
    ("surface", "expected"),
    [("Hard", "Hard"), ("clay", "Clay"), ("Grass", "Grass"), ("Carpet", "Hard"), (None, None)],
)
def test_normalize_surface(surface: str | None, expected: str | None) -> None:
    assert normalize_surface(surface) == expected


def test_estimated_day_offset_spreads_grand_slam_over_two_weeks() -> None:
    assert estimated_day_offset("G", 128, "R128") == 1
    assert estimated_day_offset("G", 128, "F") == 13
    assert estimated_day_offset("A", 32, "R32") == 2
    assert estimated_day_offset("A", 32, "F") == 6


def test_clean_matches_orders_rounds_chronologically() -> None:
    raw = raw_frame(
        raw_match(match_num=3, round="F", winner_id=1, loser_id=3),
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2),
        raw_match(match_num=2, round="QF", winner_id=1, loser_id=4),
    )
    clean = clean_matches(raw)
    assert clean["round"].tolist() == ["R32", "QF", "F"]
    assert clean["match_date"].is_monotonic_increasing


def test_clean_matches_discards_invalid_rows() -> None:
    raw = raw_frame(
        raw_match(match_num=1),
        raw_match(match_num=2, winner_id=5, loser_id=5),
        raw_match(match_num=3, best_of=1),
        raw_match(match_num=4, round="Q1"),
        raw_match(match_num=5, tourney_level="C"),
    )
    clean = clean_matches(raw)
    assert clean["match_key"].tolist() == ["2024-0001-1"]


def test_clean_matches_nullifies_aberrant_player_values() -> None:
    raw = raw_frame(
        raw_match(winner_ht=3, loser_ht=260, winner_age=63.6, loser_rank=-4, winner_rank_points=-1)
    )
    clean = clean_matches(raw)
    row = clean.iloc[0]
    assert pd.isna(row["winner_ht"])
    assert pd.isna(row["loser_ht"])
    assert pd.isna(row["winner_age"])
    assert pd.isna(row["loser_rank"])
    assert row["winner_rank_points"] == 0


def test_masks_separate_played_and_completed_matches() -> None:
    raw = raw_frame(
        raw_match(match_num=1, score="6-4 6-4"),
        raw_match(match_num=2, score="6-4 2-0 RET"),
        raw_match(match_num=3, score="W/O"),
        raw_match(match_num=4, score="6-4 6-4", surface=None),
    )
    clean = clean_matches(raw)
    assert playing_mask(clean).tolist() == [True, True, False, True]
    assert completed_mask(clean).tolist() == [True, False, False, False]


def test_summarize_counts_outcomes() -> None:
    raw = raw_frame(
        raw_match(match_num=1, score="6-4 6-4"),
        raw_match(match_num=2, score="6-4 2-0 RET"),
        raw_match(match_num=3, score="W/O"),
        raw_match(match_num=4, best_of=1),
    )
    summary = summarize(clean_matches(raw), raw_rows=len(raw))
    assert summary.completed_matches == 1
    assert summary.retirements == 1
    assert summary.walkovers == 1
    assert summary.discarded_rows == 1


def test_validate_matches_accepts_clean_data() -> None:
    clean = clean_matches(raw_frame(raw_match(match_num=1), raw_match(match_num=2)))
    validate_matches(clean, TODAY)


def corrupt(clean: pd.DataFrame, column: str, value: float | str | pd.Timestamp) -> pd.DataFrame:
    broken = clean.copy()
    broken.loc[0, column] = value
    return broken


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("tourney_date", pd.Timestamp(2031, 1, 1), "futur"),
        ("tourney_date", pd.Timestamp(1950, 1, 1), "ère Open"),
        ("winner_rank", -3.0, "classement"),
        ("loser_rank_points", -10.0, "points"),
        ("winner_ht", 40.0, "taille"),
        ("loser_age", 9.0, "âge"),
        ("loser_id", 1, "lui-même"),
        ("best_of", 7, "format"),
        ("surface", "Sand", "surface"),
    ],
)
def test_validate_matches_rejects_aberrant_values(
    column: str, value: float | str | pd.Timestamp, message: str
) -> None:
    clean = clean_matches(raw_frame(raw_match(match_num=1), raw_match(match_num=2)))
    with pytest.raises(DataQualityError, match=message):
        validate_matches(corrupt(clean, column, value), TODAY)


def test_validate_matches_rejects_unsorted_data() -> None:
    clean = clean_matches(
        raw_frame(raw_match(match_num=1, round="R32"), raw_match(match_num=2, round="F"))
    )
    reversed_order = clean.iloc[::-1].reset_index(drop=True)
    with pytest.raises(DataQualityError, match="chronologiquement"):
        validate_matches(reversed_order, TODAY)


def test_validate_matches_rejects_duplicates() -> None:
    clean = clean_matches(raw_frame(raw_match(match_num=1)))
    duplicated = pd.concat([clean, clean], ignore_index=True)
    with pytest.raises(DataQualityError, match="dupliqués"):
        validate_matches(duplicated, TODAY)
