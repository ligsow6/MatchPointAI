import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

UPSTREAM_REPOSITORY = "JeffSackmann/tennis_atp"
UPSTREAM_BRANCH = "master"
SNAPSHOT_COMMIT = "712be0c5ade693cdab9e69c23a71a0edf5a23c44"
SNAPSHOT_MIRRORS = (
    "Kadantte/tennis_atp",
    "racketbracket/tennis_atp",
    "srcde/tennis_atp",
    "jnish23/tennis_atp",
    "hartct/tennis_atp",
)
CHARTING_REPOSITORY = "JeffSackmann/tennis_MatchChartingProject"
CHARTING_BRANCH = "master"
RAW_HOST = "https://raw.githubusercontent.com"
USER_AGENT = "matchpoint-pipeline/1.0"
TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class RemoteSource:
    repository: str
    revision: str
    immutable: bool

    def url(self, filename: str) -> str:
        return f"{RAW_HOST}/{self.repository}/{self.revision}/{filename}"

    def cache_key(self) -> str:
        return f"{self.repository.replace('/', '__')}__{self.revision[:12]}"


UPSTREAM_SOURCE = RemoteSource(UPSTREAM_REPOSITORY, UPSTREAM_BRANCH, immutable=False)
SNAPSHOT_SOURCES = tuple(
    RemoteSource(mirror, SNAPSHOT_COMMIT, immutable=True) for mirror in SNAPSHOT_MIRRORS
)
CHARTING_SOURCE = RemoteSource(CHARTING_REPOSITORY, CHARTING_BRANCH, immutable=False)


class RemoteFileMissingError(Exception):
    pass


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload: bytes = response.read()
            return payload
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise RemoteFileMissingError(url) from error
        raise


def is_available(source: RemoteSource, probe_filename: str) -> bool:
    try:
        fetch_bytes(source.url(probe_filename))
    except (RemoteFileMissingError, urllib.error.URLError):
        return False
    return True


def resolve_match_source(probe_filename: str) -> RemoteSource:
    for candidate in (UPSTREAM_SOURCE, *SNAPSHOT_SOURCES):
        if is_available(candidate, probe_filename):
            return candidate
    raise RuntimeError("Aucune source de résultats ATP n'est accessible")


def download_file(source: RemoteSource, filename: str, cache_dir: Path, refresh: bool) -> Path:
    target = cache_dir / source.cache_key() / filename
    if target.exists() and (source.immutable or not refresh):
        return target
    payload = fetch_bytes(source.url(filename))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return target
