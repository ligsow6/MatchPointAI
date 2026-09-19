import argparse
from datetime import date

import pandas as pd

from pipeline import config
from pipeline.data import (
    clean_matches,
    completed_mask,
    download_seasons,
    read_raw_matches,
    summarize,
    validate_matches,
)
from pipeline.elo import attach_elo, elo_probabilities
from pipeline.metrics import score
from pipeline.sources import resolve_match_source
from pipeline.splits import TEST, assign_periods


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


def report_baseline(matches: pd.DataFrame) -> None:
    evaluated = completed_mask(matches) & (assign_periods(matches["tourney_date"]) == TEST)
    selection = evaluated.to_numpy()
    for name, probabilities in elo_probabilities(matches).items():
        print(f"{name}: {score(probabilities[selection])}")


def main() -> None:
    arguments = parse_arguments()
    matches = attach_elo(load_matches(arguments.refresh, date.today()))
    report_baseline(matches)


if __name__ == "__main__":
    main()
