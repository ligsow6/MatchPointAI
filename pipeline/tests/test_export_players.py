import json
import math
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from pipeline.comparator import (
    INACTIVE_DAYS,
    RELIABLE_MATCHES,
    MatchContext,
    PlayerRecord,
    comparator_features,
    reliability_issues,
)
from pipeline.data import clean_matches
from pipeline.elo import attach_elo, final_ratings
from pipeline.export_players import (
    COLUMNS,
    decode_record,
    encode_record,
    head_to_head_between,
    head_to_head_records,
    player_records,
    players_payload,
    published,
)
from pipeline.features import attach_player_features, replay_history, winner_perspective
from pipeline.tests.factories import raw_frame, raw_match, synthetic_history

COMPARABLE_PREFIXES = (
    "elo_",
    "surface_elo",
    "elo_played",
    "surface_played",
    "form_",
    "surface_form",
    "serve_won",
    "return_won",
    "h2h",
    "surface_hard",
    "surface_clay",
    "surface_grass",
    "level_",
    "round_order",
    "best_of",
    "draw_size",
)


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    return clean_matches(synthetic_history(players=30, tournaments=120, seed=21))


def records_of(matches: pd.DataFrame, minimum: int = 5) -> dict[int, PlayerRecord]:
    _, tracker = replay_history(matches)
    records = player_records(matches, final_ratings(matches), tracker, {}, minimum_matches=minimum)
    return {record.player_id: record for record in records}


def test_only_players_with_enough_matches_are_exported() -> None:
    raw = raw_frame(
        *[raw_match(match_num=n, round="R32", winner_id=1, loser_id=2) for n in range(1, 6)],
        raw_match(match_num=6, round="R32", winner_id=1, loser_id=3),
    )
    records = records_of(clean_matches(raw))
    assert set(records) == {1, 2}


def test_exported_state_matches_the_next_training_snapshot(history: pd.DataFrame) -> None:
    records = records_of(history)
    first, second = sorted(records)[:2]
    last = history["tourney_date"].max() + pd.Timedelta(weeks=1)
    upcoming = raw_frame(
        raw_match(
            tourney_id="2099-0001",
            tourney_date=int(last.strftime("%Y%m%d")),
            surface="Clay",
            tourney_level="M",
            draw_size=96,
            round="R64",
            winner_id=first,
            loser_id=second,
        )
    )
    extended = pd.concat([history, clean_matches(upcoming)], ignore_index=True)
    training = winner_perspective(attach_player_features(attach_elo(extended)).iloc[[-1]])
    context = MatchContext(surface="Clay", level="M", round_order=2, best_of=3, draw_size=96)
    duel = head_to_head_between(
        head_to_head_records(replay_history(history)[1], set(records)), first, second
    )
    comparator = comparator_features(records[first], records[second], context, duel)
    columns = [name for name in training.columns if name.startswith(COMPARABLE_PREFIXES)]
    assert "elo_blend_diff" in columns and "form_short_diff" in columns
    np.testing.assert_allclose(
        comparator[columns].to_numpy(dtype=float),
        training[columns].to_numpy(dtype=float),
        rtol=1e-12,
        equal_nan=True,
    )


def test_record_round_trip_keeps_published_values(history: pd.DataFrame) -> None:
    record = next(iter(records_of(history).values()))
    encoded = encode_record(record)
    assert list(encoded) == list(COLUMNS)
    json.dumps(encoded, allow_nan=False)
    decoded = decode_record(encoded)
    assert decoded == published(record)
    assert decoded.elo == pytest.approx(record.elo, abs=0.01)


def test_head_to_head_is_oriented_by_player() -> None:
    pairs = {"3": [[7, 4, 1]]}
    assert head_to_head_between(pairs, 3, 7) == (4, 1)
    assert head_to_head_between(pairs, 7, 3) == (1, 4)
    assert head_to_head_between(pairs, 3, 9) == (0, 0)


def test_head_to_head_records_only_keep_completed_duels() -> None:
    raw = raw_frame(
        raw_match(match_num=1, round="R32", winner_id=1, loser_id=2),
        raw_match(match_num=2, round="R16", winner_id=2, loser_id=1),
        raw_match(match_num=3, round="QF", winner_id=1, loser_id=3, score="W/O"),
    )
    _, tracker = replay_history(clean_matches(raw))
    assert head_to_head_records(tracker, {1, 2, 3}) == {"1": [[2, 1, 1]]}
    assert head_to_head_records(tracker, {1, 3}) == {}


def test_players_payload_is_columnar(history: pd.DataFrame) -> None:
    records = list(records_of(history).values())
    payload = players_payload(records, date(2016, 1, 1))
    rows = payload["players"]
    assert isinstance(rows, list)
    assert all(len(row) == len(COLUMNS) for row in rows)
    text = json.dumps(payload, allow_nan=False)
    assert "NaN" not in text


def test_reliability_flags_short_history_and_inactivity(history: pd.DataFrame) -> None:
    record = next(iter(records_of(history).values()))
    recent = record.last_match
    assert reliability_issues(record, recent) == (
        ["historique insuffisant"] if record.played < RELIABLE_MATCHES else []
    )
    later = date.fromordinal(recent.toordinal() + INACTIVE_DAYS + 1)
    assert "inactif depuis plus d'un an" in reliability_issues(record, later)


def test_missing_values_become_nan_features(history: pd.DataFrame) -> None:
    records = list(records_of(history).values())
    blank = published(records[0])
    stripped = replace(blank, rank=None, serve_won=None)
    context = MatchContext(surface="Hard", level="A", round_order=3, best_of=3, draw_size=32)
    features = comparator_features(stripped, published(records[1]), context, (0, 0)).iloc[0]
    assert math.isnan(features["rank_a"])
    assert math.isnan(features["log_rank_ratio"])
    assert math.isnan(features["serve_won_diff"])
    assert features["h2h_share"] == pytest.approx(0.5)
