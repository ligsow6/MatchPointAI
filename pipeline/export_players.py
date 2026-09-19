import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.calibration import Calibration
from pipeline.comparator import (
    INACTIVE_DAYS,
    MIN_MATCHES,
    NEUTRAL_REST_DAYS,
    PRESETS,
    RELIABLE_MATCHES,
    MatchContext,
    PlayerRecord,
    Predictor,
    symmetric_probability,
)
from pipeline.data import playing_mask
from pipeline.elo import INITIAL_RATING, EloTracker
from pipeline.export import write_json
from pipeline.features import (
    LONG_FORM,
    SHORT_FORM,
    SURFACE_CATEGORIES,
    HistoryTracker,
    PlayerState,
    serve_rates,
    win_rate,
)

SURFACE_SUFFIXES = {"Hard": "Hard", "Clay": "Clay", "Grass": "Grass"}
COLUMNS = (
    "id",
    "name",
    "country",
    "hand",
    "height",
    "birthDate",
    "age",
    "rank",
    "rankPoints",
    "elo",
    "played",
    *(f"elo{suffix}" for suffix in SURFACE_SUFFIXES.values()),
    *(f"played{suffix}" for suffix in SURFACE_SUFFIXES.values()),
    "formShort",
    "formLong",
    *(
        f"form{window}{suffix}"
        for suffix in SURFACE_SUFFIXES.values()
        for window in ("Short", "Long")
    ),
    "serveWon",
    "returnWon",
    "lastMatch",
)
ELO_DIGITS = 2
RATE_DIGITS = 4
SANITY_NAMES = (("Rafael Nadal", "Roger Federer"), ("Novak Djokovic", "Rafael Nadal"))


@dataclass(frozen=True)
class PlayerProfile:
    birth_date: str | None
    country: str | None


def optional(value: object) -> float | None:
    if value is None:
        return None
    number = float(str(value))
    return None if math.isnan(number) else number


