import argparse
from datetime import date

from pipeline import config
from pipeline.data import (
    clean_matches,
    download_seasons,
    read_raw_matches,
    summarize,
    validate_matches,
)
from pipeline.sources import resolve_match_source


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline", description="MatchPoint data pipeline")
    parser.add_argument("--refresh", action="store_true", help="re-download mutable raw files")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    today = date.today()
    source = resolve_match_source(config.PROBE_FILENAME)
    print(f"source: {source.repository}@{source.revision}")
    seasons = range(config.FIRST_SEASON, today.year + 1)
    paths = download_seasons(source, seasons, config.RAW_DIR, refresh=arguments.refresh)
    raw = read_raw_matches(paths)
    clean = clean_matches(raw)
    validate_matches(clean, today)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(config.PROCESSED_DIR / "matches.csv.gz", index=False)
    print(summarize(clean, raw_rows=len(raw)))


if __name__ == "__main__":
    main()
