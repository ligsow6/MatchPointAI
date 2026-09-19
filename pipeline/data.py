import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.sources import RemoteFileMissingError, RemoteSource, download_file

SURFACES = ("Hard", "Clay", "Grass")
SURFACE_ALIASES = {"Hard": "Hard", "Clay": "Clay", "Grass": "Grass", "Carpet": "Hard"}
LEVEL_LABELS = {
    "G": "Grand Chelem",
    "M": "Masters 1000",
    "A": "ATP 250/500",
    "F": "Masters de fin d'année",
    "D": "Coupe Davis",
    "O": "Jeux olympiques",
}
ROUND_ORDER = {
    "ER": 0,
    "R128": 1,
    "R64": 2,
    "R32": 3,
    "R16": 4,
    "RR": 5,
    "QF": 6,
    "SF": 7,
    "BR": 8,
    "F": 9,
}
ROUNDS_BEFORE_FINAL = {
    "ER": 5,
    "R128": 6,
    "R64": 5,
    "R32": 4,
    "R16": 3,
    "RR": 3,
    "QF": 2,
    "SF": 1,
    "BR": 0,
    "F": 0,
}
HEIGHT_RANGE_CM = (150.0, 215.0)
AGE_RANGE_YEARS = (14.0, 50.0)
SET_SCORE_PATTERN = re.compile(r"^\d{1,2}-\d{1,2}(\(\d+\))?$|^\[\d{1,2}-\d{1,2}\]$")
WALKOVER_MARKERS = ("W/O", "WALKOVER")
RETIREMENT_MARKERS = ("RET", "DEF", "ABD", "ABANDONED", "UNFINISHED")

PLAYER_COLUMNS = ("id", "name", "hand", "ht", "age", "rank", "rank_points")
SERVE_COLUMNS = ("svpt", "1stWon", "2ndWon")

OUTCOME_COMPLETED = "completed"
OUTCOME_RETIREMENT = "retirement"
OUTCOME_WALKOVER = "walkover"
OUTCOME_UNKNOWN = "unknown"


@dataclass(frozen=True)
class DatasetSummary:
    total_matches: int
    completed_matches: int
    retirements: int
    walkovers: int
    unknown_scores: int
    discarded_rows: int
    first_date: date
    last_date: date


def match_filenames(first_season: int, last_season: int) -> list[str]:
    return [f"atp_matches_{season}.csv" for season in range(first_season, last_season + 1)]


def download_seasons(
    source: RemoteSource, seasons: Iterable[int], cache_dir: Path, refresh: bool
) -> list[Path]:
    paths: list[Path] = []
    for season in seasons:
        try:
            paths.append(
                download_file(source, f"atp_matches_{season}.csv", cache_dir, refresh=refresh)
            )
        except RemoteFileMissingError:
            continue
    return paths


def read_raw_matches(paths: Iterable[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path, low_memory=False) for path in paths]
    if not frames:
        raise ValueError("Aucun fichier de matchs à charger")
    return pd.concat(frames, ignore_index=True)


def classify_outcome(score: object) -> str:
    if not isinstance(score, str) or not score.strip():
        return OUTCOME_UNKNOWN
    normalized = score.strip().upper()
    if any(marker in normalized for marker in WALKOVER_MARKERS):
        return OUTCOME_WALKOVER
    if any(marker in normalized for marker in RETIREMENT_MARKERS):
        return OUTCOME_RETIREMENT
    if all(SET_SCORE_PATTERN.match(token) for token in normalized.split()):
        return OUTCOME_COMPLETED
    return OUTCOME_UNKNOWN


def normalize_surface(surface: object) -> str | None:
    if not isinstance(surface, str):
        return None
    return SURFACE_ALIASES.get(surface.strip().title())


def tournament_final_day(level: str, draw_size: float) -> tuple[float, float]:
    if level == "G":
        return 13.0, 2.0
    if level == "D":
        return 1.0, 0.0
    if level == "M" and draw_size >= 96:
        return 11.0, 1.5
    if level == "O":
        return 8.0, 1.5
    return 6.0, 1.0


def estimated_day_offset(level: str, draw_size: float, round_code: str) -> int:
    final_day, spacing = tournament_final_day(level, draw_size)
    rounds_left = ROUNDS_BEFORE_FINAL.get(round_code, 0)
    return int(max(0.0, final_day - rounds_left * spacing))


def clip_to_range(values: pd.Series, bounds: tuple[float, float]) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.where(numeric.between(*bounds))


