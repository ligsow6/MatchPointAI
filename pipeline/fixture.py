import json
import math
from collections.abc import Mapping
from pathlib import Path

from pipeline import config
from pipeline.comparator import comparator_features
from pipeline.export_players import decode_context, decode_record


def case_features(case: Mapping[str, object]) -> dict[str, float | None]:
    """Variables attendues d'un cas de la fixture partagée, calculées par le code Python."""
    player_a = decode_record(dict_of(case["playerA"]))
    player_b = decode_record(dict_of(case["playerB"]))
    wins = [int(str(value)) for value in list_of(case["headToHead"])]
    frame = comparator_features(
        player_a, player_b, decode_context(dict_of(case["context"])), (wins[0], wins[1])
    )
    row = frame.iloc[0]
    return {
        str(name): None if math.isnan(float(value)) else float(value) for name, value in row.items()
    }


def dict_of(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("Objet JSON attendu")
    return {str(key): item for key, item in value.items()}


def list_of(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("Tableau JSON attendu")
    return list(value)


def load_fixture(path: Path) -> dict[str, object]:
    return dict_of(json.loads(path.read_text(encoding="utf-8")))


def regenerate(path: Path) -> None:
    fixture = load_fixture(path)
    for case in list_of(fixture["cases"]):
        entry = dict_of(case)
        if isinstance(case, dict):
            case["expected"] = case_features(entry)
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    regenerate(config.FIXTURE_PATH)
