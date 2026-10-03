"""O laço de previsão de ponta a ponta: ~30 h de coleta simulada contra um Worker de mentira completo.

Hoje esse laço só existe em produção depois de mais de 25 h de histórico; este teste o exercita antes: as previsões de volume
nascem, são resolvidas com a contagem REAL, respeitam as regras de validação do Worker e não são reescritas sem necessidade.
"""
import math
import random
import re
from datetime import datetime, timedelta, timezone

from pulso_engine.pipeline import run_once

START = datetime(2026, 10, 2, 6, 0, tzinfo=timezone.utc)
STEP = timedelta(minutes=10)
CYCLES = 28 * 6 + 12  # ~29 h (precisa de mais de 25 h de histórico + 1 h para resolver)
TITLES = {
    "WEATHER": "Temporal causa alagamento e deixa feridos em",
    "TRAFFIC": "Acidente grave bloqueia a rodovia e causa congestionamento em",
    "POLITICS": "Senado aprova projeto de lei no Congresso sobre",
}
PLACES = ["Alfa", "Beta", "Gama", "Delta", "Epsilon", "Zeta", "Eta", "Teta", "Iota", "Capa"]


class SimWorker:
    """Guarda o que o Worker guardaria e devolve o que o Engine lê a cada ciclo."""

    def __init__(self):
        self.series: dict[tuple, dict] = {}
        self.points: list[dict] = []
        self.forecasts: dict[str, dict] = {}
        self.forecast_writes = 0

    def history(self, now):
        cutoff = (now - timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [r for r in self.series.values() if r["bucket"] >= cutoff]

    def apply(self, batch):
        for r in batch["series"]:
            k = (r["scope"], r["category"], r["bucket"])
            if k not in self.series or r["signals"] > self.series[k]["signals"]:
                self.series[k] = r
        for p in batch["pulses"]:
            if p["scope"] == "BR":
                self.points.append({"timestamp": p["timestamp"], "score": p["score"]})
        for f in batch["forecasts"]:
            self.forecast_writes += 1
            old = self.forecasts.get(f["forecast_id"])
            if old is None:
                self.forecasts[f["forecast_id"]] = dict(f)
            elif old["status"] == "open":  # imutável: só a resolução pode ser preenchida
                for k in ("status", "outcome", "observed_value", "resolved_at", "brier"):
                    old[k] = f[k]

    def open_forecasts(self):
        return [dict(f) for f in self.forecasts.values() if f["status"] == "open"]

    def pulse_points(self, now):
        cutoff = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [p for p in self.points if p["timestamp"] >= cutoff]


def feed_for(items) -> bytes:
    body = "".join(f"<item><title>{t}</title><link>{u}</link><pubDate>{d}</pubDate></item>" for t, u, d in items)
    return f"<rss><channel>{body}</channel></rss>".encode()


def test_surge_forecast_loop_end_to_end():
    rng = random.Random(21)
    w = SimWorker()
    src = {"id": "s1", "name": "S1", "domain": "s1.com", "state": None, "adapter": "rss", "source_class": "NEWS_HIGH", "url": "https://s1.com/rss"}
    published: list[tuple[str, str, str, datetime]] = []
    serial = 0
    for i in range(CYCLES):
        now = START + i * STEP
        for cat, base in (("WEATHER", 3.2), ("TRAFFIC", 2.4), ("POLITICS", 4.0)):
            wave = 1 + 0.5 * math.sin(i / 9 + len(cat))
            for _ in range(max(0, round(rng.gauss(base * wave, 0.9)))):
                serial += 1
                at = now - timedelta(minutes=rng.uniform(0.5, 9.5))
                published.append((f"{TITLES[cat]} {PLACES[serial % 10]} caso{serial}", f"https://s1.com/n{serial}", at.strftime("%a, %d %b %Y %H:%M:%S GMT"), at))
        visible = [(t, u, d) for t, u, d, at in published if now - at <= timedelta(minutes=25)]  # o feed mostra só os últimos 25 min (ciclo de 10)
        batch = run_once([src], fetcher=lambda u: feed_for(visible), now=now, history=w.history(now),
                         pulse_points=w.pulse_points(now), open_forecasts=w.open_forecasts(), stored=[], known_events=[])
        w.apply(batch)

    fcs = list(w.forecasts.values())
    surge = [f for f in fcs if f["metric"].startswith("signals_")]
    assert surge, "com ~31 h de histórico contínuo o laço deveria ter criado previsões de volume"
    assert {f["metric"] for f in surge} <= {"signals_weather", "signals_traffic", "signals_politics"}

    # regras de validação do Worker (ingest.ts), replicadas aqui para pegar divergência antes do deploy
    for f in fcs:
        assert re.fullmatch(r"fc-[a-z0-9-]{1,100}", f["forecast_id"]) and re.fullmatch(r"[a-z_]{1,40}", f["metric"])
        assert re.fullmatch(r"BR|UF:[A-Z]{2}", f["scope"]) and 5 <= len(f["question"]) <= 300
        assert 0 < f["probability"] < 1 and f["interval_low"] <= f["probability"] <= f["interval_high"]
        assert (f["status"] == "resolved") == (f["outcome"] is not None and f["brier"] is not None)
        # coerência exigida pelo Worker (ingest.ts): aberta sem resolução; anulada sem resultado; resolvida com tudo
        if f["status"] == "open":
            assert f["outcome"] is None and f["brier"] is None and f["observed_value"] is None and f["resolved_at"] is None
        elif f["status"] == "void":
            assert f["outcome"] is None and f["brier"] is None and f["observed_value"] is None
        else:
            assert f["observed_value"] is not None and f["resolved_at"] is not None
        if f["brier"] is not None:
            assert 0 <= f["brier"] <= 1

    resolved = [f for f in surge if f["status"] == "resolved"]
    assert resolved, "previsões com mais de 1 h de idade deveriam ter sido resolvidas com a contagem real"
    assert all(f["observed_value"] is not None and f["outcome"] in (0, 1) for f in resolved)
    mean_brier = sum(f["brier"] for f in resolved) / len(resolved)
    print(f"[simulação] {len(fcs)} previsões ({len(surge)} de volume), {len(resolved)} resolvidas, Brier médio {mean_brier:.3f}, "
          f"{sum(f['outcome'] for f in resolved)} acertos do evento, {w.forecast_writes} escritas de previsão")
    assert mean_brier < 0.35  # sanidade: não é pior que chute grosseiro nesta série com sazonalidade

    # nenhuma previsão aberta ficou parada além do vencimento + tolerância (resolvida ou anulada)
    last = START + (CYCLES - 1) * STEP
    stale = [f for f in surge if f["status"] == "open" and datetime.fromisoformat(f["resolves_at"].replace("Z", "+00:00")) < last - timedelta(hours=2)]
    assert not stale
    # o orçamento de escrita: previsão aberta não é reenviada a cada ciclo (só as novas e as resoluções)
    assert w.forecast_writes < len(fcs) * 3
