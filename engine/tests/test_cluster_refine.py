from datetime import datetime, timedelta, timezone

from pulso_engine.models import Signal
from pulso_engine.processing.cluster_refine import entities, haversine_km, pair_score, refine_clusters
from pulso_engine.processing.clustering import cluster_signals

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def sig(i, title, minutes_ago=10, cat="TRAFFIC", state="MG", city="Betim", conf=70, lat=None, lon=None, source=None):
    ts = NOW - timedelta(minutes=minutes_ago)
    return Signal(signal_id=str(i), source_id=source or f"s{i}", source_class="NEWS_HIGH", timestamp=ts, collected_at=ts, title=title,
                  category=cat, hash=f"h{i}", state=state, city=city, geo_confidence=conf, latitude=lat, longitude=lon)


def groups(*sigs):
    return cluster_signals(list(sigs))


def test_entities_skip_first_word_and_catch_codes():
    e = entities("Acidente fecha BR-381 em Betim e afeta Belo Horizonte")
    assert "br-381" in e and "betim" in e and "belo horizonte" in e and "acidente" not in e


def test_same_story_different_titles_merge():
    a = sig(1, "Acidente fecha BR-381 em Betim", 30)
    b = sig(2, "Colisão interdita a BR-381 perto de Betim e provoca fila", 20, source="b")
    assert len(groups(a, b)) == 2  # o título sozinho não junta (confirma o problema)
    merged = refine_clusters(groups(a, b))
    assert len(merged) == 1 and len(merged[0].signals) == 2


def test_different_category_or_far_time_never_merge():
    a = sig(1, "Acidente fecha BR-381 em Betim", 30)
    assert pair_score(a, sig(2, "Colisão interdita a BR-381 perto de Betim", 20, cat="SECURITY")) == 0.0
    assert pair_score(a, sig(3, "Colisão interdita a BR-381 perto de Betim", 30 + 4 * 60)) == 0.0


def test_confident_different_states_veto():
    a = sig(1, "Acidente fecha BR-381 em Betim", city=None)
    b = sig(2, "Colisão interdita a BR-381 perto de Betim", state="SP", city=None, source="b")
    assert pair_score(a, b) == 0.0


def test_no_shared_entity_no_merge():
    a = sig(1, "Acidente fecha avenida central em Betim")
    b = sig(2, "Colisão interdita rodovia perto de Contagem", city="Contagem", source="b")
    assert pair_score(a, b) == 0.0


def test_coordinates_far_apart_veto_and_near_pass():
    a = sig(1, "Acidente fecha BR-381 em Betim", lat=-19.97, lon=-44.2, city=None)
    far = sig(2, "Colisão interdita a BR-381 perto de Betim", lat=-23.5, lon=-46.6, city=None, source="b")
    near = sig(3, "Colisão interdita a BR-381 perto de Betim", lat=-19.9, lon=-44.1, city=None, source="c")
    assert haversine_km(a, far) > 300 and pair_score(a, far) == 0.0
    assert pair_score(a, near) > 0.6


def test_cluster_size_cap_prevents_chaining():
    many = [sig(i, f"Colisão interdita a BR-381 perto de Betim ocorrência {i}", 10 + i % 5, source=f"s{i}") for i in range(60)]
    assert all(len(g.signals) <= 40 for g in refine_clusters([g for s in many for g in groups(s)]))
