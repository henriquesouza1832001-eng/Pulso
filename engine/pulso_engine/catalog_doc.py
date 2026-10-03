"""Gera docs/sources/CATALOGO_FONTES.md a partir de config/sources.json (a configuração é a fonte da verdade).

Uso: py -m pulso_engine.catalog_doc            # grava o arquivo
     py -m pulso_engine.catalog_doc --stdout   # só imprime
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from .pipeline import DEFAULT_SOURCES

OUT = Path(__file__).resolve().parents[2] / "docs" / "sources" / "CATALOGO_FONTES.md"
CLASS_LABEL = {"OFFICIAL": "Oficial", "NEWS_HIGH": "Imprensa nacional/internacional", "NEWS_REGIONAL": "Imprensa regional",
               "SOCIAL": "Rede social", "SOCIAL_VERIFIED": "Rede social (verificada)", "TRAFFIC_PROVIDER": "Trânsito"}


def _status(s: dict) -> str:
    if not s.get("enabled", True):
        return "desligada"
    return "ativa, revisão pendente" if "PENDENTE" in (s["reviewed_by"], s["reviewed_at"], s["terms_url"]) else "ativa"


def render(sources: list[dict]) -> str:
    on = [s for s in sources if s.get("enabled", True)]
    by_class = Counter(s["source_class"] for s in on)
    lines = [
        "# Catálogo de fontes",
        "",
        "> Gerado de `engine/config/sources.json` por `py -m pulso_engine.catalog_doc`. **Não edite à mão**: "
        "mude a configuração e gere de novo. Fichas detalhadas (termos, limites, retenção) estão em `SOURCES.md`.",
        "",
        f"**{len(sources)} fontes cadastradas, {len(on)} ativas.** Ativas por classe: "
        + ", ".join(f"{CLASS_LABEL.get(c, c)} {n}" for c, n in by_class.most_common()) + ".",
        "",
        "Critérios: feed público oficial do veículo/órgão, testado ao vivo com o coletor real; publicação recente; "
        "sem filiação política declarada (para não enviesar a amostra); feeds em inglês ficam de fora enquanto o "
        "vocabulário do motor for em português. `revisão pendente` = ainda falta uma pessoa conferir os termos "
        "(COLLECTION_PROTOCOL §4).",
        "",
    ]
    groups: dict[str, list[dict]] = {}
    for s in sources:
        groups.setdefault(s["source_class"], []).append(s)
    for cls in ("OFFICIAL", "NEWS_HIGH", "NEWS_REGIONAL", "SOCIAL", "SOCIAL_VERIFIED", "TRAFFIC_PROVIDER"):
        if cls not in groups:
            continue
        lines += [f"## {CLASS_LABEL[cls]}", "", "| id | Nome | Estado | Intervalo | Situação |", "|---|---|---|---|---|"]
        for s in sorted(groups[cls], key=lambda x: (x.get("state") or "", x["id"])):
            lines.append(f"| `{s['id']}` | {s['name']} | {s.get('state') or 'BR'} | {s['interval_s']} s | {_status(s)} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = render(json.loads(Path(DEFAULT_SOURCES).read_text(encoding="utf-8")))
    if "--stdout" in argv:
        sys.stdout.write(text)
    else:
        OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"gravado {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
