"""Confere se as chaves de Reddit, X e Bluesky funcionam. Só lê; mostra SÓ contagens e o estado (o log do repositório é público).

Lê os segredos do ambiente (REDDIT_CLIENT_ID/SECRET/USER_AGENT, X_BEARER_TOKEN, BLUESKY_HANDLE/APP_PASSWORD). Rede sem
chave aparece como "sem chave" e não conta como erro. Sai com código 1 se alguma chave existente for recusada.
"""
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulso_engine.collectors.social.common import USER_AGENT, SocialAPIError, request_json  # noqa: E402

failed = False


def report(net, fn):
    global failed
    try:
        print(f"{net}: OK ({fn()})")
    except SocialAPIError as e:
        failed = True
        hint = {"AUTH_ERROR": "chave recusada: confira o valor e se a conta/app foi aprovada", "RATE_LIMITED": "limite de uso atingido: tente depois"}.get(e.health_status, "serviço indisponível")
        print(f"{net}: FALHOU, HTTP {e.status} ({e.health_status}); {hint}")
    except Exception as e:  # noqa: BLE001
        failed = True
        print(f"{net}: FALHOU ({type(e).__name__})")


def reddit():
    cid, sec = os.environ["REDDIT_CLIENT_ID"], os.environ["REDDIT_CLIENT_SECRET"]
    agent = os.environ.get("REDDIT_USER_AGENT") or USER_AGENT
    basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    tok = request_json("https://www.reddit.com/api/v1/access_token", {"Authorization": f"Basic {basic}", "User-Agent": agent, "Content-Type": "application/x-www-form-urlencoded"}, b"grant_type=client_credentials")["access_token"]
    data = request_json("https://oauth.reddit.com/r/brasil/new?limit=5", {"Authorization": f"Bearer {tok}", "User-Agent": agent})
    return f"token obtido; {len(data.get('data', {}).get('children', []))} posts lidos de r/brasil"


def x():
    data = request_json("https://api.x.com/2/tweets/search/recent?query=enchente%20lang%3Apt%20-is%3Aretweet&max_results=10", {"Authorization": f"Bearer {os.environ['X_BEARER_TOKEN']}"})
    return f"{len(data.get('data', []))} posts lidos"


def bluesky():
    host = (os.environ.get("BLUESKY_PDS") or "https://bsky.social").rstrip("/")
    s = request_json(f"{host}/xrpc/com.atproto.server.createSession", {"Content-Type": "application/json"},
                     json.dumps({"identifier": os.environ["BLUESKY_HANDLE"], "password": os.environ["BLUESKY_APP_PASSWORD"]}).encode())
    data = request_json(f"{host}/xrpc/app.bsky.feed.searchPosts?q=enchente&lang=pt&limit=5", {"Authorization": f"Bearer {s['accessJwt']}"})
    return f"sessão criada; {len(data.get('posts', []))} posts lidos"


for net, need, fn in (("Reddit", ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"), reddit), ("X", ("X_BEARER_TOKEN",), x),
                      ("Bluesky", ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"), bluesky)):
    if all(os.environ.get(k, "").strip() for k in need):
        report(net, fn)
    else:
        print(f"{net}: sem chave (segredos ausentes: {', '.join(k for k in need if not os.environ.get(k, '').strip())})")
sys.exit(1 if failed else 0)
