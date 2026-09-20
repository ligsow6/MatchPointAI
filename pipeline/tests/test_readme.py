import json
from pathlib import Path
from typing import Any

import pytest

from pipeline import config
from pipeline.readme import (
    ReadmeStructureError,
    render,
    results_section,
    synchronise,
)


def scores(accuracy: float, log_loss: float, brier: float, calibration: float) -> dict[str, Any]:
    return {
        "matches": 4140,
        "accuracy": accuracy,
        "logLoss": log_loss,
        "brier": brier,
        "calibrationError": calibration,
    }


def metrics(
    accuracy: float, log_loss: float, brier: float, significant: bool
) -> list[dict[str, Any]]:
    return [
        {
            "metric": "accuracy",
            "mean": accuracy,
            "lower": 0.0064,
            "upper": 0.02887,
            "significant": significant,
        },
        {
            "metric": "logLoss",
            "mean": log_loss,
            "lower": -0.04048,
            "upper": -0.02309,
            "significant": significant,
        },
        {
            "metric": "brier",
            "mean": brier,
            "lower": -0.01565,
            "upper": -0.0086,
            "significant": significant,
        },
    ]


def segment(
    dimension: str, value: str, label: str, *, matches: int, model: float, elo: float
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "value": value,
        "label": label,
        "matches": matches,
        "elo": scores(elo, 0.66011, 0.23138, 0.08512),
        "model": scores(model, 0.62398, 0.21862, 0.04199),
    }


@pytest.fixture
def performance() -> dict[str, Any]:
    return {
        "models": [
            {
                "key": "elo",
                "label": "Elo surface (baseline)",
                **scores(0.64771, 0.63424, 0.22079, 0.05198),
            },
            {
                "key": "elo_recalibrated",
                "label": "Elo recalibré",
                **scores(0.64771, 0.62444, 0.21779, 0.01941),
            },
            {"key": "model", "label": "LightGBM", **scores(0.66498, 0.60247, 0.20869, 0.01723)},
        ],
        "comparisons": [
            {"reference": "elo", "metrics": metrics(0.01727, -0.03177, -0.0121, True)},
            {"reference": "elo_recalibrated", "metrics": metrics(0.01727, -0.02197, -0.0091, True)},
        ],
        "yearly": [
            {
                "year": 2006,
                "elo": scores(0.68, 0.5941, 0.2, 0.03),
                "model": scores(0.69, 0.56831, 0.19, 0.02),
            },
            {
                "year": 2007,
                "elo": scores(0.68, 0.5941, 0.2, 0.03),
                "model": scores(0.69, 0.56831, 0.19, 0.02),
            },
        ],
        "segments": [
            segment("tourney_level", "M", "Masters 1000", matches=1156, model=0.63062, elo=0.63668),
            segment("tourney_level", "G", "Grand Chelem", matches=717, model=0.70, elo=0.68898),
            segment(
                "experience",
                "moins de 30 matchs",
                "Moins de 30 matchs",
                matches=1277,
                model=0.65858,
                elo=0.63,
            ),
            segment(
                "experience",
                "30 matchs ou plus",
                "30 matchs ou plus",
                matches=2863,
                model=0.66783,
                elo=0.65,
            ),
        ],
    }


@pytest.fixture
def overview() -> dict[str, Any]:
    return {
        "periods": [
            {"name": "train", "start": "1991-01-07", "end": "2023-12-03", "matches": 101868},
            {"name": "test", "start": "2025-01-06", "end": "2026-06-07", "matches": 4140},
        ]
    }


def test_the_section_reports_the_published_figures(
    performance: dict[str, Any], overview: dict[str, Any]
) -> None:
    section = results_section(performance, overview)
    assert "4 140 matchs, du 6 janvier 2025 au 7 juin 2026" in section
    assert "| **LightGBM** | **66,5 %** | **0,6025** | **0,2087** | **1,7 %** |" in section
    assert "| Elo surface (baseline) | 64,8 % | 0,6342 | 0,2208 | 5,2 % |" in section
    assert "+1,7 pt [+0,6 ; +2,9]" in section
    assert "−0,032 [−0,040 ; −0,023]" in section
    assert "1,7 point d'exactitude" in section


def test_the_commentary_follows_the_numbers(
    performance: dict[str, Any], overview: dict[str, Any]
) -> None:
    section = results_section(performance, overview)
    assert "significative sur les trois métriques" in section
    assert "les 2 saisons" in section
    assert "moins bien que le Elo en Masters 1000 (63,1 % contre 63,7 %" in section
    assert "l'exactitude vaut 65,9 %, contre 66,8 % sinon" in section


def test_a_lost_advantage_is_stated_instead_of_claimed(
    performance: dict[str, Any], overview: dict[str, Any]
) -> None:
    performance["comparisons"][0]["metrics"][0]["significant"] = False
    performance["yearly"][1]["model"]["logLoss"] = 0.9
    performance["segments"][0]["model"]["accuracy"] = 0.99
    section = results_section(performance, overview)
    assert "que sur la log loss et le Brier" in section
    assert "sur 1 des 2 saisons" in section
    assert "au moins aussi bien que le Elo sur tous les niveaux" in section


def test_only_the_results_section_is_rewritten() -> None:
    document = "# Titre\n\nAvant.\n\n## Résultats\n\nAncien.\n\n## Limites connues\n\nAprès.\n"
    updated = render(document, "## Résultats\n\nNouveau.\n\n")
    assert (
        updated == "# Titre\n\nAvant.\n\n## Résultats\n\nNouveau.\n\n## Limites connues\n\nAprès.\n"
    )


def test_a_missing_heading_is_an_error_rather_than_a_silent_append() -> None:
    with pytest.raises(ReadmeStructureError):
        render("# Titre\n\n## Résultats\n\nAncien.\n", "## Résultats\n\nNouveau.\n\n")


def test_synchronising_twice_changes_nothing(
    tmp_path: Path, performance: dict[str, Any], overview: dict[str, Any]
) -> None:
    (tmp_path / "performance.json").write_text(json.dumps(performance), encoding="utf-8")
    (tmp_path / "overview.json").write_text(json.dumps(overview), encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("## Résultats\n\nAncien.\n\n## Limites connues\n\nFin.\n", encoding="utf-8")
    assert synchronise(readme, tmp_path) is True
    assert synchronise(readme, tmp_path) is False


def test_the_published_readme_matches_the_published_data() -> None:
    document = (config.ROOT_DIR / "README.md").read_text(encoding="utf-8")
    published = [
        json.loads((config.OUTPUT_DIR / name).read_text(encoding="utf-8"))
        for name in ("performance.json", "overview.json")
    ]
    assert render(document, results_section(published[0], published[1])) == document, (
        "les chiffres du README ne correspondent plus aux fichiers publiés : "
        "relancer le pipeline régénère la section Résultats"
    )
