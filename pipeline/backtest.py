from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from pipeline import config
from pipeline.calibration import CalibrationChoice, choose_calibration, logit, symmetric_pairs
from pipeline.data import completed_mask
from pipeline.elo import elo_probabilities
from pipeline.metrics import (
    CalibrationBin,
    PairedDifference,
    Scores,
    calibration_bins,
    paired_bootstrap,
    score,
)
from pipeline.model import (
    TrainedModel,
    Trial,
    build_datasets,
    feature_importance,
    predict_winner_probability,
    search_hyperparameters,
    train_with_early_stopping,
)
from pipeline.splits import TEST, TRAIN, VALIDATION, assign_periods

ELO_KEY = "elo"
RECALIBRATED_ELO_KEY = "elo_recalibrated"
MODEL_KEY = "model"
MODEL_LABELS = {
    ELO_KEY: "Elo surface (baseline)",
    RECALIBRATED_ELO_KEY: "Elo recalibré",
    MODEL_KEY: "LightGBM",
}
EXPERIENCE_THRESHOLD = 30
HEADLINE_TRIALS = 30
WALK_FORWARD_TRIALS = 16
WALK_FORWARD_TUNING_YEAR = 2005


@dataclass(frozen=True)
class ModelReport:
    key: str
    label: str
    scores: Scores
    calibration: list[CalibrationBin]


@dataclass(frozen=True)
class Segment:
    dimension: str
    value: str
    matches: int
    scores: dict[str, Scores]


@dataclass(frozen=True)
class PeriodSummary:
    name: str
    start: date
    end: date
    matches: int


@dataclass(frozen=True)
class HeadlineResult:
    periods: list[PeriodSummary]
    reports: list[ModelReport]
    differences: dict[str, list[PairedDifference]]
    segments: list[Segment]
    importance: pd.Series
    model: TrainedModel
    trials: list[Trial]
    calibration: CalibrationChoice
    test_predictions: pd.DataFrame


@dataclass(frozen=True)
class YearResult:
    year: int
    matches: int
    scores: dict[str, Scores]


@dataclass(frozen=True)
class WalkForwardResult:
    tuning: TrainedModel
    years: list[YearResult]
    predictions: pd.DataFrame


def evaluable(matches: pd.DataFrame) -> pd.DataFrame:
    labelled = matches.assign(period=assign_periods(matches["tourney_date"]))
    return labelled.loc[completed_mask(labelled)]


def period_summaries(frames: dict[str, pd.DataFrame]) -> list[PeriodSummary]:
    return [
        PeriodSummary(
            name=name,
            start=frame["tourney_date"].min().date(),
            end=frame["match_date"].max().date(),
            matches=len(frame),
        )
        for name, frame in frames.items()
    ]


