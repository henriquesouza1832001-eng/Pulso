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
