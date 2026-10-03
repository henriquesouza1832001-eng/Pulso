from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import chunks, run_once, signal_from_row
from tests.test_pipeline import rss, src

T0 = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)

A = "Temporal causa alagamento em Belo Horizonte e deixa feridos"
B = "Alagamento em Belo Horizonte após temporal deixa feridos"
C = "Temporal e alagamento em Belo Horizonte: feridos graves"


def feeds(*items):
    """items = (fonte, título, minutos atrás)."""
    by_src: dict[str, list] = {}
    for s, t, m in items:
        by_src.setdefault(s, []).append((t, f"https://{s}.com/{abs(hash(t))}", m))
    return {f"https://{s}.com/rss": rss(*v) for s, v in by_src.items()}, [src(s) for s in by_src]


def rows_from(batch):
    return [dict(s) for s in batch["signals"]]


def test_event_id_survives_when_oldest_item_leaves_the_feed():
    f1, s1 = feeds(("a", A, 50), ("b", B, 40))
    run1 = run_once(s1, lambda u: f1[u], T0)
    eid = run1["events"][0]["event_id"]

    # 30 min depois o feed da fonte "a" já não traz a matéria antiga; chega uma terceira fonte.
    later = T0 + timedelta(minutes=30)
    f2, s2 = feeds(("c", C, 5))
    run2 = run_once(s2, lambda u: f2[u], later, stored=rows_from(run1))
    assert [e["event_id"] for e in run2["events"]] == [eid]  # mesmo id, sem duplicata
    assert run2["events"][0]["signal_count"] == 3 and run2["events"][0]["source_count"] == 3


def test_without_state_the_same_story_would_get_a_new_id_proving_the_fix():
    f1, s1 = feeds(("a", A, 50), ("b", B, 40))
    eid = run_once(s1, lambda u: f1[u], T0)["events"][0]["event_id"]
    f2, s2 = feeds(("c", C, 5))
    stateless = run_once(s2, lambda u: f2[u], T0 + timedelta(minutes=30))
    assert stateless["events"][0]["event_id"] != eid and stateless["events"][0]["signal_count"] == 1


def test_only_new_or_changed_signals_are_sent():
    f1, s1 = feeds(("a", A, 50), ("b", B, 40))
    run1 = run_once(s1, lambda u: f1[u], T0)
    f2, s2 = feeds(("c", C, 5))
    run2 = run_once(s2, lambda u: f2[u], T0 + timedelta(minutes=30), stored=rows_from(run1))
    assert len(run2["signals"]) == 1  # só a nova; as duas antigas já estão gravadas com o mesmo evento


def test_old_state_outside_the_window_is_ignored_and_bad_rows_do_not_crash():
    f1, s1 = feeds(("a", A, 50), ("b", B, 40))
    run1 = run_once(s1, lambda u: f1[u], T0)
    bad = rows_from(run1) + [{"hash": "x"}, {"signal_id": "z"}]
    # 30 h depois: o estado antigo está fora da janela; a matéria nova foi publicada 5 min antes dessa rodada
    f2, s2 = feeds(("c", C, -(30 * 60 - 5)))
    run2 = run_once(s2, lambda u: f2[u], T0 + timedelta(hours=30), stored=bad)
    assert run2["events"][0]["signal_count"] == 1
    assert signal_from_row({"hash": "x"}) is None


def test_orphan_signals_are_chunked_without_events():
    f, s = feeds(("a", "Receita de bolo de cenoura", 3), ("b", "Dicas de jardinagem para o verão", 4))
    batch = run_once(s, lambda u: f[u], T0)
    assert batch["events"] == [] and len(batch["signals"]) == 2
    parts = chunks(batch, max_signals=1)
    assert [len(p["signals"]) for p in parts if p["signals"]] == [1, 1]


def test_stored_signals_with_wrong_old_geolocation_are_corrected():
    f1, s1 = feeds(("a", "Governo vai pagar bônus para professores em todo o país", 50),
                   ("b", "Bônus para professores: governo vai pagar em todo o país", 40))
    run1 = run_once(s1, lambda u: f1[u], T0)
    rows = rows_from(run1)
    for r in rows:  # simula o dado antigo gravado com o bug do Pará
        r["state"], r["city"], r["latitude"], r["longitude"] = "PA", None, -1.46, -48.5
    f2, s2 = feeds(("c", "Professores recebem bônus: governo vai pagar para todo o país", 5))
    run2 = run_once(s2, lambda u: f2[u], T0 + timedelta(minutes=30), stored=rows)
    assert run2["events"] and all(e["state"] is None for e in run2["events"])  # sem UF falsa
