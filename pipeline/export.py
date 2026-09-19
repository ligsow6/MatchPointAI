import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline import elo, model
from pipeline.backtest import WALK_FORWARD_TUNING_YEAR, HeadlineResult, WalkForwardResult
from pipeline.data import LEVEL_LABELS, DatasetSummary
from pipeline.metrics import CalibrationBin, PairedDifference, Scores
from pipeline.replay import MatchReplay, PointEvent
from pipeline.sources import SNAPSHOT_COMMIT, RemoteSource

PROBABILITY_DIGITS = 4
METRIC_DIGITS = 5
PERIOD_LABELS = {"train": "Entraînement", "validation": "Validation", "test": "Test"}
SURFACE_LABELS = {"Hard": "Dur", "Clay": "Terre battue", "Grass": "Gazon"}
SEGMENT_TITLES = {
    "surface": "Surface",
    "tourney_level": "Niveau du tournoi",
    "best_of": "Format",
    "experience": "Expérience du joueur le moins capé",
}
FEATURE_FAMILIES = {
    "elo": "Elo (global et surface)",
    "rank": "Classement et points ATP",
    "form": "Forme récente",
    "serve": "Service et retour",
    "h2h": "Face-à-face",
    "rest": "Repos et fatigue",
    "profile": "Profil (âge, taille, main)",
    "experience": "Expérience (matchs joués)",
    "context": "Contexte (surface, niveau, tour, format)",
}
FEATURE_LABELS = {
    "elo_blend_diff": ("elo", "Écart Elo combiné global + surface"),
    "elo_diff": ("elo", "Écart Elo global"),
    "surface_elo_diff": ("elo", "Écart Elo sur la surface"),
    "elo_a": ("elo", "Elo global du joueur A"),
    "elo_b": ("elo", "Elo global du joueur B"),
    "surface_elo_a": ("elo", "Elo surface du joueur A"),
    "surface_elo_b": ("elo", "Elo surface du joueur B"),
    "log_rank_ratio": ("rank", "Rapport des classements ATP (log)"),
    "log_points_ratio": ("rank", "Rapport des points ATP (log)"),
    "rank_a": ("rank", "Classement du joueur A"),
    "rank_b": ("rank", "Classement du joueur B"),
    "rank_points_a": ("rank", "Points ATP du joueur A"),
    "rank_points_b": ("rank", "Points ATP du joueur B"),
    "h2h_share": ("h2h", "Part des victoires en face-à-face"),
    "h2h_wins_a": ("h2h", "Victoires en face-à-face du joueur A"),
    "h2h_wins_b": ("h2h", "Victoires en face-à-face du joueur B"),
    "rest_days_diff": ("rest", "Écart de jours de repos"),
    "rest_days_a": ("rest", "Jours de repos du joueur A"),
    "rest_days_b": ("rest", "Jours de repos du joueur B"),
    "tourney_matches_a": ("rest", "Matchs déjà joués dans le tournoi (A)"),
    "tourney_matches_b": ("rest", "Matchs déjà joués dans le tournoi (B)"),
    "serve_won_diff": ("serve", "Écart de points gagnés au service"),
    "return_won_diff": ("serve", "Écart de points gagnés au retour"),
    "serve_won_a": ("serve", "Points gagnés au service (A)"),
    "serve_won_b": ("serve", "Points gagnés au service (B)"),
    "return_won_a": ("serve", "Points gagnés au retour (A)"),
    "return_won_b": ("serve", "Points gagnés au retour (B)"),
    "age_diff": ("profile", "Écart d'âge"),
    "age_a": ("profile", "Âge du joueur A"),
    "age_b": ("profile", "Âge du joueur B"),
    "height_diff": ("profile", "Écart de taille"),
    "left_handed_a": ("profile", "Gaucher (A)"),
    "left_handed_b": ("profile", "Gaucher (B)"),
    "elo_played_a": ("experience", "Matchs joués en carrière (A)"),
    "elo_played_b": ("experience", "Matchs joués en carrière (B)"),
    "surface_played_a": ("experience", "Matchs joués sur la surface (A)"),
    "surface_played_b": ("experience", "Matchs joués sur la surface (B)"),
    "surface": ("context", "Surface"),
    "tourney_level": ("context", "Niveau du tournoi"),
    "round_order": ("context", "Tour"),
    "best_of": ("context", "Format (3 ou 5 sets)"),
    "draw_size": ("context", "Taille du tableau"),
}
FORM_PREFIXES = ("form_", "surface_form_")


