"""Barramento de coordenação entre agentes (scripts/agentbus.py): mensagens, reservas e a trava do turno de commit."""
import importlib.util
import time
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("agentbus", Path(__file__).resolve().parents[2] / "scripts" / "agentbus.py")
bus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bus)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "DIR", tmp_path / ".agents")


def test_messages_are_delivered_once_and_broadcast_reaches_everyone(capsys):
    bus.send("claude-motor", "codex", "Primeira linha clara\ndetalhe")
    bus.send("claude-hen", "all", "aviso geral")
    got = bus.inbox("codex", False)
    assert [m["from"] for m in got] == ["claude-motor", "claude-hen"]
    assert bus.inbox("codex", False) == []  # já lidas: não repete
    assert len(bus.inbox("codex", True)) == 2  # --all mostra o histórico
    assert [m["text"] for m in bus.inbox("claude-motor", False)] == ["aviso geral"]  # o remetente não recebe a própria mensagem
    assert "nenhuma mensagem nova" in capsys.readouterr().out


def test_lock_is_exclusive_renewable_and_releasable(capsys):
    assert bus.lock_acquire("codex", "subir X") == 0
    assert bus.lock_acquire("claude-hen", "subir Y") == 1  # ocupada
    assert bus.lock_acquire("codex", "ainda X") == 0  # o dono renova
    assert bus.lock_release("claude-hen") == 1  # só o dono libera
    assert bus.lock_release("codex") == 0
    assert bus.lock_acquire("claude-hen", "agora eu") == 0
    assert bus.lock_status()["holder"] == "claude-hen"
    assert "OCUPADA" in capsys.readouterr().err


def test_stale_lock_does_not_block_forever(monkeypatch):
    assert bus.lock_acquire("codex", "travou e sumiu") == 0
    real = time.time
    monkeypatch.setattr(bus, "_now", lambda: real() + bus.STALE_S + 60)
    assert bus.lock_status() is None  # expirada
    assert bus.lock_acquire("claude-hen", "assumo") == 0


def test_claims_detect_overlap_between_agents(capsys):
    assert bus.claim("codex", ["engine/pulso_engine/pipeline.py", "docs/research/"]) == 0
    assert bus.claim("claude-hen", ["docs/research/SPEC_01.md"]) == 1  # dentro de uma pasta reservada pelo outro
    assert bus.claim("claude-hen", ["engine/pulso_engine/flags.py"]) == 0
    assert bus.claim("codex", ["engine/pulso_engine/pipeline.py"]) == 0  # o próprio dono repetir não conflita
    bus.unclaim("codex", [])
    assert bus.claim("claude-hen", ["docs/research/SPEC_01.md"]) == 0
    assert "CONFLITO" in capsys.readouterr().err


def test_invalid_names_are_rejected():
    for bad in ("", "a/b", "x y", "a" * 50):
        with pytest.raises(SystemExit):
            bus.send(bad, "all", "oi")


def test_who_lists_roster_lock_claims(capsys):
    bus.register("codex", "pesquisa de sensores")
    bus.lock_acquire("codex", "x")
    bus.claim("codex", ["docs/research/"])
    bus.who()
    out = capsys.readouterr().out
    assert "codex" in out and "TRAVA com codex" in out and "docs/research/" in out


def test_claim_keeps_the_dot_of_hidden_folders_and_ignores_dot_slash():
    assert bus.claim("claude-hen", [".github/workflows/", "./README.md"]) == 0
    claims = bus._read(bus.DIR / "claims.json", {})
    assert claims["claude-hen"] == [".github/workflows/", "README.md"]
    assert bus.claim("codex", [".github/workflows/turso-schema.yml"]) == 1  # dentro da pasta reservada
