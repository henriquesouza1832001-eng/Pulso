"""Copia o D1 para o Turso: aplica as migrations (esquema) e importa os dados de um dump do D1.

Uso (no CI, com TURSO_URL/TURSO_TOKEN nos segredos):
    npx wrangler d1 export pulso --remote --no-schema --output dump.sql
    py engine/scripts/turso_migrate.py [dump.sql]

Idempotente: migrations já aplicadas são puladas (tabela `_pulso_migrations`) e os dados entram com INSERT OR REPLACE.
Nunca imprime o token. Termina com erro se a contagem de linhas por tabela não bater com o dump.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
url = os.environ.get("TURSO_URL", "").strip()
token = os.environ.get("TURSO_TOKEN", "").strip().strip("\"'").strip()
if not url or not token:
    sys.exit("TURSO_URL/TURSO_TOKEN ausentes")
base = url.replace("libsql://", "https://").rstrip("/")
SKIP_TABLES = {"d1_migrations", "_cf_KV", "sqlite_sequence", "_pulso_migrations"}
CHUNK_BYTES = 600_000


def call(requests):
    body = json.dumps({"requests": requests + [{"type": "close"}]}).encode()
    req = urllib.request.Request(f"{base}/v2/pipeline", data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())["results"]
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read(300).decode('utf-8', 'replace')}")
    for x in res[:-1]:
        if x["type"] != "ok":
            sys.exit(f"erro do Turso: {x['error']['message'][:300]}")
    return res


def scalar(sql):
    r = call([{"type": "execute", "stmt": {"sql": sql}}])[0]["response"]["result"]["rows"]
    return int(r[0][0]["value"]) if r else 0


# 1) esquema: as mesmas migrations do D1, uma vez cada
call([{"type": "execute", "stmt": {"sql": "CREATE TABLE IF NOT EXISTS _pulso_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"}}])
applied = {row[0]["value"] for row in call([{"type": "execute", "stmt": {"sql": "SELECT name FROM _pulso_migrations"}}])[0]["response"]["result"]["rows"]}
for f in sorted((ROOT / "database/migrations").glob("*.sql")):
    if f.name in applied:
        print("migration já aplicada:", f.name)
        continue
    call([{"type": "sequence", "sql": f.read_text(encoding="utf-8")},
          {"type": "execute", "stmt": {"sql": "INSERT INTO _pulso_migrations (name, applied_at) VALUES (?1, datetime('now'))", "args": [{"type": "text", "value": f.name}]}}])
    print("migration aplicada:", f.name)

# 2) dados: dump do D1 (uma instrução por linha), em lotes, com INSERT OR REPLACE
dump = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if dump is None or not dump.exists():
    print("sem dump: só o esquema foi aplicado")
    sys.exit(0)
expected = Counter()
batch, size = [], 0


def flush():
    global batch, size
    if batch:
        call([{"type": "sequence", "sql": "\n".join(batch)}])
        batch, size = [], 0


stmt_re = re.compile(r'^INSERT INTO\s+"?([A-Za-z0-9_]+)"?\s', re.I)
for line in dump.read_text(encoding="utf-8").splitlines():
    m = stmt_re.match(line)
    if not m or m.group(1) in SKIP_TABLES:
        continue
    expected[m.group(1)] += 1
    s = re.sub(r"^INSERT INTO", "INSERT OR REPLACE INTO", line, count=1, flags=re.I)
    batch.append(s)
    size += len(s)
    if size >= CHUNK_BYTES:
        flush()
flush()

# 3) conferência: cada tabela do dump tem, no Turso, pelo menos as linhas do dump (o Turso pode ter mais, se o Worker já gravou)
bad = []
for table, n in sorted(expected.items()):
    have = scalar(f'SELECT COUNT(*) FROM "{table}"')
    print(f"{table}: dump {n} | turso {have}")
    if have < n:
        bad.append(table)
if bad:
    sys.exit(f"contagem menor que o dump em: {bad}")
print("OK: esquema e dados copiados para o Turso")
