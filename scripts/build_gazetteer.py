#!/usr/bin/env python3
"""Gera o gazetteer dos municípios brasileiros a partir de DADOS ABERTOS DO IBGE (engine/data/br_municipalities.json).

Fontes (todas oficiais, sem chave):
- nomes, UF e código:     https://servicodados.ibge.gov.br/api/v1/localidades/municipios
- malha municipal (por UF): https://servicodados.ibge.gov.br/api/v3/malhas/estados/<UF>?intrarregiao=municipio (GeoJSON)
- população estimada:     https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-1/variaveis/9324 (SIDRA 6579)

A latitude/longitude é o CENTROIDE do polígono do município (calculado aqui), não a sede: serve para localizar a notícia
no município certo e nunca no centro da capital do estado. Licença dos dados do IBGE: uso livre com citação da fonte
("Fonte: IBGE"). O arquivo gerado é commitado; este script só roda quando o IBGE atualizar a base (ex.: nova estimativa).

    py scripts/build_gazetteer.py            # grava engine/data/br_municipalities.json e .meta.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "engine" / "data" / "br_municipalities.json"
UA = "pulso-engine/0.1 (+https://github.com/henriquesouza1832001-eng/Pulso)"
BASE = "https://servicodados.ibge.gov.br/api"
UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
# Apelidos usados na imprensa e SEM ambiguidade (apelido ambíguo, como "Rio", não entra aqui).
ALIASES = {"3550308": ["Sampa"], "4205407": ["Floripa"], "3106200": ["BH"], "4314902": ["Poa"], "2304400": []}


def fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def get(url: str) -> bytes:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
                return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("inalcançável")


def ring_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    """Centroide e área (assinada) de um anel de lon/lat pela fórmula do polígono; área pequena, plano local basta."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    if a == 0:
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys), 0.0
    return cx / (3 * a), cy / (3 * a), a / 2


def centroid(geom: dict) -> tuple[float, float]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    sx = sy = total = 0.0
    for poly in polys:  # só o anel externo; o polígono maior domina (ilhas pequenas pesam pouco)
        cx, cy, area = ring_centroid(poly[0])
        w = abs(area)
        sx, sy, total = sx + cx * w, sy + cy * w, total + w
    if total == 0:
        pts = [p for poly in polys for p in poly[0]]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return sx / total, sy / total


def main() -> int:
    munis = json.loads(get(f"{BASE}/v1/localidades/municipios"))
    print("municípios (IBGE):", len(munis))
    cents: dict[str, tuple[float, float]] = {}
    for uf in UFS:
        mesh = json.loads(get(f"{BASE}/v3/malhas/estados/{uf}?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"))
        for f in mesh["features"]:
            cents[str(f["properties"]["codarea"])] = centroid(f["geometry"])
        print(f"  malha {uf}: {len(mesh['features'])}")
    pop_raw = json.loads(get(f"{BASE}/v3/agregados/6579/periodos/-1/variaveis/9324?localidades=N6[all]"))
    pop: dict[str, int] = {}
    year = ""
    for s in pop_raw[0]["resultados"][0]["series"]:
        (year, value), = s["serie"].items()
        if value.isdigit():
            pop[s["localidade"]["id"]] = int(value)
    rows = []
    for m in munis:
        ibge = str(m["id"])
        uf = (m.get("microrregiao") or m.get("regiao-imediata") or {}).get("mesorregiao", {}).get("UF", {}).get("sigla")
        if uf is None:  # municípios sem microrregião (raros): UF pelos 2 primeiros dígitos do código
            uf = {11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
                  31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF"}[int(ibge[:2])]
        quality = "centroid"
        if ibge in cents:
            lon, lat = cents[ibge]
        else:  # município novo que a malha do IBGE ainda não tem: média dos vizinhos da mesma microrregião (precisão menor, marcada)
            # microrregião, ou região imediata quando o cadastro novo do município ainda não tem a primeira
            key, val = (("microrregiao", m["microrregiao"]["id"]) if m.get("microrregiao") else ("regiao-imediata", (m.get("regiao-imediata") or {}).get("id")))
            near = [cents[str(o["id"])] for o in munis if str(o["id"]) in cents and (o.get(key) or {}).get("id") == val] if val else []
            if not near:
                raise SystemExit(f"sem malha nem vizinhos para {ibge} {m['nome']}")
            lon, lat = sum(c[0] for c in near) / len(near), sum(c[1] for c in near) / len(near)
            quality = "microregion_avg"
            print(f"  aviso: {ibge} {m['nome']} sem malha; coordenada = média de {len(near)} vizinhos da microrregião")
        rows.append({"ibge_id": ibge, "name": m["nome"], "normalized_name": fold(m["nome"]), "uf": uf,
                     "latitude": round(lat, 4), "longitude": round(lon, 4), "coord_quality": quality,
                     "population": pop.get(ibge), "aliases": ALIASES.get(ibge, [])})
    rows.sort(key=lambda r: (r["uf"], r["normalized_name"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(body, encoding="utf-8", newline="\n")
    meta = {
        "dataset": "br_municipalities", "count": len(rows), "population_year": year,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "sources": [f"{BASE}/v1/localidades/municipios", f"{BASE}/v3/malhas/estados/<UF>?intrarregiao=municipio (qualidade=minima)",
                    f"{BASE}/v3/agregados/6579/periodos/-1/variaveis/9324 (SIDRA 6579, estimativa de população)"],
        "license": "Dados abertos do IBGE: uso livre com citação da fonte (Fonte: IBGE).",
        "coordinates": "centroide do polígono do município (malha IBGE, qualidade mínima), NÃO a sede",
        "generator": "scripts/build_gazetteer.py",
    }
    OUT.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"gravado {OUT} ({len(body) // 1024} KB, {len(rows)} municípios, população {year})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