def recalibrated_elo(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    """Régression logistique sur l'écart Elo, ajustée uniquement sur la période d'entraînement."""
    train_probabilities, labels = symmetric_pairs(elo_probabilities(train)["elo_blend"])
    regression = LogisticRegression(C=1e6, fit_intercept=False)
    regression.fit(logit(train_probabilities).reshape(-1, 1), labels)
    target_logits = logit(elo_probabilities(target)["elo_blend"]).reshape(-1, 1)
    return np.asarray(regression.predict_proba(target_logits)[:, 1])


def experience_bucket(frame: pd.DataFrame) -> pd.Series:
    least = np.minimum(frame["elo_played_w"], frame["elo_played_l"])
    labels = np.where(
        least < EXPERIENCE_THRESHOLD,
        f"moins de {EXPERIENCE_THRESHOLD} matchs",
        f"{EXPERIENCE_THRESHOLD} matchs ou plus",
    )
    return pd.Series(labels, index=frame.index)


def segment_scores(frame: pd.DataFrame, predictions: dict[str, np.ndarray]) -> list[Segment]:
    dimensions = {
        "surface": frame["surface"],
        "tourney_level": frame["tourney_level"],
        "best_of": frame["best_of"].astype(str),
        "experience": experience_bucket(frame),
    }
    segments: list[Segment] = []
    for dimension, values in dimensions.items():
        for value in sorted(values.unique()):
            members = (values == value).to_numpy()
            segments.append(
                Segment(
                    dimension=dimension,
                    value=str(value),
                    matches=int(members.sum()),
                    scores={
                        key: score(prediction[members]) for key, prediction in predictions.items()
                    },
                )
            )
    return segments


def headline_evaluation(matches: pd.DataFrame, seed: int) -> HeadlineResult:
    """Protocole principal : entraînement jusqu'en 2023, validation 2024, test 2025 et au-delà."""
    labelled = evaluable(matches)
    frames = {name: labelled.loc[labelled["period"] == name] for name in (TRAIN, VALIDATION, TEST)}
    train, validation, test = frames[TRAIN], frames[VALIDATION], frames[TEST]
    model, trials = search_hyperparameters(train, validation, HEADLINE_TRIALS, seed)
    calibration = choose_calibration(predict_winner_probability(model, validation))
    predictions = {
        ELO_KEY: elo_probabilities(test)["elo_blend"],
        RECALIBRATED_ELO_KEY: recalibrated_elo(train, test),
        MODEL_KEY: calibration.transform(predict_winner_probability(model, test)),
    }
    reports = [
        ModelReport(key, MODEL_LABELS[key], score(values), calibration_bins(values))
        for key, values in predictions.items()
    ]
    differences = {
        reference: paired_bootstrap(predictions[MODEL_KEY], predictions[reference], seed)
        for reference in (ELO_KEY, RECALIBRATED_ELO_KEY)
    }
    test_predictions = pd.DataFrame(
        {"match_key": test["match_key"].to_numpy(), **predictions}, index=test.index
    )
    return HeadlineResult(
        periods=period_summaries(frames),
        reports=reports,
        differences=differences,
        segments=segment_scores(test, predictions),
        importance=feature_importance(model),
        model=model,
        trials=trials,
        calibration=calibration,
        test_predictions=test_predictions,
    )


def year_bounds(frame: pd.DataFrame, first: int, last: int) -> pd.Series:
    years = frame["tourney_date"].dt.year
    inside: pd.Series = (years >= first) & (years <= last)
    return inside


def walk_forward(matches: pd.DataFrame, last_year: int, seed: int) -> WalkForwardResult:
    """Backtest annuel : l'année N est prédite par un modèle entraîné sur les saisons < N - 1,
    arrêté en validation sur N - 1, avec des hyperparamètres choisis une seule fois sur 2005."""
    completed = matches.loc[completed_mask(matches)]
    first_train_year = config.TRAIN_START.year
    tuning_train = completed.loc[
        year_bounds(completed, first_train_year, WALK_FORWARD_TUNING_YEAR - 1)
    ]
    tuning_validation = completed.loc[
        year_bounds(completed, WALK_FORWARD_TUNING_YEAR, WALK_FORWARD_TUNING_YEAR)
    ]
    tuning, _ = search_hyperparameters(tuning_train, tuning_validation, WALK_FORWARD_TRIALS, seed)
    years: list[YearResult] = []
    predictions: list[pd.DataFrame] = []
    for year in range(WALK_FORWARD_TUNING_YEAR + 1, last_year + 1):
        train = completed.loc[year_bounds(completed, first_train_year, year - 2)]
        validation = completed.loc[year_bounds(completed, year - 1, year - 1)]
        target = completed.loc[year_bounds(completed, year, year)]
        if target.empty:
            continue
        training_set, validation_set = build_datasets(train, validation)
        model = train_with_early_stopping(tuning.parameters, training_set, validation_set, seed)
        model_probabilities = predict_winner_probability(model, target)
        elo = elo_probabilities(target)["elo_blend"]
        years.append(
            YearResult(
                year=year,
                matches=len(target),
                scores={ELO_KEY: score(elo), MODEL_KEY: score(model_probabilities)},
            )
        )
        predictions.append(
            pd.DataFrame(
                {
                    "match_key": target["match_key"].to_numpy(),
                    ELO_KEY: elo,
                    MODEL_KEY: model_probabilities,
                },
                index=target.index,
            )
        )
    return WalkForwardResult(tuning=tuning, years=years, predictions=pd.concat(predictions))