class ExportValidationError(ValueError):
    pass


def rounded(value: float, digits: int) -> float:
    if not math.isfinite(value):
        raise ExportValidationError("Valeur non finie dans l'export")
    return round(float(value), digits)


def feature_description(name: str) -> tuple[str, str]:
    if name in FEATURE_LABELS:
        return FEATURE_LABELS[name]
    if name.startswith(FORM_PREFIXES):
        scope = "sur la surface" if name.startswith("surface_") else "toutes surfaces"
        window = "10" if "_short" in name else "20"
        side = {"a": " (A)", "b": " (B)"}.get(name.rsplit("_", 1)[-1], "")
        kind = "Écart de forme" if name.endswith("_diff") else "Forme"
        return "form", f"{kind} sur {window} matchs {scope}{side}"
    return "context", name


def scores_payload(scores: Scores) -> dict[str, Any]:
    return {
        "matches": scores.matches,
        "accuracy": rounded(scores.accuracy, METRIC_DIGITS),
        "logLoss": rounded(scores.log_loss, METRIC_DIGITS),
        "brier": rounded(scores.brier, METRIC_DIGITS),
        "calibrationError": rounded(scores.calibration_error, METRIC_DIGITS),
    }


def calibration_payload(bins: Sequence[CalibrationBin]) -> list[dict[str, Any]]:
    return [
        {
            "lower": rounded(item.lower, 2),
            "upper": rounded(item.upper, 2),
            "matches": item.matches,
            "predicted": rounded(item.mean_predicted, PROBABILITY_DIGITS),
            "observed": rounded(item.observed, PROBABILITY_DIGITS),
        }
        for item in bins
    ]


def difference_payload(differences: Sequence[PairedDifference]) -> list[dict[str, Any]]:
    return [
        {
            "metric": {"log_loss": "logLoss"}.get(item.metric, item.metric),
            "mean": rounded(item.mean, METRIC_DIGITS),
            "lower": rounded(item.lower, METRIC_DIGITS),
            "upper": rounded(item.upper, METRIC_DIGITS),
            "significant": item.lower > 0 or item.upper < 0,
        }
        for item in differences
    ]


def segment_label(dimension: str, value: str) -> str:
    if dimension == "surface":
        return SURFACE_LABELS.get(value, value)
    if dimension == "tourney_level":
        return LEVEL_LABELS.get(value, value)
    if dimension == "best_of":
        return f"Au meilleur des {value} sets"
    return value[0].upper() + value[1:]


def overview_payload(
    summary: DatasetSummary, source: RemoteSource, headline: HeadlineResult, players: int
) -> dict[str, Any]:
    return {
        "source": {
            "repository": source.repository,
            "revision": source.revision,
            "snapshot": source.revision == SNAPSHOT_COMMIT,
        },
        "dataset": {
            "totalMatches": summary.total_matches,
            "completedMatches": summary.completed_matches,
            "retirements": summary.retirements,
            "walkovers": summary.walkovers,
            "unknownScores": summary.unknown_scores,
            "discardedRows": summary.discarded_rows,
            "players": players,
            "firstDate": summary.first_date.isoformat(),
            "lastDate": summary.last_date.isoformat(),
        },
        "periods": [
            {
                "name": period.name,
                "label": PERIOD_LABELS[period.name],
                "start": period.start.isoformat(),
                "end": period.end.isoformat(),
                "matches": period.matches,
            }
            for period in headline.periods
        ],
    }


