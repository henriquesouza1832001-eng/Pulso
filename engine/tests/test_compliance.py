import copy
import json

import pytest

from pulso_engine.compliance import (build_report, compliance_status, evidence_ok, render_markdown, unsupported_approvals,
                                     worksheet_rows)
from pulso_engine.config import DEFAULT_SOURCES_PATH, SourceConfigError, validate_source

BASE = {"id": "x", "name": "X", "domain": "x.com.br", "adapter": "rss", "source_class": "NEWS_REGIONAL", "url": "https://x.com.br/rss",
        "enabled": True, "access": "public_feed", "terms_url": "PENDENTE", "interval_s": 300, "retention_days": 90, "display": "headline_link",
        "reviewed_by": "PENDENTE", "reviewed_at": "PENDENTE"}


def src(**kw):
    return {**copy.deepcopy(BASE), **kw}


def test_nothing_is_approved_automatically():
    assert compliance_status(src())[0] == "PENDING"
    reviewed = src(terms_url="https://x.com.br/termos", reviewed_by="alguém", reviewed_at="2026-10-03")
    status, reason = compliance_status(reviewed)
    assert status == "PENDING" and "sem decisão explícita" in reason  # tem revisão, mas ninguém decidiu: continua PENDING


def test_explicit_human_decision_needs_evidence():
    ok = src(terms_url="https://x.com.br/termos", reviewed_by="alguém", reviewed_at="2026-10-03", review_status="APPROVED")
    assert compliance_status(ok)[0] == "APPROVED" and evidence_ok(ok)
    fake = src(review_status="APPROVED")
    assert compliance_status(fake)[0] == "PENDING" and "rebaixada" in compliance_status(fake)[1]
    assert compliance_status({**ok, "review_status": "RESTRICTED"})[0] == "RESTRICTED"
    assert compliance_status({**ok, "review_status": "talvez"})[0] == "UNKNOWN"
    assert compliance_status(src(enabled=False))[0] == "DISABLED"


def test_config_refuses_approval_without_evidence_and_invalid_status():
    with pytest.raises(SourceConfigError, match="exige terms_url"):
        validate_source(src(review_status="APPROVED"))
    with pytest.raises(SourceConfigError, match="review_status deve ser"):
        validate_source(src(review_status="ok"))
    validate_source(src(review_status="PENDING"))  # permitido
    validate_source(src(terms_url="https://x.com.br/t", reviewed_by="a", reviewed_at="2026-10-03", review_status="APPROVED"))


def test_report_counts_by_status_and_family_and_renders():
    sources = [src(id="a"), src(id="b", domain="y.com", source_class="NEWS_HIGH"), src(id="c", enabled=False),
               src(id="d", terms_url="https://x/t", reviewed_by="p", reviewed_at="2026-10-03", review_status="APPROVED")]
    rep = build_report(sources)
    assert rep["total"] == 4 and rep["active_total"] == 3
    assert rep["by_status"] == {"APPROVED": 1, "RESTRICTED": 0, "PENDING": 2, "DISABLED": 1, "UNKNOWN": 0}
    assert rep["by_family"]["NEWS_HIGH/rss"]["PENDING"] == 1
    md = render_markdown(rep)
    assert "| APPROVED | 1 |" in md and "Nenhuma fonte é APPROVED automaticamente" in md


def test_worksheet_groups_by_domain_and_skips_decided_and_disabled():
    sources = [src(id="a"), src(id="a2"), src(id="b", domain="y.com"), src(id="c", enabled=False),
               src(id="d", terms_url="https://x/t", reviewed_by="p", reviewed_at="2026-10-03", review_status="APPROVED")]
    rows = worksheet_rows(sources)
    assert [r["domain"] for r in rows] == ["x.com.br", "y.com"] and rows[0]["sources"] == 2 and rows[0]["terms_url_verified"] == ""


def test_real_catalog_has_no_unsupported_approvals_and_is_still_pending_overall():
    sources = json.loads(DEFAULT_SOURCES_PATH.read_text(encoding="utf-8"))
    assert unsupported_approvals(sources) == []
    rep = build_report(sources)
    assert rep["by_status"]["APPROVED"] == 0 and rep["by_status"]["PENDING"] >= 270  # honestidade: nada aprovado por script