def rounded(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def read_profiles(path: Path | None) -> dict[int, PlayerProfile]:
    if path is None or not path.exists():
        return {}
    table = pd.read_csv(path, usecols=["player_id", "dob", "ioc"], low_memory=False)
    profiles: dict[int, PlayerProfile] = {}
    for player_id, birth, country in zip(
        table["player_id"], table["dob"], table["ioc"], strict=True
    ):
        parsed = pd.to_datetime(str(birth).split(".")[0], format="%Y%m%d", errors="coerce")
        profiles[int(player_id)] = PlayerProfile(
            birth_date=None if pd.isna(parsed) else parsed.date().isoformat(),
            country=country if isinstance(country, str) else None,
        )
    return profiles


def last_appearances(matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dernier match joué de chaque joueur (classement, âge) et dernières valeurs connues."""
    played = matches.loc[playing_mask(matches)]
    order = np.arange(len(played))
    sides = [
        pd.DataFrame(
            {
                "player_id": played[f"{side}_id"].to_numpy(),
                "name": played[f"{side}_name"].to_numpy(),
                "hand": played[f"{side}_hand"].to_numpy(),
                "height": played[f"{side}_ht"].to_numpy(),
                "age": played[f"{side}_age"].to_numpy(),
                "rank": played[f"{side}_rank"].to_numpy(),
                "rank_points": played[f"{side}_rank_points"].to_numpy(),
                "match_date": played["match_date"].to_numpy(),
                "order": order,
            }
        )
        for side in ("winner", "loser")
    ]
    long = pd.concat(sides, ignore_index=True).sort_values("order", kind="mergesort")
    grouped = long.groupby("player_id", sort=True)
    latest = grouped.nth(-1).set_index("player_id")
    known = grouped[["name", "hand", "height"]].last()
    return latest, known


def state_rates(state: PlayerState | None) -> dict[str, float | None]:
    if state is None:
        return {}
    serve, returned = serve_rates(state.serve_history)
    rates: dict[str, float | None] = {
        "form_short": optional(win_rate(state.results, SHORT_FORM)),
        "form_long": optional(win_rate(state.results, LONG_FORM)),
        "serve_won": optional(serve),
        "return_won": optional(returned),
    }
    for surface in SURFACE_CATEGORIES:
        results = state.surface_results.get(surface)
        rates[f"short_{surface}"] = optional(win_rate(results, SHORT_FORM)) if results else None
        rates[f"long_{surface}"] = optional(win_rate(results, LONG_FORM)) if results else None
    return rates


def player_record(
    player_id: int,
    *,
    latest: pd.Series,
    known: pd.Series,
    elo: EloTracker,
    history: HistoryTracker,
    profile: PlayerProfile | None,
) -> PlayerRecord:
    rates = state_rates(history.players.get(player_id))
    pools = {surface: elo.by_surface.get(surface) for surface in SURFACE_CATEGORIES}
    hand = known["hand"]
    return PlayerRecord(
        player_id=player_id,
        name=str(known["name"]),
        country=profile.country if profile else None,
        hand=hand if isinstance(hand, str) else None,
        height=optional(known["height"]),
        birth_date=profile.birth_date if profile else None,
        age=optional(latest["age"]),
        rank=optional(latest["rank"]),
        rank_points=optional(latest["rank_points"]),
        elo=elo.overall.ratings.get(player_id, INITIAL_RATING),
        played=elo.overall.played.get(player_id, 0),
        surface_elo={
            surface: pool.ratings.get(player_id, INITIAL_RATING) if pool else INITIAL_RATING
            for surface, pool in pools.items()
        },
        surface_played={
            surface: pool.played.get(player_id, 0) if pool else 0 for surface, pool in pools.items()
        },
        form_short=rates.get("form_short"),
        form_long=rates.get("form_long"),
        surface_form_short={
            surface: rates.get(f"short_{surface}") for surface in SURFACE_CATEGORIES
        },
        surface_form_long={surface: rates.get(f"long_{surface}") for surface in SURFACE_CATEGORIES},
        serve_won=rates.get("serve_won"),
        return_won=rates.get("return_won"),
        last_match=pd.Timestamp(latest["match_date"]).date(),
    )


def player_records(
    matches: pd.DataFrame,
    elo: EloTracker,
    history: HistoryTracker,
    profiles: Mapping[int, PlayerProfile],
    minimum_matches: int = MIN_MATCHES,
) -> list[PlayerRecord]:
    """Un enregistrement par joueur ayant disputé au moins `minimum_matches` matchs complets."""
    latest, known = last_appearances(matches)
    records = [
        player_record(
            int(player_id),
            latest=latest.loc[player_id],
            known=known.loc[player_id],
            elo=elo,
            history=history,
            profile=profiles.get(int(player_id)),
        )
        for player_id in latest.index
        if elo.overall.played.get(int(player_id), 0) >= minimum_matches
    ]
    return sorted(records, key=lambda record: (record.name, record.player_id))


def encode_record(record: PlayerRecord) -> dict[str, object]:
    values: dict[str, object] = {
        "id": record.player_id,
        "name": record.name,
        "country": record.country,
        "hand": record.hand,
        "height": rounded(record.height, 0),
        "birthDate": record.birth_date,
        "age": rounded(record.age, 2),
        "rank": rounded(record.rank, 0),
        "rankPoints": rounded(record.rank_points, 0),
        "elo": round(record.elo, ELO_DIGITS),
        "played": record.played,
        "formShort": rounded(record.form_short, RATE_DIGITS),
        "formLong": rounded(record.form_long, RATE_DIGITS),
        "serveWon": rounded(record.serve_won, RATE_DIGITS),
        "returnWon": rounded(record.return_won, RATE_DIGITS),
        "lastMatch": record.last_match.isoformat(),
    }
    for surface, suffix in SURFACE_SUFFIXES.items():
        values[f"elo{suffix}"] = round(record.surface_elo[surface], ELO_DIGITS)
        values[f"played{suffix}"] = record.surface_played[surface]
        values[f"formShort{suffix}"] = rounded(record.surface_form_short[surface], RATE_DIGITS)
        values[f"formLong{suffix}"] = rounded(record.surface_form_long[surface], RATE_DIGITS)
    return {column: values[column] for column in COLUMNS}


def number_or_none(value: object) -> float | None:
    return None if value is None else float(str(value))


def decode_record(values: Mapping[str, object]) -> PlayerRecord:
    hand = values["hand"]
    country = values["country"]
    birth = values["birthDate"]
    return PlayerRecord(
        player_id=int(str(values["id"])),
        name=str(values["name"]),
        country=country if isinstance(country, str) else None,
        hand=hand if isinstance(hand, str) else None,
        height=number_or_none(values["height"]),
        birth_date=birth if isinstance(birth, str) else None,
        age=number_or_none(values["age"]),
        rank=number_or_none(values["rank"]),
        rank_points=number_or_none(values["rankPoints"]),
        elo=float(str(values["elo"])),
        played=int(str(values["played"])),
        surface_elo={s: float(str(values[f"elo{x}"])) for s, x in SURFACE_SUFFIXES.items()},
        surface_played={s: int(str(values[f"played{x}"])) for s, x in SURFACE_SUFFIXES.items()},
        form_short=number_or_none(values["formShort"]),
        form_long=number_or_none(values["formLong"]),
        surface_form_short={
            s: number_or_none(values[f"formShort{x}"]) for s, x in SURFACE_SUFFIXES.items()
        },
        surface_form_long={
            s: number_or_none(values[f"formLong{x}"]) for s, x in SURFACE_SUFFIXES.items()
        },
        serve_won=number_or_none(values["serveWon"]),
        return_won=number_or_none(values["returnWon"]),
        last_match=date.fromisoformat(str(values["lastMatch"])),
    )


def published(record: PlayerRecord) -> PlayerRecord:
    """Enregistrement tel que le navigateur le lira, après arrondi de publication."""
    return decode_record(encode_record(record))


def head_to_head_records(history: HistoryTracker, included: set[int]) -> dict[str, list[list[int]]]:
    """Face-à-face groupés par plus petit identifiant : [adversaire, victoires, défaites]."""
    grouped: dict[str, list[list[int]]] = {}
    for (first, second), duel in sorted(history.head_to_head.items()):
        wins = [duel.get(first, 0), duel.get(second, 0)]
        if first in included and second in included and sum(wins) > 0:
            grouped.setdefault(str(first), []).append([second, *wins])
    return grouped


def head_to_head_between(
    grouped: Mapping[str, Sequence[Sequence[int]]], player_a: int, player_b: int
) -> tuple[int, int]:
    first, second = sorted((player_a, player_b))
    entry = next((item for item in grouped.get(str(first), ()) if item[0] == second), None)
    wins = (entry[1], entry[2]) if entry is not None else (0, 0)
    return wins if player_a == first else (wins[1], wins[0])


def players_payload(records: Sequence[PlayerRecord], data_through: date) -> dict[str, object]:
    return {
        "dataThrough": data_through.isoformat(),
        "minMatches": MIN_MATCHES,
        "reliableMatches": RELIABLE_MATCHES,
        "inactiveDays": INACTIVE_DAYS,
        "columns": list(COLUMNS),
        "players": [list(encode_record(record).values()) for record in records],
    }


def sanity_pairs(
    records: Sequence[PlayerRecord], data_through: date
) -> list[tuple[PlayerRecord, PlayerRecord]]:
    by_name = {record.name: record for record in records}
    pairs = [(by_name[a], by_name[b]) for a, b in SANITY_NAMES if a in by_name and b in by_name]
    active = sorted(
        (r for r in records if (data_through - r.last_match).days <= INACTIVE_DAYS),
        key=lambda record: -record.elo,
    )
    historic = sorted(
        (r for r in records if r.last_match.year < 1995),
        key=lambda record: -record.elo,
    )
    if len(active) >= 2:
        pairs.append((active[0], active[1]))
    if active and historic:
        pairs.append((active[0], historic[0]))
    return pairs


def sanity_cases(
    records: Sequence[PlayerRecord],
    pairs: Mapping[str, Sequence[Sequence[int]]],
    predict: Predictor,
    calibration: Calibration,
    data_through: date,
) -> list[dict[str, object]]:
    """Cas de contrôle : probabilités Python que le navigateur doit retrouver à 1e-6 près."""
    cases: list[dict[str, object]] = []
    for index, (player_a, player_b) in enumerate(sanity_pairs(records, data_through)):
        surface = SURFACE_CATEGORIES[index % len(SURFACE_CATEGORIES)]
        preset = PRESETS[index % len(PRESETS)]
        a, b = published(player_a), published(player_b)
        duel = head_to_head_between(pairs, a.player_id, b.player_id)
        probability = symmetric_probability(
            predict,
            a,
            b,
            context=preset.context(surface),
            head_to_head=duel,
            calibration=calibration,
        )
        cases.append(
            {
                "playerA": a.player_id,
                "playerB": b.player_id,
                "surface": surface,
                "preset": preset.key,
                "probability": probability,
            }
        )
    return cases


def presets_payload() -> list[dict[str, object]]:
    return [
        {
            "key": preset.key,
            "label": preset.label,
            "level": preset.level,
            "roundOrder": preset.round_order,
            "bestOf": preset.best_of,
            "drawSize": preset.draw_size,
        }
        for preset in PRESETS
    ]


def context_payload(context: MatchContext) -> dict[str, object]:
    return {
        "surface": context.surface,
        "level": context.level,
        "roundOrder": context.round_order,
        "bestOf": context.best_of,
        "drawSize": context.draw_size,
        "restDays": context.rest_days,
        "tourneyMatches": context.tourney_matches,
    }


def decode_context(values: Mapping[str, object]) -> MatchContext:
    return MatchContext(
        surface=str(values["surface"]),
        level=str(values["level"]),
        round_order=int(str(values["roundOrder"])),
        best_of=int(str(values["bestOf"])),
        draw_size=int(str(values["drawSize"])),
        rest_days=float(str(values.get("restDays", NEUTRAL_REST_DAYS))),
        tourney_matches=float(str(values.get("tourneyMatches", 0.0))),
    )


def write_players(
    directory: Path,
    records: Sequence[PlayerRecord],
    pairs: Mapping[str, Sequence[Sequence[int]]],
    data_through: date,
) -> list[Path]:
    players_path = directory / "players.json"
    pairs_path = directory / "h2h.json"
    write_json(players_path, players_payload(records, data_through))
    write_json(pairs_path, {"dataThrough": data_through.isoformat(), "pairs": dict(pairs)})
    return [players_path, pairs_path]


def model_metadata(
    *,
    feature_list: Sequence[str],
    calibration: Calibration,
    trees: int,
    parity_rows: int,
    parity_difference: float,
    float32_difference: float,
    trained_through: date,
    sanity: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "file": "matchpoint.onnx",
        "features": list(feature_list),
        "calibration": calibration.parameters(),
        "presets": presets_payload(),
        "neutralRestDays": NEUTRAL_REST_DAYS,
        "trainedThrough": trained_through.isoformat(),
        "trees": trees,
        "parity": {
            "rows": parity_rows,
            "maxDifference": parity_difference,
            "float32MaxDifference": float32_difference,
        },
        "sanity": list(sanity),
    }
