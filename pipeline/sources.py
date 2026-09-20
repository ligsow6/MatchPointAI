import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
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
ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0


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
    """Le serveur a répondu : ce fichier n'existe pas (HTTP 404)."""


class SourceUnreachableError(Exception):
    """Aucune réponse exploitable : réseau coupé, délai dépassé, quota ou erreur serveur."""


class Availability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class SourceResolution:
    source: RemoteSource
    upstream: Availability
    reason: str


def read_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload: bytes = response.read()
            return payload
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise RemoteFileMissingError(f"{url} : HTTP 404") from error
        raise SourceUnreachableError(f"{url} : HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise SourceUnreachableError(f"{url} : {error.reason}") from error
    except TimeoutError as error:
        raise SourceUnreachableError(f"{url} : délai dépassé") from error


def fetch_bytes(
    url: str, attempts: int = ATTEMPTS, sleeper: Callable[[float], None] = time.sleep
) -> bytes:
    """Télécharge une URL en réessayant les erreurs transitoires, jamais un 404."""
    last_error: SourceUnreachableError | None = None
    for attempt in range(attempts):
        try:
            return read_url(url)
        except SourceUnreachableError as error:
            last_error = error
            if attempt + 1 < attempts:
                sleeper(RETRY_DELAY_SECONDS * (attempt + 1))
    raise last_error if last_error else SourceUnreachableError(url)


def probe(
    source: RemoteSource,
    probe_filename: str,
    attempts: int = ATTEMPTS,
    sleeper: Callable[[float], None] = time.sleep,
) -> Availability:
    """Distingue une source vivante, un fichier réellement absent et une panne de réseau."""
    try:
        fetch_bytes(source.url(probe_filename), attempts=attempts, sleeper=sleeper)
    except RemoteFileMissingError:
        return Availability.MISSING
    except SourceUnreachableError:
        return Availability.UNREACHABLE
    return Availability.AVAILABLE


def resolution_reason(upstream: Availability, source: RemoteSource) -> str:
    if upstream is Availability.AVAILABLE:
        return "dépôt d'origine accessible"
    origin = (
        "le dépôt d'origine répond 404"
        if upstream is Availability.MISSING
        else "le dépôt d'origine est injoignable"
    )
    return f"{origin}, repli sur l'instantané épinglé {source.repository}@{source.revision[:7]}"


def resolve_match_source(
    probe_filename: str,
    attempts: int = ATTEMPTS,
    sleeper: Callable[[float], None] = time.sleep,
) -> SourceResolution:
    """Préfère toujours le dépôt d'origine ; ne se replie que si une autre source répond."""
    upstream = probe(UPSTREAM_SOURCE, probe_filename, attempts=attempts, sleeper=sleeper)
    if upstream is Availability.AVAILABLE:
        reason = resolution_reason(upstream, UPSTREAM_SOURCE)
        return SourceResolution(UPSTREAM_SOURCE, upstream, reason)
    for mirror in SNAPSHOT_SOURCES:
        status = probe(mirror, probe_filename, attempts=attempts, sleeper=sleeper)
        if status is Availability.AVAILABLE:
            return SourceResolution(mirror, upstream, resolution_reason(upstream, mirror))
    raise SourceUnreachableError(
        "Aucune source de résultats ATP n'a répondu, y compris les miroirs : "
        "le réseau est probablement indisponible"
    )


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
