from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import is_due

T0 = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)


def make(n, interval):
    return [{"id": f"fonte-{i}", "interval_s": interval} for i in range(n)]


def test_load_is_spread_across_ticks_instead_of_piling_on_even_ones():
    sources = make(60, 600)
    loads = [sum(is_due(s, T0 + timedelta(minutes=5 * k)) for s in sources) for k in range(24)]
    assert max(loads) - min(loads) <= 20  # sem espalhar, seria 0 numa rodada e 60 na outra
    assert 15 <= min(loads) and max(loads) <= 45


def test_every_source_runs_once_per_interval_and_the_offset_is_stable():
    for interval in (300, 600, 900, 1800, 3600, 21600):
        for s in make(30, interval):
            ticks = interval // 300
            runs = [k for k in range(ticks * 3) if is_due(s, T0 + timedelta(minutes=5 * k))]
            assert len(runs) >= 3, (s, interval, runs)  # roda em todo intervalo (3 intervalos observados)
            if ticks > 1:
                assert runs[1] - runs[0] in (1, ticks - 1, ticks), (interval, runs)  # janela de 1 ou 2 rodadas, depois o intervalo
            again = [k for k in range(ticks * 3) if is_due(s, T0 + timedelta(minutes=5 * k))]
            assert runs == again  # determinístico: mesmo id, mesmos horários


def test_source_without_id_keeps_the_round_clock_windows():
    base = datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc)
    assert is_due({"interval_s": 900}, base) and not is_due({"interval_s": 900}, base + timedelta(minutes=5))
