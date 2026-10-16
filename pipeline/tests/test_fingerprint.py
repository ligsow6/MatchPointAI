import json
from pathlib import Path

from pipeline import config
from pipeline.fingerprint import (
    FINGERPRINT_KEY,
    input_fingerprint,
    must_rebuild,
    pipeline_sources,
    published_fingerprint,
)


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_identical_inputs_give_identical_fingerprints(tmp_path: Path) -> None:
    data = [write(tmp_path / "miroir" / "atp_matches_2024.csv", "a,b\n1,2\n")]
    code = [write(tmp_path / "pipeline" / "model.py", "x = 1\n")]
    assert input_fingerprint(data, code, tmp_path) == input_fingerprint(data, code, tmp_path)


def test_any_data_change_changes_the_fingerprint(tmp_path: Path) -> None:
    data = write(tmp_path / "miroir" / "atp_matches_2024.csv", "a,b\n1,2\n")
    code = [write(tmp_path / "pipeline" / "model.py", "x = 1\n")]
    before = input_fingerprint([data], code, tmp_path)
    write(data, "a,b\n1,3\n")
    assert input_fingerprint([data], code, tmp_path) != before


def test_any_code_change_changes_the_fingerprint(tmp_path: Path) -> None:
    data = [write(tmp_path / "miroir" / "atp_matches_2024.csv", "a,b\n1,2\n")]
    code = write(tmp_path / "pipeline" / "model.py", "x = 1\n")
    before = input_fingerprint(data, [code], tmp_path)
    write(code, "x = 2\n")
    assert input_fingerprint(data, [code], tmp_path) != before


def test_the_same_file_from_another_mirror_keeps_the_fingerprint(tmp_path: Path) -> None:
    code = [write(tmp_path / "pipeline" / "model.py", "x = 1\n")]
    first = write(tmp_path / "Kadantte__tennis_atp" / "atp_matches_2024.csv", "a,b\n1,2\n")
    second = write(tmp_path / "srcde__tennis_atp" / "atp_matches_2024.csv", "a,b\n1,2\n")
    assert input_fingerprint([first], code, tmp_path) == input_fingerprint([second], code, tmp_path)


def test_a_renamed_file_changes_the_fingerprint(tmp_path: Path) -> None:
    code = [write(tmp_path / "pipeline" / "model.py", "x = 1\n")]
    first = write(tmp_path / "miroir" / "atp_matches_2024.csv", "a,b\n1,2\n")
    second = write(tmp_path / "miroir" / "atp_matches_2025.csv", "a,b\n1,2\n")
    assert input_fingerprint([first], code, tmp_path) != input_fingerprint([second], code, tmp_path)


def test_the_order_of_the_inputs_does_not_matter(tmp_path: Path) -> None:
    code = [write(tmp_path / "pipeline" / "model.py", "x = 1\n")]
    first = write(tmp_path / "miroir" / "atp_matches_2024.csv", "a\n1\n")
    second = write(tmp_path / "miroir" / "atp_matches_2025.csv", "a\n2\n")
    assert input_fingerprint([first, second], code, tmp_path) == input_fingerprint(
        [second, first], code, tmp_path
    )


def test_the_tracked_code_excludes_tests_and_includes_dependencies(tmp_path: Path) -> None:
    module = write(tmp_path / "pipeline" / "model.py", "x = 1\n")
    nested = write(tmp_path / "pipeline" / "comparator" / "rules.py", "y = 1\n")
    write(tmp_path / "pipeline" / "tests" / "test_model.py", "z = 1\n")
    project = write(tmp_path / "pyproject.toml", "[project]\n")
    assert pipeline_sources(tmp_path / "pipeline", project) == sorted([module, nested, project])


def test_the_real_pipeline_code_is_tracked() -> None:
    names = {path.relative_to(config.ROOT_DIR).as_posix() for path in pipeline_sources()}
    assert {"pipeline/model.py", "pipeline/features.py", "pyproject.toml"} <= names
    assert not any(name.startswith("pipeline/tests/") for name in names)


def test_published_fingerprint_is_read_from_the_metadata(tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.json"
    assert published_fingerprint(metadata) is None
    metadata.write_text(json.dumps({"trees": 12}), encoding="utf-8")
    assert published_fingerprint(metadata) is None
    metadata.write_text(json.dumps({FINGERPRINT_KEY: "abc"}), encoding="utf-8")
    assert published_fingerprint(metadata) == "abc"


def test_the_model_is_rebuilt_only_for_new_inputs_or_on_request() -> None:
    assert must_rebuild("abc", "abc", force=False) is False
    assert must_rebuild("abc", "abd", force=False) is True
    assert must_rebuild("abc", None, force=False) is True
    assert must_rebuild("abc", "abc", force=True) is True
