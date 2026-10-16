import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import config
from pipeline.backtest import HeadlineResult, evaluable, headline_evaluation, walk_forward
from pipeline.data import (
    DatasetSummary,
    clean_matches,
    download_seasons,
    read_raw_matches,
    summarize,
    validate_matches,
)
from pipeline.elo import attach_elo, final_ratings
from pipeline.export import export_all, refresh_source_status, write_json
from pipeline.export_players import (
    head_to_head_records,
    model_metadata,
    player_records,
    read_profiles,
    sanity_cases,
    write_players,
)
from pipeline.features import (
    attach_player_features,
    feature_names,
    loser_perspective,
    replay_history,
    winner_perspective,
)
from pipeline.fingerprint import (
    input_fingerprint,
    must_rebuild,
    pipeline_sources,
    published_fingerprint,
)
from pipeline.onnx_export import export_onnx, trimmed_booster
from pipeline.readme import synchronise
from pipeline.replay import REPLAY_SELECTIONS, MatchReplay, build_replay
from pipeline.sources import (
    CHARTING_SOURCE,
    RemoteFileMissingError,
    RemoteSource,
    SourceResolution,
    download_file,
    resolve_match_source,
)
from pipeline.splits import TEST

CHARTING_FILES = ("charting-m-matches.csv",)
METADATA_PATH = config.MODEL_DIR / "metadata.json"
README_PATH = config.ROOT_DIR / "README.md"


@dataclass(frozen=True)
class LoadedMatches:
    matches: pd.DataFrame
    summary: DatasetSummary
    resolution: SourceResolution
    profiles_path: Path | None
    season_paths: tuple[Path, ...]

    @property
    def source(self) -> RemoteSource:
        return self.resolution.source

    @property
    def files(self) -> list[Path]:
        profiles = [self.profiles_path] if self.profiles_path is not None else []
        return [*self.season_paths, *profiles]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline", description="MatchPoint data pipeline")
    parser.add_argument("--refresh", action="store_true", help="re-download mutable raw files")
    parser.add_argument(
        "--force", action="store_true", help="retrain even when the inputs are unchanged"
    )
    return parser.parse_args()


def download_profiles(source: RemoteSource, refresh: bool) -> Path | None:
    try:
        return download_file(source, config.PLAYERS_FILENAME, config.RAW_DIR, refresh=refresh)
    except RemoteFileMissingError:
        return None


def load_matches(refresh: bool, today: date) -> LoadedMatches:
    resolution = resolve_match_source(config.PROBE_FILENAME)
    source = resolution.source
    print(f"source : {source.repository}@{source.revision} ({resolution.reason})")
    seasons = range(config.FIRST_SEASON, today.year + 1)
    paths = download_seasons(source, seasons, config.RAW_DIR, refresh=refresh)
    raw = read_raw_matches(paths)
    clean = clean_matches(raw)
    validate_matches(clean, today)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(config.PROCESSED_DIR / "matches.csv.gz", index=False)
    summary = summarize(clean, raw_rows=len(raw))
    profiles = download_profiles(source, refresh)
    return LoadedMatches(clean, summary, resolution, profiles, tuple(paths))


def download_charting(refresh: bool) -> list[Path]:
    filenames = {*CHARTING_FILES, *(selection.points_file for selection in REPLAY_SELECTIONS)}
    return [
        download_file(CHARTING_SOURCE, filename, config.RAW_DIR, refresh=refresh)
        for filename in sorted(filenames)
    ]


def build_replays(matches: pd.DataFrame, predictions: pd.DataFrame) -> list[MatchReplay]:
    charting_dir = config.RAW_DIR / CHARTING_SOURCE.cache_key()
    return [
        build_replay(selection, matches, predictions, charting_dir)
        for selection in REPLAY_SELECTIONS
    ]


def distinct_players(matches: pd.DataFrame) -> int:
    return int(pd.concat([matches["winner_id"], matches["loser_id"]]).nunique())


def held_out_features(matches: pd.DataFrame) -> np.ndarray:
    labelled = evaluable(matches)
    test = labelled.loc[labelled["period"] == TEST]
    return pd.concat([winner_perspective(test), loser_perspective(test)]).to_numpy(dtype=float)


def export_comparator(
    loaded: LoadedMatches, matches: pd.DataFrame, headline: HeadlineResult, fingerprint: str
) -> list[Path]:
    """Exporte l'état des joueurs, les face-à-face et le modèle ONNX vérifié à 1e-6 près."""
    data_through = loaded.summary.last_date
    _, history = replay_history(loaded.matches)
    records = player_records(
        loaded.matches, final_ratings(loaded.matches), history, read_profiles(loaded.profiles_path)
    )
    pairs = head_to_head_records(history, {record.player_id for record in records})
    written = write_players(config.OUTPUT_DIR, records, pairs, data_through)
    report = export_onnx(
        headline.model, held_out_features(matches), config.MODEL_DIR / "matchpoint.onnx"
    )
    state = "réécrit" if report.rewritten else "inchangé (prévisions identiques)"
    print(f"ONNX : {report.trees} arbres, écart maximal {report.max_difference:.1e}, {state}")
    booster = trimmed_booster(headline.model)
    sanity = sanity_cases(
        records,
        pairs,
        lambda features: np.asarray(booster.predict(features), dtype=float),
        headline.calibration.transform,
        data_through,
    )
    write_json(
        METADATA_PATH,
        model_metadata(
            feature_list=feature_names(),
            calibration=headline.calibration.transform,
            trees=report.trees,
            parity_rows=report.rows,
            parity_difference=report.max_difference,
            float32_difference=report.float32_difference,
            trained_through=headline.periods[0].end,
            sanity=sanity,
            input_fingerprint=fingerprint,
        ),
    )
    return [*written, report.path, METADATA_PATH]


def keep_published(resolution: SourceResolution) -> list[Path]:
    overview_path = config.OUTPUT_DIR / "overview.json"
    return [overview_path] if refresh_source_status(overview_path, resolution) else []


def rebuild(loaded: LoadedMatches, today: date, fingerprint: str) -> list[Path]:
    matches = attach_player_features(attach_elo(loaded.matches))
    headline = headline_evaluation(matches, config.RANDOM_SEED)
    for report in headline.reports:
        print(f"{report.label} : {report.scores}")
    history = walk_forward(matches, last_year=today.year, seed=config.RANDOM_SEED)
    replays = build_replays(matches, history.predictions)
    written = export_all(
        config.OUTPUT_DIR,
        summary=loaded.summary,
        resolution=loaded.resolution,
        players=distinct_players(loaded.matches),
        headline=headline,
        history=history,
        replays=replays,
    )
    written.extend(export_comparator(loaded, matches, headline, fingerprint))
    return written


def main() -> None:
    arguments = parse_arguments()
    today = date.today()
    loaded = load_matches(arguments.refresh, today)
    print(loaded.summary)
    charting = download_charting(arguments.refresh)
    fingerprint = input_fingerprint([*loaded.files, *charting], pipeline_sources())
    published = published_fingerprint(METADATA_PATH)
    print(f"empreinte des entrées : {fingerprint[:12]}, publiée : {(published or 'aucune')[:12]}")
    if must_rebuild(fingerprint, published, arguments.force):
        written = rebuild(loaded, today, fingerprint)
    else:
        print("entrées inchangées depuis la dernière publication : modèle et données conservés")
        written = keep_published(loaded.resolution)
    if synchronise(README_PATH, config.OUTPUT_DIR):
        written.append(README_PATH)
    for path in written:
        print(f"écrit : {path.relative_to(config.ROOT_DIR)}")


if __name__ == "__main__":
    main()