def positive_or_missing(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.where(numeric > 0)


def clean_matches(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["tourney_date"] = pd.to_datetime(
        frame["tourney_date"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce"
    )
    frame["surface"] = frame["surface"].map(normalize_surface)
    frame["best_of"] = pd.to_numeric(frame["best_of"], errors="coerce")
    frame["draw_size"] = pd.to_numeric(frame["draw_size"], errors="coerce").fillna(32.0)
    frame["round_order"] = frame["round"].map(ROUND_ORDER)
    frame["outcome"] = frame["score"].map(classify_outcome)

    valid = (
        frame["tourney_date"].notna()
        & frame["best_of"].isin([3, 5])
        & frame["round_order"].notna()
        & frame["winner_id"].notna()
        & frame["loser_id"].notna()
        & (frame["winner_id"] != frame["loser_id"])
        & frame["tourney_level"].isin(list(LEVEL_LABELS))
    )
    frame = frame.loc[valid].copy()

    for side in ("winner", "loser"):
        frame[f"{side}_id"] = frame[f"{side}_id"].astype("int64")
        frame[f"{side}_ht"] = clip_to_range(frame[f"{side}_ht"], HEIGHT_RANGE_CM)
        frame[f"{side}_age"] = clip_to_range(frame[f"{side}_age"], AGE_RANGE_YEARS)
        frame[f"{side}_rank"] = positive_or_missing(frame[f"{side}_rank"])
        frame[f"{side}_rank_points"] = pd.to_numeric(
            frame[f"{side}_rank_points"], errors="coerce"
        ).clip(lower=0)

    offsets = [
        estimated_day_offset(level, draw, round_code)
        for level, draw, round_code in zip(
            frame["tourney_level"], frame["draw_size"], frame["round"], strict=True
        )
    ]
    frame["match_date"] = frame["tourney_date"] + pd.to_timedelta(offsets, unit="D")
    frame["best_of"] = frame["best_of"].astype("int64")
    frame["round_order"] = frame["round_order"].astype("int64")
    frame["match_num"] = pd.to_numeric(frame["match_num"], errors="coerce").fillna(0)
    frame["match_key"] = (
        frame["tourney_id"].astype(str) + "-" + frame["match_num"].astype("int64").astype(str)
    )

    frame = frame.sort_values(
        ["match_date", "tourney_date", "tourney_id", "round_order", "match_num"],
        kind="mergesort",
    )
    frame = frame.drop_duplicates(subset=["match_key", "winner_id", "loser_id"])
    return frame[clean_columns()].reset_index(drop=True)


def clean_columns() -> list[str]:
    base = [
        "match_key",
        "tourney_id",
        "tourney_name",
        "tourney_level",
        "tourney_date",
        "match_date",
        "surface",
        "draw_size",
        "round",
        "round_order",
        "best_of",
        "score",
        "outcome",
    ]
    players = [f"{side}_{column}" for side in ("winner", "loser") for column in PLAYER_COLUMNS]
    serve = [f"{prefix}_{column}" for prefix in ("w", "l") for column in SERVE_COLUMNS]
    return base + players + serve


def summarize(clean: pd.DataFrame, raw_rows: int) -> DatasetSummary:
    outcomes = clean["outcome"].value_counts()
    return DatasetSummary(
        total_matches=len(clean),
        completed_matches=int(outcomes.get(OUTCOME_COMPLETED, 0)),
        retirements=int(outcomes.get(OUTCOME_RETIREMENT, 0)),
        walkovers=int(outcomes.get(OUTCOME_WALKOVER, 0)),
        unknown_scores=int(outcomes.get(OUTCOME_UNKNOWN, 0)),
        discarded_rows=raw_rows - len(clean),
        first_date=clean["tourney_date"].min().date(),
        last_date=clean["match_date"].max().date(),
    )


class DataQualityError(ValueError):
    pass


def date_problems(clean: pd.DataFrame, today: date) -> list[str]:
    problems: list[str] = []
    upper_bound = pd.Timestamp(today) + pd.Timedelta(days=31)
    if clean["tourney_date"].isna().any() or (clean["tourney_date"] > upper_bound).any():
        problems.append("dates de tournoi manquantes ou dans le futur")
    if (clean["tourney_date"] < pd.Timestamp(1967, 12, 1)).any():
        problems.append("dates de tournoi antérieures à l'ère Open")
    if (clean["match_date"] < clean["tourney_date"]).any():
        problems.append("date de match antérieure au début du tournoi")
    if not clean["match_date"].is_monotonic_increasing:
        problems.append("matchs non triés chronologiquement")
    return problems


def player_problems(clean: pd.DataFrame, side: str) -> list[str]:
    checks = {
        f"classement {side} négatif ou nul": (clean[f"{side}_rank"] <= 0).any(),
        f"points {side} négatifs": (clean[f"{side}_rank_points"] < 0).any(),
        f"taille {side} hors bornes": not clean[f"{side}_ht"]
        .dropna()
        .between(*HEIGHT_RANGE_CM)
        .all(),
        f"âge {side} hors bornes": not clean[f"{side}_age"]
        .dropna()
        .between(*AGE_RANGE_YEARS)
        .all(),
    }
    return [message for message, failed in checks.items() if failed]


def structure_problems(clean: pd.DataFrame) -> list[str]:
    checks = {
        "un joueur affronte lui-même": (clean["winner_id"] == clean["loser_id"]).any(),
        "format de match inconnu": not clean["best_of"].isin([3, 5]).all(),
        "identifiants de match dupliqués": clean["match_key"].duplicated().any(),
        "surface inconnue": not clean["surface"].dropna().isin(SURFACES).all(),
    }
    return [message for message, failed in checks.items() if failed]


def validate_matches(clean: pd.DataFrame, today: date) -> None:
    """Rejette un jeu de données contenant des valeurs manifestement aberrantes."""
    problems = [
        *date_problems(clean, today),
        *player_problems(clean, "winner"),
        *player_problems(clean, "loser"),
        *structure_problems(clean),
    ]
    if problems:
        raise DataQualityError("; ".join(problems))


def playing_mask(clean: pd.DataFrame) -> pd.Series:
    return clean["outcome"].isin([OUTCOME_COMPLETED, OUTCOME_RETIREMENT])


def completed_mask(clean: pd.DataFrame) -> pd.Series:
    return (clean["outcome"] == OUTCOME_COMPLETED) & clean["surface"].notna()
