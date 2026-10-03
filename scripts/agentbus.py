#!/usr/bin/env python3
"""Barramento de coordenação entre agentes (Claude, Codex, humanos) que trabalham NA MESMA árvore de arquivos.

Não precisa de rede nem de instalação: só arquivos em `.agents/` (ignorado pelo git) na raiz do repositório.
Cada agente usa o seu NOME (ex.: `claude-hen`, `claude-motor`, `codex`) em todos os comandos.

    py scripts/agentbus.py register <nome> --role "o que faz"      entra no quadro
    py scripts/agentbus.py who                                      quem está ativo, o que faz, quem tem a trava e os arquivos reservados
    py scripts/agentbus.py send <para|all> "mensagem" --from <nome> manda mensagem (a primeira linha deve ser autoexplicativa)
    py scripts/agentbus.py inbox <nome>                             lê (e marca como lida) as mensagens novas; --all mostra tudo
    py scripts/agentbus.py claim <nome> <arquivo-ou-pasta> ...      reserva arquivos que vai editar (avisa se já são de outro)
    py scripts/agentbus.py unclaim <nome> [<arquivo> ...]           libera (sem argumentos, libera tudo do agente)
    py scripts/agentbus.py lock status                              quem tem o TURNO DE COMMIT/PUSH
    py scripts/agentbus.py lock acquire <nome> --note "o que vai subir"   pega o turno (falha se outro está com ele)
    py scripts/agentbus.py lock release <nome>                      devolve o turno

Regra do projeto: só quem tem a trava faz `git add/commit/push` (sempre `git add` por nome de arquivo). A trava expira em 45
minutos sem renovação (agente que travou/fechou não bloqueia os outros). Veja AGENTS.md e docs/agents/COORDENACAO.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = Path(os.environ.get("AGENTBUS_DIR") or ROOT / ".agents")
STALE_S = 45 * 60


def _now() -> float:
    return time.time()


def _stamp(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t or _now()))


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)  # atômico no mesmo volume


def _name(n: str) -> str:
    n = n.strip().lower()
    if not n or any(c in n for c in "/\\ :*?\"<>|") or len(n) > 40:
        raise SystemExit("nome inválido: use letras, números, '-' ou '_' (ex.: codex, claude-motor)")
    return n


# ---------- quadro (roster) ----------
def register(name: str, role: str) -> None:
    name = _name(name)
    roster = _read(DIR / "roster.json", {})
    roster[name] = {"role": role, "since": roster.get(name, {}).get("since", _now()), "seen": _now()}
    _write(DIR / "roster.json", roster)
    print(f"registrado: {name} ({role})")


def _seen(name: str) -> None:
    roster = _read(DIR / "roster.json", {})
    if name in roster:
        roster[name]["seen"] = _now()
        _write(DIR / "roster.json", roster)


# ---------- mensagens ----------
def send(frm: str, to: str, text: str) -> None:
    frm, to = _name(frm), ("all" if to == "all" else _name(to))
    if not text.strip():
        raise SystemExit("mensagem vazia")
    msgs = _read(DIR / "messages.json", [])
    msg = {"id": (msgs[-1]["id"] + 1) if msgs else 1, "at": _now(), "from": frm, "to": to, "text": text.strip(), "read_by": [frm]}
    msgs.append(msg)
    _write(DIR / "messages.json", msgs[-500:])
    _seen(frm)
    print(f"enviada #{msg['id']} para {to}")


def inbox(name: str, show_all: bool) -> list[dict]:
    name = _name(name)
    msgs = _read(DIR / "messages.json", [])
    mine = [m for m in msgs if m["to"] in (name, "all") and (show_all or name not in m["read_by"])]
    for m in mine:
        print(f"--- #{m['id']} {_stamp(m['at'])} de {m['from']} para {m['to']}\n{m['text']}\n")
        if name not in m["read_by"]:
            m["read_by"].append(name)
    if mine and not show_all:
        _write(DIR / "messages.json", msgs)
    if not mine:
        print("(nenhuma mensagem nova)")
    _seen(name)
    return mine


# ---------- reservas de arquivos ----------
def _norm(p: str) -> str:
    """Caminho relativo com barras normais, sem './' inicial. Não usar lstrip('./'): apagaria o ponto de '.github'."""
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _overlap(a: str, b: str) -> bool:
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def claim(name: str, paths: list[str]) -> int:
    name = _name(name)
    claims = _read(DIR / "claims.json", {})
    clash = []
    for p in paths:
        p = _norm(p)
        for owner, owned in claims.items():
            if owner != name and any(_overlap(p, q) for q in owned):
                clash.append((p, owner))
    if clash:
        for p, owner in clash:
            print(f"CONFLITO: {p} já está reservado por {owner}. Combine com ele (send) antes de editar.", file=sys.stderr)
        return 1
    claims.setdefault(name, [])
    for p in paths:
        p = _norm(p)
        if p not in claims[name]:
            claims[name].append(p)
    _write(DIR / "claims.json", claims)
    _seen(name)
    print(f"reservado para {name}: {', '.join(paths)}")
    return 0


def unclaim(name: str, paths: list[str]) -> None:
    name = _name(name)
    claims = _read(DIR / "claims.json", {})
    if not paths:
        claims.pop(name, None)
    else:
        norm = {_norm(p) for p in paths}
        claims[name] = [q for q in claims.get(name, []) if q not in norm]
        if not claims[name]:
            claims.pop(name)
    _write(DIR / "claims.json", claims)
    print("liberado")


# ---------- trava do turno de commit ----------
LOCK = "commit.lock"


def _lock_info() -> dict | None:
    info = _read(DIR / LOCK, None)
    if info and _now() - info.get("at", 0) > STALE_S:
        return None  # expirada
    return info


def lock_status() -> dict | None:
    info = _lock_info()
    if info:
        print(f"TRAVA com {info['holder']} desde {_stamp(info['at'])} ({int((_now() - info['at']) // 60)} min): {info.get('note', '')}")
    else:
        print("TRAVA livre")
    return info


def lock_acquire(name: str, note: str) -> int:
    name = _name(name)
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / LOCK
    info = _lock_info()
    if info and info["holder"] != name:
        print(f"OCUPADA: {info['holder']} está com o turno ({info.get('note', '')}). Peça com send e espere.", file=sys.stderr)
        return 1
    if info and info["holder"] == name:  # renovação
        _write(path, {**info, "at": _now(), "note": note or info.get("note", "")})
        print("trava renovada")
        return 0
    if path.exists():  # expirada: remove antes de recriar
        path.unlink(missing_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # atômico: dois agentes ao mesmo tempo, só um vence
    except FileExistsError:
        print("OCUPADA (corrida): outro agente pegou agora. Tente de novo.", file=sys.stderr)
        return 1
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"holder": name, "at": _now(), "note": note}, f, ensure_ascii=False)
    _seen(name)
    print(f"trava com {name}")
    return 0


def lock_release(name: str, force: bool = False) -> int:
    name = _name(name)
    info = _read(DIR / LOCK, None)
    if not info:
        print("trava já estava livre")
        return 0
    if info["holder"] != name and not force:
        print(f"só {info['holder']} pode liberar (ou use --force se ele sumiu)", file=sys.stderr)
        return 1
    (DIR / LOCK).unlink(missing_ok=True)
    print("trava liberada")
    return 0


def who() -> None:
    roster = _read(DIR / "roster.json", {})
    print("AGENTES:")
    for n, r in sorted(roster.items()):
        idle = int((_now() - r["seen"]) // 60)
        print(f"  {n:<16} {r['role']}  (visto há {idle} min)")
    if not roster:
        print("  (ninguém registrado: use `register`)")
    lock_status()
    claims = _read(DIR / "claims.json", {})
    print("ARQUIVOS RESERVADOS:" + ("" if claims else " nenhum"))
    for n, paths in sorted(claims.items()):
        print(f"  {n}: {', '.join(paths)}")
    msgs = _read(DIR / "messages.json", [])
    print(f"MENSAGENS: {len(msgs)} no total")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agentbus", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("register"); p.add_argument("name"); p.add_argument("--role", default="")
    sub.add_parser("who")
    p = sub.add_parser("send"); p.add_argument("to"); p.add_argument("text"); p.add_argument("--from", dest="frm", required=True)
    p = sub.add_parser("inbox"); p.add_argument("name"); p.add_argument("--all", action="store_true")
    p = sub.add_parser("claim"); p.add_argument("name"); p.add_argument("paths", nargs="+")
    p = sub.add_parser("unclaim"); p.add_argument("name"); p.add_argument("paths", nargs="*")
    p = sub.add_parser("lock"); p.add_argument("action", choices=["status", "acquire", "release"]); p.add_argument("name", nargs="?")
    p.add_argument("--note", default=""); p.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "register":
        register(a.name, a.role)
    elif a.cmd == "who":
        who()
    elif a.cmd == "send":
        send(a.frm, a.to, a.text)
    elif a.cmd == "inbox":
        inbox(a.name, a.all)
    elif a.cmd == "claim":
        return claim(a.name, a.paths)
    elif a.cmd == "unclaim":
        unclaim(a.name, a.paths)
    elif a.cmd == "lock":
        if a.action == "status":
            lock_status()
        elif not a.name:
            raise SystemExit("informe o nome do agente")
        elif a.action == "acquire":
            return lock_acquire(a.name, a.note)
        else:
            return lock_release(a.name, a.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
