"""Verificação de saúde da produção (rota pública /api/health). Sai com código 1 se algo estiver errado.

Uso: py -m pulso_engine.healthcheck [URL_BASE]     (padrão: PULSO_API_URL ou a API de produção)
Roda a cada 30 min no GitHub (.github/workflows/healthcheck.yml): workflow que falha avisa o dono do repositório.
Só lê rotas públicas; não usa nenhum segredo.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

DEFAULT_BASE = "https://pulso-api.henriquesouza.workers.dev"
MAX_COLLECTION_AGE_S = 30 * 60  # a coleta roda a cada 5 min: 30 min sem pulso é falha, não atraso
MAX_OFFLINE_RATIO = 0.5  # mais da metade das fontes OFFLINE: algo geral (rede, bloqueio, deploy quebrado)
MIN_ONLINE_RATIO = 0.4  # entre as fontes que já reportaram, ao menos 40% ONLINE


def evaluate(health: dict) -> list[str]:
    """Lista de problemas encontrados (vazia = saudável). Função pura, testável."""
    problems: list[str] = []
    if health.get("api") != "ONLINE":
        problems.append(f"API não está ONLINE ({health.get('api')})")
    if health.get("db") != "ONLINE":
        problems.append(f"banco de dados não está ONLINE ({health.get('db')})")
    coll = health.get("collection") or {}
    age = coll.get("age_seconds")
    if age is None:
        problems.append("a coleta nunca gravou um pulso")
    elif age > MAX_COLLECTION_AGE_S:
        problems.append(f"coleta parada há {int(age // 60)} min (limite {MAX_COLLECTION_AGE_S // 60} min)")
    sources = health.get("sources") or []
    reported = [s for s in sources if s.get("status") != "UNKNOWN"]
    if reported:
        offline = sum(1 for s in reported if s["status"] == "OFFLINE")
        online = sum(1 for s in reported if s["status"] == "ONLINE")
        if offline / len(reported) > MAX_OFFLINE_RATIO:
            problems.append(f"{offline} de {len(reported)} fontes OFFLINE")
        if online / len(reported) < MIN_ONLINE_RATIO:
            problems.append(f"só {online} de {len(reported)} fontes ONLINE")
    auth = [s["source_id"] for s in reported if s.get("status") == "AUTH_ERROR"]
    if auth:
        problems.append("erro de autenticação em: " + ", ".join(auth[:5]) + " (não insistir; checar credenciais)")
    return problems


def fetch(base: str) -> dict:
    req = urllib.request.Request(f"{base.rstrip('/')}/api/health",
                                 headers={"User-Agent": "pulso-healthcheck/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - URL de configuração do próprio projeto
        return json.loads(resp.read())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    base = argv[0] if argv else os.environ.get("PULSO_API_URL", DEFAULT_BASE)
    try:
        health = fetch(base)
    except Exception as exc:  # noqa: BLE001
        print(f"FALHA: não foi possível ler {base}/api/health: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    problems = evaluate(health)
    sources = health.get("sources") or []
    online = sum(1 for s in sources if s.get("status") == "ONLINE")
    print(f"fontes: {online} ONLINE de {len(sources)}; coleta há {(health.get('collection') or {}).get('age_seconds')} s")
    if problems:
        for p in problems:
            print(f"PROBLEMA: {p}", file=sys.stderr)
        return 1
    print("saudável")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
