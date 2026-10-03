"""Conformidade das fontes: estado por fonte, relatório mensurável e planilha de revisão HUMANA.

Estados: APPROVED, RESTRICTED, PENDING, DISABLED, UNKNOWN. **Nada é APPROVED automaticamente**: só vale `review_status:
"APPROVED"` escrito por uma pessoa, junto de `reviewed_by`, `reviewed_at` reais e `terms_url` verificado; sem essa evidência o
estado cai para PENDING (e `config.validate_source` recusa a configuração). Fonte desligada é DISABLED. A automação aqui só
COLETA evidência e organiza a fila de revisão; a decisão é humana (AGENTS.md: nunca contornar termos de uso).

    py -m pulso_engine.compliance --write       gera docs/maturity/COMPLIANCE_REPORT.md
    py -m pulso_engine.compliance --worksheet   gera docs/sources/REVIEW_WORKSHEET.csv (uma linha por domínio)
    py -m pulso_engine.compliance --check       sai com código 1 se houver APPROVED sem evidência
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .config import DEFAULT_SOURCES_PATH, PENDING

STATES = ("APPROVED", "RESTRICTED", "PENDING", "DISABLED", "UNKNOWN")
DECISIONS = {"APPROVED", "RESTRICTED", "PENDING", "DISABLED"}
ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs" / "maturity" / "COMPLIANCE_REPORT.md"
WORKSHEET_PATH = ROOT / "docs" / "sources" / "REVIEW_WORKSHEET.csv"


def _real(value) -> bool:
    return value not in (None, "", PENDING)


def evidence_ok(src: dict) -> bool:
    """Uma decisão humana precisa de quem, quando e de um link de termos verificado."""
    return _real(src.get("reviewed_by")) and _real(src.get("reviewed_at")) and _real(src.get("terms_url"))


def compliance_status(src: dict) -> tuple[str, str]:
    """(estado, motivo). Nunca devolve APPROVED sem decisão explícita E evidência."""
    if not src.get("enabled", True):
        return "DISABLED", "fonte desligada"
    decision = src.get("review_status")
    if decision is None:
        if evidence_ok(src):
            return "PENDING", "revisada por pessoa, mas sem decisão explícita (review_status)"
        return "PENDING", "sem revisão humana"
    if decision not in DECISIONS:
        return "UNKNOWN", f"review_status inválido: {decision!r}"
    if decision in ("APPROVED", "RESTRICTED") and not evidence_ok(src):
        return "PENDING", f"{decision} sem evidência (reviewed_by/reviewed_at/terms_url): rebaixada"
    return decision, "decisão humana registrada"


def family(src: dict) -> str:
    return f"{src.get('source_class', 'UNKNOWN')}/{src.get('adapter', '?')}"


def record(src: dict) -> dict:
    status, reason = compliance_status(src)
    return {
        "id": src["id"], "family": family(src), "status": status, "reason": reason,
        "collection_method": src.get("access"), "terms_status": "VERIFIED_URL" if _real(src.get("terms_url")) else PENDING,
        "review_status": src.get("review_status") or ("REVIEWED_NO_DECISION" if evidence_ok(src) else PENDING),
        "reviewed_at": src.get("reviewed_at"), "reviewed_by": src.get("reviewed_by"),
        "attribution_required": src.get("attribution_required"),  # None = desconhecido
        "retention_policy": f"{src.get('retention_days')} dias", "rate_limit_notes": f"intervalo mínimo {src.get('interval_s')} s",
        "display_constraints": src.get("display"), "compliance_notes": src.get("compliance_notes"),
    }


def build_report(sources: list[dict]) -> dict:
    recs = [record(s) for s in sources]
    active = [r for r in recs if r["status"] != "DISABLED"]
    by_family: dict[str, Counter] = defaultdict(Counter)
    for r in recs:
        by_family[r["family"]][r["status"]] += 1
    domains = {s.get("domain") or s["id"] for s in sources if s.get("enabled", True)}
    pending_domains = {s.get("domain") or s["id"] for s, r in zip(sources, recs) if r["status"] == "PENDING"}
    return {"total": len(recs), "active_total": len(active), "by_status": {k: sum(1 for r in recs if r["status"] == k) for k in STATES},
            "by_family": {f: dict(c) for f, c in sorted(by_family.items())}, "unique_active_domains": len(domains),
            "unique_pending_domains": len(pending_domains), "attribution_unknown": sum(1 for r in active if r["attribution_required"] is None),
            "records": recs}


def render_markdown(rep: dict) -> str:
    s, n = rep["by_status"], max(1, rep["active_total"])
    lines = ["# Conformidade das fontes (relatório gerado)", "",
             "> Gerado por `py -m pulso_engine.compliance --write` a partir de `engine/config/sources.json`. **Não editar à mão.** Nenhuma fonte é APPROVED automaticamente: a decisão é humana (`review_status` + `reviewed_by` + `reviewed_at` + `terms_url`).", "",
             f"- Fontes cadastradas: **{rep['total']}** · ativas: **{rep['active_total']}** · domínios ativos distintos: **{rep['unique_active_domains']}** (domínios com revisão pendente: {rep['unique_pending_domains']}).", "",
             "| Estado | Fontes | % das ativas |", "|---|---|---|"]
    for k in STATES:
        pct = "" if k == "DISABLED" else f"{100 * s[k] / n:.1f}%"
        lines.append(f"| {k} | {s[k]} | {pct} |")
    lines += ["", "## Por família (classe/adaptador)", "", "| Família | " + " | ".join(STATES) + " |", "|---|" + "---|" * len(STATES)]
    for fam, c in rep["by_family"].items():
        lines.append(f"| {fam} | " + " | ".join(str(c.get(k, 0)) for k in STATES) + " |")
    lines += ["", f"Atribuição exigida desconhecida em **{rep['attribution_unknown']}** fontes ativas (campo `attribution_required` ainda não preenchido).", "",
              "## Como reduzir PENDING", "",
              "1. Abrir `docs/sources/REVIEW_WORKSHEET.csv` (uma linha por domínio: uma leitura de termos cobre todas as fontes do domínio).",
              "2. Ler os termos reais do site e preencher `terms_url`, `reviewed_by`, `reviewed_at` e `review_status` (`APPROVED` ou `RESTRICTED`) em `engine/config/sources.json`.",
              "3. `RESTRICTED` quando os termos limitam o uso (ex.: sem redistribuição de texto): registrar a restrição em `compliance_notes` e ajustar `display`/`retention_days`.",
              "4. Termos que proíbem a coleta: `enabled: false` (DISABLED). Nunca contornar login, CAPTCHA, paywall, robots ou limites.", ""]
    return "\n".join(lines)


def worksheet_rows(sources: list[dict]) -> list[dict]:
    """Uma linha por domínio ativo com revisão pendente (ou sem decisão): reduz ~280 leituras a ~240 (e menos onde o domínio se repete)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in sources:
        if s.get("enabled", True) and compliance_status(s)[0] == "PENDING":
            groups[s.get("domain") or s["id"]].append(s)
    rows = []
    for dom, ss in sorted(groups.items()):
        known = sorted({s["terms_url"] for s in ss if _real(s.get("terms_url"))})
        rows.append({"domain": dom, "sources": len(ss), "example_ids": ";".join(s["id"] for s in ss[:5]), "families": ";".join(sorted({family(s) for s in ss})),
                     "terms_url_known": known[0] if known else "", "terms_url_verified": "", "decision_APPROVED_RESTRICTED_DISABLED": "",
                     "attribution_required": "", "reviewed_by": "", "reviewed_at": "", "notes": ""})
    return rows


def unsupported_approvals(sources: list[dict]) -> list[str]:
    """IDs com APPROVED/RESTRICTED sem evidência (nunca deveria existir; o CI usa isto)."""
    return [s["id"] for s in sources if s.get("review_status") in ("APPROVED", "RESTRICTED") and not evidence_ok(s)]


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    sources = json.loads(DEFAULT_SOURCES_PATH.read_text(encoding="utf-8"))
    rep = build_report(sources)
    if "--check" in args:
        bad = unsupported_approvals(sources)
        if bad:
            print("APPROVED/RESTRICTED sem evidência: " + ", ".join(bad), file=sys.stderr)
            return 1
    if "--write" in args:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(render_markdown(rep), encoding="utf-8", newline="\n")
    if "--worksheet" in args:
        rows = worksheet_rows(sources)
        with WORKSHEET_PATH.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["domain"])
            w.writeheader()
            w.writerows(rows)
    print(f"ativas={rep['active_total']} " + " ".join(f"{k}={v}" for k, v in rep["by_status"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
