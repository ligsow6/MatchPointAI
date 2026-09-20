import urllib.error
import urllib.request
from collections.abc import Callable

import pytest

from pipeline.sources import (
    SNAPSHOT_SOURCES,
    UPSTREAM_SOURCE,
    Availability,
    RemoteFileMissingError,
    SourceUnreachableError,
    fetch_bytes,
    probe,
    resolve_match_source,
)

PROBE = "atp_matches_2024.csv"


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *details: object) -> None:
        return None


def responder(behaviour: dict[str, object]) -> Callable[..., FakeResponse]:
    def urlopen(request: urllib.request.Request, timeout: float | None = None) -> FakeResponse:
        for fragment, outcome in behaviour.items():
            if fragment in request.full_url:
                if isinstance(outcome, Exception):
                    raise outcome
                return FakeResponse(
                    outcome if isinstance(outcome, bytes) else str(outcome).encode()
                )
        raise AssertionError(f"URL inattendue : {request.full_url}")

    return urlopen


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test", code, "erreur", {}, None)  # type: ignore[arg-type]


def network_error() -> urllib.error.URLError:
    return urllib.error.URLError("nom de domaine introuvable")


@pytest.fixture
def no_sleep() -> Callable[[float], None]:
    return lambda _: None


def patch_read(monkeypatch: pytest.MonkeyPatch, behaviour: dict[str, object]) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", responder(behaviour))


def test_missing_file_is_distinct_from_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_read(monkeypatch, {"absent": http_error(404), "coupe": network_error()})
    with pytest.raises(RemoteFileMissingError):
        fetch_bytes("https://host/absent", attempts=1)
    with pytest.raises(SourceUnreachableError):
        fetch_bytes("https://host/coupe", attempts=1, sleeper=lambda _: None)


@pytest.mark.parametrize("code", [403, 429, 500, 502])
def test_server_errors_are_not_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch, code: int, no_sleep: Callable[[float], None]
) -> None:
    patch_read(monkeypatch, {"fichier": http_error(code)})
    with pytest.raises(SourceUnreachableError):
        fetch_bytes("https://host/fichier", attempts=1, sleeper=no_sleep)


def test_transient_failure_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def urlopen(request: urllib.request.Request, timeout: float | None = None) -> FakeResponse:
        attempts.append(1)
        if len(attempts) < 3:
            raise network_error()
        return FakeResponse(b"contenu")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    delays: list[float] = []
    assert fetch_bytes("https://host/fichier", attempts=3, sleeper=delays.append) == b"contenu"
    assert len(attempts) == 3
    assert delays == [2.0, 4.0]


def test_a_404_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def urlopen(request: urllib.request.Request, timeout: float | None = None) -> FakeResponse:
        calls.append(request.full_url)
        raise http_error(404)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(RemoteFileMissingError):
        fetch_bytes("https://host/absent", attempts=3, sleeper=lambda _: None)
    assert len(calls) == 1


def test_probe_reports_the_three_states(
    monkeypatch: pytest.MonkeyPatch, no_sleep: Callable[[float], None]
) -> None:
    patch_read(monkeypatch, {UPSTREAM_SOURCE.repository: b"ok"})
    assert probe(UPSTREAM_SOURCE, PROBE, attempts=1, sleeper=no_sleep) is Availability.AVAILABLE
    patch_read(monkeypatch, {UPSTREAM_SOURCE.repository: http_error(404)})
    assert probe(UPSTREAM_SOURCE, PROBE, attempts=1, sleeper=no_sleep) is Availability.MISSING
    patch_read(monkeypatch, {UPSTREAM_SOURCE.repository: network_error()})
    assert probe(UPSTREAM_SOURCE, PROBE, attempts=1, sleeper=no_sleep) is Availability.UNREACHABLE


def test_live_upstream_is_preferred_over_the_snapshot(
    monkeypatch: pytest.MonkeyPatch, no_sleep: Callable[[float], None]
) -> None:
    patch_read(monkeypatch, {UPSTREAM_SOURCE.repository: b"ok"})
    resolution = resolve_match_source(PROBE, attempts=1, sleeper=no_sleep)
    assert resolution.source == UPSTREAM_SOURCE
    assert resolution.source.immutable is False
    assert resolution.upstream is Availability.AVAILABLE
    assert "accessible" in resolution.reason


def test_a_deleted_upstream_falls_back_to_the_pinned_mirror(
    monkeypatch: pytest.MonkeyPatch, no_sleep: Callable[[float], None]
) -> None:
    patch_read(
        monkeypatch,
        {UPSTREAM_SOURCE.repository: http_error(404), SNAPSHOT_SOURCES[0].repository: b"ok"},
    )
    resolution = resolve_match_source(PROBE, attempts=1, sleeper=no_sleep)
    assert resolution.source == SNAPSHOT_SOURCES[0]
    assert resolution.upstream is Availability.MISSING
    assert "404" in resolution.reason


def test_a_network_outage_is_reported_and_not_mistaken_for_a_deletion(
    monkeypatch: pytest.MonkeyPatch, no_sleep: Callable[[float], None]
) -> None:
    patch_read(monkeypatch, {"githubusercontent": network_error()})
    with pytest.raises(SourceUnreachableError, match="réseau"):
        resolve_match_source(PROBE, attempts=1, sleeper=no_sleep)


def test_an_unreachable_upstream_is_flagged_even_when_a_mirror_answers(
    monkeypatch: pytest.MonkeyPatch, no_sleep: Callable[[float], None]
) -> None:
    patch_read(
        monkeypatch,
        {UPSTREAM_SOURCE.repository: http_error(500), SNAPSHOT_SOURCES[0].repository: b"ok"},
    )
    resolution = resolve_match_source(PROBE, attempts=1, sleeper=no_sleep)
    assert resolution.upstream is Availability.UNREACHABLE
    assert "injoignable" in resolution.reason
