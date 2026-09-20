import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

MINUS = "−"
DASH = "–"
MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
SECTION_HEADING = "## Résultats"
NEXT_HEADING = "## Limites connues"
METRIC_LABELS = (("accuracy", "Exactitude"), ("logLoss", "Log loss"), ("brier", "Brier"))
METRIC_NAMES = {"accuracy": "l'exactitude", "logLoss": "la log loss", "brier": "le Brier"}
REFERENCE_LABELS = {"elo": "Face au Elo", "elo_recalibrated": "Face au Elo recalibré"}
MINIMUM_SEGMENT_MATCHES = 500
SIGNIFICANCE = "de façon statistiquement significative"
EXPERIENCE_LOW = "moins de 30 matchs"
EXPERIENCE_HIGH = "30 matchs ou plus"

Payload = Mapping[str, Any]


class ReadmeStructureError(Exception):
    """Le README ne contient plus les deux titres qui délimitent la section générée."""


def decimal(value: float, digits: int) -> str:
    return f"{value:.{digits}f}".replace("-", MINUS).replace(".", ",")


def signed(value: float, digits: int) -> str:
    return f"{value:+.{digits}f}".replace("-", MINUS).replace(".", ",")


def integer(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def percent(value: float, digits: int = 1) -> str:
    return f"{decimal(value * 100, digits)} %"


def french_date(value: str) -> str:
    moment = date.fromisoformat(value)
    return f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def metric_of(comparison: Payload, key: str) -> Payload:
    for metric in comparison["metrics"]:
        if metric["metric"] == key:
            entry: Payload = metric
            return entry
    raise KeyError(key)


def model_of(performance: Payload, key: str) -> Payload:
    for entry in performance["models"]:
        if entry["key"] == key:
            found: Payload = entry
            return found
    raise KeyError(key)


def period_of(overview: Payload, name: str) -> Payload:
    for entry in overview["periods"]:
        if entry["name"] == name:
            found: Payload = entry
            return found
    raise KeyError(name)


def segment_of(performance: Payload, dimension: str, value: str) -> Payload:
    for entry in performance["segments"]:
        if entry["dimension"] == dimension and entry["value"] == value:
            found: Payload = entry
            return found
    raise KeyError(value)


def difference_cell(metric: Payload) -> str:
    scale, digits, unit = (100.0, 1, " pt") if metric["metric"] == "accuracy" else (1.0, 3, "")
    bounds = " ; ".join(signed(float(metric[side]) * scale, digits) for side in ("lower", "upper"))
    return f"{signed(float(metric['mean']) * scale, digits)}{unit} [{bounds}]"


def models_table(models: Sequence[Payload]) -> str:
    lines = [
        "| Modèle | Exactitude | Log loss | Brier | Erreur de calibration |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for entry in models:
        cells = [
            str(entry["label"]),
            percent(float(entry["accuracy"])),
            decimal(float(entry["logLoss"]), 4),
            decimal(float(entry["brier"]), 4),
            percent(float(entry["calibrationError"])),
        ]
        if entry["key"] == "model":
            cells = [f"**{cell}**" for cell in cells]
        lines.append(f"| {' | '.join(cells)} |")
    return "\n".join(lines)


def differences_table(comparisons: Sequence[Payload]) -> str:
    columns = [REFERENCE_LABELS[str(entry["reference"])] for entry in comparisons]
    lines = [
        f"| Métrique | {' | '.join(columns)} |",
        f"| --- | {' | '.join('---' for _ in columns)} |",
    ]
    for key, label in METRIC_LABELS:
        cells = [difference_cell(metric_of(entry, key)) for entry in comparisons]
        lines.append(f"| {label} | {' | '.join(cells)} |")
    return "\n".join(lines)


def significance_clause(comparison: Payload) -> str:
    names = [
        METRIC_NAMES[key] for key, _ in METRIC_LABELS if metric_of(comparison, key)["significant"]
    ]
    if len(names) == len(METRIC_LABELS):
        return f"LightGBM bat la baseline {SIGNIFICANCE} sur les trois métriques"
    if not names:
        return f"LightGBM ne bat la baseline {SIGNIFICANCE} sur aucune métrique"
    listed = " et ".join([", ".join(names[:-1]), names[-1]] if len(names) > 1 else names)
    return f"LightGBM ne bat la baseline {SIGNIFICANCE} que sur {listed}"


def calibration_clause(performance: Payload) -> str:
    baseline = float(model_of(performance, "elo")["logLoss"])
    recalibrated = float(model_of(performance, "elo_recalibrated")["logLoss"])
    model = float(model_of(performance, "model")["logLoss"])
    total = baseline - model
    if total <= 0:
        return "Le gain en log loss ne vient pas d'une meilleure calibration"
    share = (baseline - recalibrated) / total
    return (
        f"{percent(share, 0)} du gain en log loss vient simplement d'une meilleure calibration "
        "(le Elo classique est trop sûr de lui) ; le reste est une information "
        "que le Elo seul ne capte pas"
    )


def seasons_clause(yearly: Sequence[Payload]) -> str:
    won = sum(1 for year in yearly if year["model"]["logLoss"] < year["elo"]["logLoss"])
    span = f"{yearly[0]['year']}{DASH}{yearly[-1]['year']}"
    scope = (
        f"les {len(yearly)} saisons" if won == len(yearly) else f"{won} des {len(yearly)} saisons"
    )
    return (
        f"Sur le backtest annuel {span}, LightGBM obtient une meilleure log loss "
        f"que le Elo sur {scope}"
    )


def weakness_clause(performance: Payload) -> str:
    levels = [
        entry
        for entry in performance["segments"]
        if entry["dimension"] == "tourney_level"
        and int(entry["matches"]) >= MINIMUM_SEGMENT_MATCHES
        and float(entry["model"]["accuracy"]) < float(entry["elo"]["accuracy"])
    ]
    if not levels:
        return (
            "Il fait au moins aussi bien que le Elo sur tous les niveaux de tournoi "
            f"comptant au moins {integer(MINIMUM_SEGMENT_MATCHES)} matchs de test."
        )
    weakest = min(
        levels, key=lambda entry: float(entry["model"]["accuracy"] - entry["elo"]["accuracy"])
    )
    return (
        f"En revanche, il fait légèrement moins bien que le Elo en {weakest['label']} "
        f"({percent(float(weakest['model']['accuracy']))} contre "
        f"{percent(float(weakest['elo']['accuracy']))} d'exactitude "
        f"sur {integer(int(weakest['matches']))} matchs)."
    )


def experience_sentence(performance: Payload) -> str:
    low = segment_of(performance, "experience", EXPERIENCE_LOW)
    high = segment_of(performance, "experience", EXPERIENCE_HIGH)
    return (
        "Quand l'un des deux joueurs compte moins de 30 matchs en base "
        f"({integer(int(low['matches']))} matchs de test), l'exactitude vaut "
        f"{percent(float(low['model']['accuracy']))}, contre "
        f"{percent(float(high['model']['accuracy']))} sinon."
    )


def meaning_paragraph(performance: Payload) -> str:
    comparison = performance["comparisons"][0]
    gain = float(metric_of(comparison, "accuracy")["mean"])
    missed = 1.0 - float(model_of(performance, "model")["accuracy"])
    return (
        f"**Ce que ça signifie.** {significance_clause(comparison)}, mais le gain reste modeste : "
        f"{decimal(gain * 100, 1)} point d'exactitude, et {percent(missed, 0)} "
        "des matchs restent mal prédits. "
        f"{calibration_clause(performance)}. {seasons_clause(performance['yearly'])}. "
        f"{weakness_clause(performance)} {experience_sentence(performance)}"
    )


def results_section(performance: Payload, overview: Payload) -> str:
    test = period_of(overview, "test")
    blocks = [
        SECTION_HEADING,
        f"Période de test : {integer(int(test['matches']))} matchs, "
        f"du {french_date(str(test['start']))} au {french_date(str(test['end']))}.",
        models_table(performance["models"]),
        f"Écart LightGBM {MINUS} Elo, avec intervalle de confiance à 95 % "
        "(bootstrap apparié, 2 000 tirages) :",
        differences_table(performance["comparisons"]),
        meaning_paragraph(performance),
    ]
    return "\n\n".join(blocks) + "\n\n"


def render(document: str, section: str) -> str:
    start = document.find(SECTION_HEADING)
    end = document.find(NEXT_HEADING)
    if start < 0 or end <= start:
        raise ReadmeStructureError(
            f"titres « {SECTION_HEADING} » et « {NEXT_HEADING} » introuvables"
        )
    return document[:start] + section + document[end:]


def synchronise(readme_path: Path, output_dir: Path) -> bool:
    """Réécrit la section Résultats du README à partir des fichiers publiés."""
    payloads = [
        json.loads((output_dir / name).read_text(encoding="utf-8"))
        for name in ("performance.json", "overview.json")
    ]
    document = readme_path.read_text(encoding="utf-8")
    updated = render(document, results_section(payloads[0], payloads[1]))
    if updated == document:
        return False
    readme_path.write_text(updated, encoding="utf-8")
    return True
