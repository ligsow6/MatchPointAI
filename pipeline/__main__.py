import argparse
from dataclasses import dataclass
from datetime import date

import pandas as pd

from pipeline import config
from pipeline.backtest import headline_evaluation, walk_forward
from pipeline.data import (
    DatasetSummary,
    clean_matches,
    download_seasons,
    read_raw_matches,
    summarize,
    validate_matches,
)
from pipeline.elo import attach_elo
from pipeline.export import export_all
from pipeline.features import attach_player_features
from pipeline.replay import REPLAY_SELECTIONS, MatchReplay, build_replay
from pipeline.sources import (
    CHARTING_SOURCE,
    RemoteSource,
    download_file,
    resolve_match_source,
)

CHARTING_FILES = ("charting-m-matches.csv",)


@dataclass(frozen=True)
class LoadedMatches:
    matches: pd.DataFrame
    summary: DatasetSummary
    source: RemoteSource


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline", description="MatchPoint data pipeline")
    parser.add_argument("--refresh", action="store_true", help="re-download mutable raw files")
    return parser.parse_args()


def load_matches(refresh: bool, today: date) -> LoadedMatches:
    source = resolve_match_source(config.PROBE_FILENAME)
    print(f"source : {source.repository}@{source.revision}")
    seasons = range(config.FIRST_SEASON, today.year + 1)
    paths = download_seasons(source, seasons, config.RAW_DIR, refresh=refresh)
    raw = read_raw_matches(paths)
    clean = clean_matches(raw)
    validate_matches(clean, today)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(config.PROCESSED_DIR / "matches.csv.gz", index=False)
    return LoadedMatches(clean, summarize(clean, raw_rows=len(raw)), source)


def build_replays(
    matches: pd.DataFrame, predictions: pd.DataFrame, refresh: bool
) -> list[MatchReplay]:
    filenames = {*CHARTING_FILES, *(selection.points_file for selection in REPLAY_SELECTIONS)}
    for filename in sorted(filenames):
        download_file(CHARTING_SOURCE, filename, config.RAW_DIR, refresh=refresh)
    charting_dir = config.RAW_DIR / CHARTING_SOURCE.cache_key()
    return [
        build_replay(selection, matches, predictions, charting_dir)
        for selection in REPLAY_SELECTIONS
    ]


def distinct_players(matches: pd.DataFrame) -> int:
    return int(pd.concat([matches["winner_id"], matches["loser_id"]]).nunique())


def main() -> None:
    arguments = parse_arguments()
    today = date.today()
    loaded = load_matches(arguments.refresh, today)
    print(loaded.summary)
    matches = attach_player_features(attach_elo(loaded.matches))
    headline = headline_evaluation(matches, config.RANDOM_SEED)
    for report in headline.reports:
        print(f"{report.label} : {report.scores}")
    history = walk_forward(matches, last_year=today.year, seed=config.RANDOM_SEED)
    replays = build_replays(matches, history.predictions, arguments.refresh)
    written = export_all(
        config.OUTPUT_DIR,
        summary=loaded.summary,
        source=loaded.source,
        players=distinct_players(loaded.matches),
        headline=headline,
        history=history,
        replays=replays,
    )
    for path in written:
        print(f"écrit : {path.relative_to(config.ROOT_DIR)}")


if __name__ == "__main__":
    main()
