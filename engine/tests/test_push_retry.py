import io
import json
import urllib.error

import pytest

from pulso_engine import client


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://w/api/ingest", code, "x", {}, io.BytesIO(body))


def run(monkeypatch, outcomes):
    calls = {"n": 0, "sleeps": []}
    monkeypatch.setattr(client.time, "sleep", lambda s: calls["sleeps"].append(s))

    def urlopen(req, timeout=0):
        out = outcomes[min(calls["n"], len(outcomes) - 1)]
        calls["n"] += 1
        if isinstance(out, Exception):
            raise out
        return _Resp(json.dumps(out).encode())

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    return calls


def push():
    return client.push_batch({"batch_id": "b"}, base_url="https://w", token="segredo")


def test_transient_5xx_and_network_errors_are_retried_then_succeed(monkeypatch):
    calls = run(monkeypatch, [http_error(503), urllib.error.URLError("timed out"), {"ok": True}])
    assert push() == {"ok": True} and calls["n"] == 3 and calls["sleeps"] == [2.0, 5.0]


def test_gives_up_after_the_retries_and_surfaces_the_last_error(monkeypatch):
    calls = run(monkeypatch, [http_error(502)])
    with pytest.raises(client.PushError) as exc:
        push()
    assert exc.value.status == 502 and calls["n"] == 3


def test_invalid_batch_is_not_retried_and_shows_the_reason_without_the_token(monkeypatch):
    calls = run(monkeypatch, [http_error(400, b'{"error":"invalid_batch","detail":"Too big: expected array to have <=100 items"}')])
    with pytest.raises(client.PushError) as exc:
        push()
    assert calls["n"] == 1 and calls["sleeps"] == []
    assert "invalid_batch" in str(exc.value) and "<=100 items" in str(exc.value) and "segredo" not in str(exc.value)


def test_auth_error_is_not_retried(monkeypatch):
    calls = run(monkeypatch, [http_error(401, b'{"error":"unauthorized"}')])
    with pytest.raises(client.PushError):
        push()
    assert calls["n"] == 1


def test_missing_token_fails_fast(monkeypatch):
    monkeypatch.delenv("PULSO_INGEST_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="PULSO_INGEST_TOKEN"):
        client.push_batch({"batch_id": "b"}, base_url="https://w")