def performance_payload(headline: HeadlineResult, history: WalkForwardResult) -> dict[str, Any]:
    return {
        "models": [
            {
                "key": report.key,
                "label": report.label,
                **scores_payload(report.scores),
                "calibration": calibration_payload(report.calibration),
            }
            for report in headline.reports
        ],
        "comparisons": [
            {"reference": reference, "metrics": difference_payload(differences)}
            for reference, differences in headline.differences.items()
        ],
        "yearly": [
            {
                "year": year.year,
                "matches": year.matches,
                **{key: scores_payload(value) for key, value in year.scores.items()},
            }
            for year in history.years
        ],
        "segments": [
            {
                "dimension": segment.dimension,
                "title": SEGMENT_TITLES[segment.dimension],
                "value": segment.value,
                "label": segment_label(segment.dimension, segment.value),
                "matches": segment.matches,
                **{key: scores_payload(value) for key, value in segment.scores.items()},
            }
            for segment in headline.segments
        ],
    }


def importance_payload(importance: pd.Series) -> dict[str, Any]:
    features = [
        {"name": str(name), "family": family, "label": label, "share": rounded(float(share), 5)}
        for name, share in importance.items()
        for family, label in [feature_description(str(name))]
    ]
    families: dict[str, float] = {}
    for name, share in importance.items():
        family = feature_description(str(name))[0]
        families[family] = families.get(family, 0.0) + float(share)
    return {
        "features": features,
        "families": sorted(
            (
                {"key": key, "label": FEATURE_FAMILIES[key], "share": rounded(share, 5)}
                for key, share in families.items()
            ),
            key=lambda item: -float(item["share"]),
        ),
    }


def model_payload(headline: HeadlineResult, history: WalkForwardResult) -> dict[str, Any]:
    return {
        "elo": {
            "initialRating": elo.INITIAL_RATING,
            "kNumerator": elo.K_NUMERATOR,
            "kOffset": elo.K_OFFSET,
            "kShape": elo.K_SHAPE,
            "surfaceWeight": elo.SURFACE_WEIGHT,
        },
        "gradientBoosting": {
            "library": "LightGBM",
            "hyperparameters": headline.model.parameters,
            "trees": headline.model.rounds,
            "trials": len(headline.trials),
            "searchSpace": {name: list(values) for name, values in model.SEARCH_SPACE.items()},
            "validationLogLoss": rounded(headline.model.validation_log_loss, METRIC_DIGITS),
            "calibration": {
                "chosen": headline.calibration.name,
                "candidates": {
                    name: rounded(value, METRIC_DIGITS)
                    for name, value in headline.calibration.cross_fitted_log_loss.items()
                },
            },
        },
        "walkForward": {
            "tuningYear": WALK_FORWARD_TUNING_YEAR,
            "hyperparameters": history.tuning.parameters,
            "firstYear": history.years[0].year,
            "lastYear": history.years[-1].year,
        },
        "importance": importance_payload(headline.importance),
    }


def score_line(replay: MatchReplay) -> str:
    parts: list[str] = []
    winner = replay.winner
    for games, tiebreak in zip(replay.set_scores, replay.tiebreak_scores, strict=True):
        own, opposing = games[winner], games[1 - winner]
        suffix = f"({min(tiebreak)})" if tiebreak else ""
        parts.append(f"{own}-{opposing}{suffix}")
    return " ".join(parts)


def short_name(full_name: str) -> str:
    return full_name.split(" ", 1)[-1]


