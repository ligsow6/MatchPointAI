import json
import math
from pathlib import Path
from typing import Any

import pytest

from pipeline.export import (
    ExportValidationError,
    difference_payload,
    feature_description,
    refresh_source_status,
    rounded,
    validate_replay,
    write_json,
)
from pipeline.metrics import PairedDifference
from pipeline.sources import (
    SNAPSHOT_SOURCES,
    UPSTREAM_SOURCE,
    Availability,
    SourceResolution,
    resolution_reason,
)


def replay_document(**overrides: Any) -> dict[str, Any]:
    timeline = [{"n": number, "p": 0.5} for number in range(1, 80)]
    timeline.append({"n": 80, "p": 1.0})
    return {
        "slug": "demo",
        "winner": 0,
        "preMatch": {"model": 0.6, "elo": 0.55},
        "timeline": timeline,
        **overrides,
    }


def test_rounded_rejects_non_finite_values() -> None:
    assert rounded(0.123456, 3) == 0.123
    with pytest.raises(ExportValidationError):
        rounded(math.nan, 3)


def test_difference_payload_flags_significance() -> None:
    payload = difference_payload(
        [
            PairedDifference("log_loss", -0.03, -0.04, -0.02),
            PairedDifference("accuracy", 0.01, -0.001, 0.02),
        ]
    )
    assert payload[0]["metric"] == "logLoss"
    assert payload[0]["significant"] is True
    assert payload[1]["significant"] is False


def test_feature_description_covers_form_features() -> None:
    assert feature_description("surface_form_short_diff") == (
        "form",
        "Écart de forme sur 10 matchs sur la surface",
    )
    assert feature_description("form_long_a") == ("form", "Forme sur 20 matchs toutes surfaces (A)")
    assert feature_description("elo_blend_diff")[0] == "elo"


def test_validate_replay_accepts_consistent_document() -> None:
    validate_replay(replay_document())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"winner": 1}, "finale"),
        ({"timeline": [{"n": 1, "p": 0.5}] * 3}, "trop peu"),
        ({"preMatch": {"model": 1.4}}, "avant-match"),
    ],
)
def test_validate_replay_rejects_inconsistent_document(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ExportValidationError, match=message):
        validate_replay(replay_document(**overrides))


def test_validate_replay_rejects_out_of_range_probability() -> None:
    document = replay_document()
    document["timeline"][5]["p"] = 1.2
    with pytest.raises(ExportValidationError, match="hors"):
        validate_replay(document)


def test_write_json_refuses_nan(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="JSON"):
        write_json(tmp_path / "broken.json", {"value": math.nan})
    write_json(tmp_path / "ok.json", {"value": 0.5, "label": "É"})
    assert json.loads((tmp_path / "ok.json").read_text(encoding="utf-8")) == {
        "value": 0.5,
        "label": "É",
    }


def resolution(upstream: Availability) -> SourceResolution:
    source = UPSTREAM_SOURCE if upstream is Availability.AVAILABLE else SNAPSHOT_SOURCES[0]
    return SourceResolution(source, upstream, resolution_reason(upstream, source))


def published_overview(tmp_path: Path, upstream: Availability) -> Path:
    path = tmp_path / "overview.json"
    write_json(path, {"source": {}, "dataset": {"totalMatches": 12}, "periods": [{"name": "test"}]})
    refresh_source_status(path, resolution(upstream))
    return path


def test_an_unchanged_source_status_leaves_the_overview_untouched(tmp_path: Path) -> None:
    path = published_overview(tmp_path, Availability.MISSING)
    before = path.read_bytes()
    assert refresh_source_status(path, resolution(Availability.MISSING)) is False
    assert path.read_bytes() == before


def test_a_returning_upstream_is_published_without_touching_the_rest(tmp_path: Path) -> None:
    path = published_overview(tmp_path, Availability.MISSING)
    assert refresh_source_status(path, resolution(Availability.AVAILABLE)) is True
    overview = json.loads(path.read_text(encoding="utf-8"))
    assert list(overview) == ["source", "dataset", "periods"]
    assert overview["source"]["upstream"] == "available"
    assert overview["source"]["snapshot"] is False
    assert overview["dataset"] == {"totalMatches": 12}
