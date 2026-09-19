import math

import pytest

from pipeline import config
from pipeline.features import feature_names
from pipeline.fixture import case_features, dict_of, list_of, load_fixture

CASES = [dict_of(case) for case in list_of(load_fixture(config.FIXTURE_PATH)["cases"])]


def test_fixture_covers_missing_values_and_all_surfaces() -> None:
    surfaces = {dict_of(case["context"])["surface"] for case in CASES}
    assert surfaces == {"Hard", "Clay", "Grass"}
    assert any(value is None for case in CASES for value in dict_of(case["expected"]).values())


@pytest.mark.parametrize("case", CASES, ids=[str(case["name"]) for case in CASES])
def test_python_features_match_the_shared_fixture(case: dict[str, object]) -> None:
    expected = dict_of(case["expected"])
    computed = case_features(case)
    assert list(expected) == feature_names()
    assert list(computed) == feature_names()
    for name, value in expected.items():
        observed = computed[name]
        if value is None:
            assert observed is None or math.isnan(observed), name
        else:
            assert observed == pytest.approx(float(str(value)), rel=1e-12, abs=1e-12), name