def replay_summary(replay: MatchReplay) -> dict[str, Any]:
    selection = replay.selection
    return {
        "slug": selection.slug,
        "title": selection.title,
        "date": replay.match_date,
        "surface": SURFACE_LABELS.get(replay.surface, replay.surface),
        "players": list(replay.players),
        "shortNames": [short_name(player) for player in replay.players],
        "winner": replay.winner,
        "score": score_line(replay),
        "points": len(replay.events),
        "preMatch": {
            key: rounded(value, PROBABILITY_DIGITS) for key, value in replay.pre_match.items()
        },
        "outOfSample": True,
    }


def point_payload(event: PointEvent) -> dict[str, Any]:
    return {
        "n": event.number,
        "server": event.server,
        "winner": event.winner,
        "p": rounded(event.probability, PROBABILITY_DIGITS),
        "sets": list(event.sets),
        "games": list(event.games),
        "points": list(event.points),
        "tiebreak": event.tiebreak,
        "opportunities": list(event.opportunities),
        "outcome": event.outcome,
    }


def french_decimal(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def ordinal(number: int) -> str:
    return "1er" if number == 1 else f"{number}e"


def saved_label(count: int) -> str:
    return "1re" if count == 1 else f"{count}e"


def set_moment(replay: MatchReplay, event: PointEvent, index: int) -> dict[str, Any]:
    names = [short_name(player) for player in replay.players]
    games = replay.set_scores[index]
    own, opposing = games[event.winner], games[1 - event.winner]
    return {
        "n": event.number,
        "kind": "set",
        "text": f"{names[event.winner]} remporte le {ordinal(index + 1)} set {own}-{opposing}.",
    }


def lowest_moment(replay: MatchReplay, winner_view: list[float]) -> dict[str, Any] | None:
    lowest_index = min(range(len(winner_view)), key=lambda index: winner_view[index])
    if lowest_index == 0:
        return None
    name = short_name(replay.players[replay.winner])
    chance = french_decimal(winner_view[lowest_index] * 100)
    return {
        "n": replay.events[lowest_index - 1].number,
        "kind": "low",
        "text": f"Point le plus bas pour {name}, futur vainqueur : {chance} % de chances.",
    }


def swing_moments(replay: MatchReplay, probabilities: list[float]) -> list[dict[str, Any]]:
    names = [short_name(player) for player in replay.players]
    swings = sorted(
        range(1, len(probabilities)),
        key=lambda index: -abs(probabilities[index] - probabilities[index - 1]),
    )[:3]
    moments: list[dict[str, Any]] = []
    for index in sorted(swings):
        change = (probabilities[index] - probabilities[index - 1]) * 100
        beneficiary = names[0] if change > 0 else names[1]
        moments.append(
            {
                "n": replay.events[index - 1].number,
                "kind": "swing",
                "text": f"Bascule : +{french_decimal(abs(change))} points de probabilité "
                f"pour {beneficiary}.",
            }
        )
    return moments


def key_moments(replay: MatchReplay) -> list[dict[str, Any]]:
    loser = 1 - replay.winner
    winner_name = short_name(replay.players[replay.winner])
    probabilities = [replay.pre_match["model"], *(event.probability for event in replay.events)]
    winner_view = [p if replay.winner == 0 else 1 - p for p in probabilities]
    moments: list[dict[str, Any]] = []
    lowest = lowest_moment(replay, winner_view)
    if lowest is not None:
        moments.append(lowest)
    saved = 0
    completed_sets = 0
    for event in replay.events:
        if f"match_point_{loser}" in event.opportunities and event.winner == replay.winner:
            saved += 1
            moments.append(
                {
                    "n": event.number,
                    "kind": "saved",
                    "text": f"{saved_label(saved)} balle de match sauvée par {winner_name}.",
                }
            )
        if event.outcome in ("set", "match"):
            moments.append(set_moment(replay, event, completed_sets))
            completed_sets += 1
    moments.extend(swing_moments(replay, probabilities))
    return sorted(moments, key=lambda moment: (moment["n"], moment["kind"]))


def replay_payload(replay: MatchReplay) -> dict[str, Any]:
    return {
        **replay_summary(replay),
        "format": {
            "bestOf": replay.match_format.best_of,
            "finalSet": replay.match_format.final_set.value,
        },
        "sets": [list(games) for games in replay.set_scores],
        "tiebreaks": [list(points) if points else None for points in replay.tiebreak_scores],
        "serveWin": [rounded(value, PROBABILITY_DIGITS) for value in replay.serve_win],
        "tourServeWin": rounded(replay.tour_serve_win, PROBABILITY_DIGITS),
        "firstServer": replay.events[0].server,
        "timeline": [point_payload(event) for event in replay.events],
        "moments": key_moments(replay),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExportValidationError(message)


def is_probability(value: object) -> bool:
    return isinstance(value, float | int) and 0.0 <= float(value) <= 1.0


def validate_scores(payload: Mapping[str, Any], context: str) -> None:
    for key in ("accuracy", "logLoss", "brier", "calibrationError"):
        require(key in payload, f"{context} : métrique {key} absente")
    require(is_probability(payload["accuracy"]), f"{context} : exactitude hors [0, 1]")
    require(is_probability(payload["brier"]), f"{context} : Brier hors [0, 1]")
    require(payload["logLoss"] > 0, f"{context} : log loss non positive")
    require(payload["matches"] > 0, f"{context} : aucun match")


def validate_performance(payload: Mapping[str, Any]) -> None:
    keys = [item["key"] for item in payload["models"]]
    require(keys == ["elo", "elo_recalibrated", "model"], "modèles attendus absents")
    for item in payload["models"]:
        validate_scores(item, item["key"])
        require(len(item["calibration"]) > 0, f"{item['key']} : calibration vide")
        for point in item["calibration"]:
            require(is_probability(point["predicted"]), "calibration hors [0, 1]")
            require(is_probability(point["observed"]), "calibration hors [0, 1]")
    years = [item["year"] for item in payload["yearly"]]
    require(years == sorted(years) and len(years) > 0, "backtest annuel vide ou non trié")
    for item in payload["yearly"]:
        validate_scores(item["elo"], f"année {item['year']}")
        validate_scores(item["model"], f"année {item['year']}")
    require(len(payload["segments"]) > 0, "segments absents")


def validate_replay(payload: Mapping[str, Any]) -> None:
    timeline = payload["timeline"]
    require(len(timeline) > 50, f"{payload['slug']} : trop peu de points")
    require(all(is_probability(point["p"]) for point in timeline), "probabilité hors [0, 1]")
    numbers = [point["n"] for point in timeline]
    require(numbers == sorted(numbers), f"{payload['slug']} : points non ordonnés")
    final = timeline[-1]["p"]
    require(final == (1.0 if payload["winner"] == 0 else 0.0), "probabilité finale incohérente")
    require(all(is_probability(value) for value in payload["preMatch"].values()), "avant-match")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
    )
    path.write_text(text + "\n", encoding="utf-8")


def export_all(
    output_dir: Path,
    *,
    summary: DatasetSummary,
    source: RemoteSource,
    players: int,
    headline: HeadlineResult,
    history: WalkForwardResult,
    replays: Sequence[MatchReplay],
) -> list[Path]:
    """Écrit les fichiers JSON consommés par le site après validation de leur contenu."""
    performance = performance_payload(headline, history)
    validate_performance(performance)
    replay_payloads = [replay_payload(replay) for replay in replays]
    for payload in replay_payloads:
        validate_replay(payload)
    files: dict[Path, object] = {
        output_dir / "overview.json": overview_payload(summary, source, headline, players),
        output_dir / "performance.json": performance,
        output_dir / "model.json": model_payload(headline, history),
        output_dir / "replays" / "index.json": [replay_summary(replay) for replay in replays],
    }
    for replay_data in replay_payloads:
        files[output_dir / "replays" / f"{replay_data['slug']}.json"] = replay_data
    for path, content in files.items():
        write_json(path, content)
    return list(files)
