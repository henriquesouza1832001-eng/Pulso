"""Confere a conexão com o Turso usando TURSO_URL e TURSO_TOKEN (segredos do ambiente). Nunca imprime o token.

Protocolo: Hrana sobre HTTP (`POST {base}/v2/pipeline`, `Authorization: Bearer`). Só leitura e uma tabela de teste
temporária; serve para validar o protocolo antes de qualquer código de produção depender dele.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

url = os.environ.get("TURSO_URL", "").strip()
raw_token = os.environ.get("TURSO_TOKEN", "")
token = raw_token.strip().strip("\"'").strip()
if token.lower().startswith("bearer "):
    token = token[7:].strip()
# diagnóstico seguro (nunca imprime o token): formato esperado de JWT = 3 partes separadas por ponto, começando com "eyJ"
print("token: comprimento", len(token), "| partes", token.count(".") + 1, "| começa com eyJ:", token.startswith("eyJ"),
      "| espaços/quebras no original:", raw_token != raw_token.strip(), "| aspas:", token[:1] in "\"'" or raw_token.strip()[:1] in "\"'")
if not url or not token:
    sys.exit("TURSO_URL/TURSO_TOKEN ausentes")
base = url.replace("libsql://", "https://").rstrip("/")
print("host:", base.split("//", 1)[-1].split(".")[0][:3] + "***", "|", base.split("//", 1)[-1].split(".", 1)[-1])


def pipeline(statements):
    body = {"requests": [{"type": "execute", "stmt": {"sql": s, **({"args": a} if a else {})}} for s, a in statements] + [{"type": "close"}]}
    req = urllib.request.Request(f"{base}/v2/pipeline", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read(300).decode('utf-8', 'replace')}")
    return data, round((time.time() - t0) * 1000)


data, ms = pipeline([("SELECT 1 AS ok, sqlite_version() AS v", None)])
res = data["results"][0]
print("status:", res["type"], f"({ms} ms)")
cols = [c["name"] for c in res["response"]["result"]["cols"]]
row = [c.get("value") for c in res["response"]["result"]["rows"][0]]
print("select:", dict(zip(cols, row)))

# escrita, leitura e JSON em lote (o formato que o ingest vai usar), numa tabela temporária de teste
data, ms = pipeline([
    ("CREATE TABLE IF NOT EXISTS _pulso_check (k TEXT PRIMARY KEY, v INTEGER)", None),
    ("INSERT INTO _pulso_check (k,v) VALUES ('a',1),('b',2) ON CONFLICT(k) DO UPDATE SET v=excluded.v", None),
    ("SELECT COUNT(*) AS n, SUM(v) AS s FROM _pulso_check", None),
    ("SELECT value FROM json_each(?)", [{"type": "text", "value": json.dumps([1, 2, 3])}]),
    ("DROP TABLE _pulso_check", None),
])
for i, r in enumerate(data["results"][:-1]):
    print(i, r["type"], r.get("response", {}).get("result", {}).get("affected_row_count"), "linhas afetadas" if r["type"] == "ok" else r)
sel = data["results"][2]["response"]["result"]
print("contagem:", [c.get("value") for c in sel["rows"][0]], f"({ms} ms para o lote)")
print("OK: leitura, escrita, upsert e json_each funcionam")


# --- formatos usados pela camada do Worker (apps/worker/src/lib/turso.ts) ---
def raw(requests):
    req = urllib.request.Request(f"{base}/v2/pipeline", data=json.dumps({"requests": requests + [{"type": "close"}]}).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["results"]


T = lambda v: {"type": "text", "value": v}  # noqa: E731
I = lambda v: {"type": "integer", "value": str(v)}  # noqa: E731, E741

# 1) sequence (várias instruções) e parâmetros NUMERADOS (?1, ?2) com a mesma posição reutilizada
r = raw([{"type": "sequence", "sql": "DROP TABLE IF EXISTS _pc2; CREATE TABLE _pc2 (k TEXT PRIMARY KEY, n INTEGER);"}])
assert r[0]["type"] == "ok", r
r = raw([{"type": "execute", "stmt": {"sql": "INSERT INTO _pc2 (k,n) VALUES (?1,?2),(?1||'x',?2)", "args": [T("a"), I(5)]}}])
assert r[0]["type"] == "ok" and r[0]["response"]["result"]["affected_row_count"] == 2, r
print("numerados (?1,?2): ok")


# 2) batch transacional com condições: tudo grava ou nada grava
def txn(stmts):
    n = len(stmts)
    steps = [{"stmt": {"sql": "BEGIN"}}]
    steps += [{"condition": {"type": "ok", "step": i}, "stmt": s} for i, s in enumerate(stmts)]
    steps += [{"condition": {"type": "ok", "step": n}, "stmt": {"sql": "COMMIT"}},
              {"condition": {"type": "not", "cond": {"type": "ok", "step": n + 1}}, "stmt": {"sql": "ROLLBACK"}}]
    res = raw([{"type": "batch", "batch": {"steps": steps}}])[0]["response"]["result"]
    return res["step_results"], res["step_errors"]


ins = lambda k: {"sql": "INSERT INTO _pc2 (k,n) VALUES (?1,1)", "args": [T(k)]}  # noqa: E731
sr, se = txn([ins("p"), ins("q")])
assert all(e is None for e in se[:4]) and sr[3] is not None, (sr, se)
cnt = lambda: int(raw([{"type": "execute", "stmt": {"sql": "SELECT COUNT(*) FROM _pc2"}}])[0]["response"]["result"]["rows"][0][0]["value"])  # noqa: E731
before = cnt()
sr, se = txn([ins("r"), ins("r")])  # a segunda viola a chave primária
assert se[2] is not None and se[4] is None, se[:5]
assert cnt() == before, "o rollback deveria desfazer a primeira inserção"
print("batch transacional e rollback: ok", f"(linhas {before}, sem alteração após o erro)")

# 3) consulta com `rows_written` próximo do que o D1 reporta: o Turso informa só as linhas alteradas
r = raw([{"type": "execute", "stmt": {"sql": "DROP TABLE _pc2"}}])
print("limpeza:", r[0]["type"])
print("OK: o protocolo que a camada do Worker usa funciona no servidor real")
