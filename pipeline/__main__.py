import argparse
from datetime import date

import pandas as pd

from pipeline import config
from pipeline.backtest import HeadlineResult, WalkForwardResult, headline_evaluation, walk_forward
from pipeline.data import (
    clean_matches,
    download_seasons,
    read_raw_matches,
    summarize,
    validate_matches,
)
from pipeline.elo import attach_elo
from pipeline.features import attach_player_features
from pipeline.sources import resolve_match_source


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline", description="MatchPoint data pipeline")
    parser.add_argument("--refresh", action="store_true", help="re-download mutable raw files")
    return parser.parse_args()


def load_matches(refresh: bool, today: date) -> pd.DataFrame:
    source = resolve_match_source(config.PROBE_FILENAME)
    print(f"source: {source.repository}@{source.revision}")
    seasons = range(config.FIRST_SEASON, today.year + 1)
    paths = download_seasons(source, seasons, config.RAW_DIR, refresh=refresh)
    raw = read_raw_matches(paths)
    clean = clean_matches(raw)
    validate_matches(clean, today)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(config.PROCESSED_DIR / "matches.csv.gz", index=False)
    print(summarize(clean, raw_rows=len(raw)))
    return clean


def report(headline: HeadlineResult, history: WalkForwardResult) -> None:
    for model_report in headline.reports:
        print(f"{model_report.label}: {model_report.scores}")
    for reference, differences in headline.differences.items():
        print(f"LightGBM - {reference}: {differences}")
    print(f"calibration: {headline.calibration.name} {headline.calibration.cross_fitted_log_loss}")
    print(f"hyperparamètres: {headline.model.parameters} ({headline.model.rounds} arbres)")
    for year in history.years:
        print(year.year, {key: round(value.log_loss, 4) for key, value in year.scores.items()})


def main() -> None:
    arguments = parse_arguments()
    today = date.today()
    matches = attach_player_features(attach_elo(load_matches(arguments.refresh, today)))
    headline = headline_evaluation(matches, config.RANDOM_SEED)
    history = walk_forward(matches, last_year=today.year, seed=config.RANDOM_SEED)
    report(headline, history)


if __name__ == "__main__":
    main()
