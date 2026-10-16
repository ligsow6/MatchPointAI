import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from pipeline import config

FINGERPRINT_KEY = "inputFingerprint"
CODE_DIR = config.ROOT_DIR / "pipeline"
PROJECT_FILE = config.ROOT_DIR / "pyproject.toml"


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pipeline_sources(code_dir: Path = CODE_DIR, project_file: Path = PROJECT_FILE) -> list[Path]:
    modules = [
        path for path in code_dir.rglob("*.py") if "tests" not in path.relative_to(code_dir).parts
    ]
    return sorted([*modules, project_file])


def input_fingerprint(
    data_files: Iterable[Path], code_files: Iterable[Path], root: Path = config.ROOT_DIR
) -> str:
    """Empreinte SHA-256 des données lues et du code qui les transforme.

    Une donnée est identifiée par son nom et son contenu, pas par son dossier : le même
    fichier servi par un autre miroir donne la même empreinte.
    """
    entries = sorted(
        [(f"donnees/{path.name}", file_digest(path)) for path in data_files]
        + [(f"code/{path.relative_to(root).as_posix()}", file_digest(path)) for path in code_files]
    )
    digest = hashlib.sha256()
    for label, content in entries:
        digest.update(f"{label}\t{content}\n".encode())
    return digest.hexdigest()


def published_fingerprint(metadata_path: Path) -> str | None:
    if not metadata_path.exists():
        return None
    value = json.loads(metadata_path.read_text(encoding="utf-8")).get(FINGERPRINT_KEY)
    return value if isinstance(value, str) else None
