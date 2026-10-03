from datetime import datetime, timezone

from pulso_engine.collectors.official.ons_ear import OnsEarAdapter

SRC = {"id": "ons-ear", "adapter": "ons_ear", "source_class": "OFFICIAL", "url": "https://ons/EAR_{year}.csv"}
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
HEAD = "id_subsistema;nom_subsistema;ear_data;ear_max_subsistema;ear_verif_subsistema_mwmes;ear_verif_subsistema_percentual\n"


def run(rows, **extra):
    body = (HEAD + "".join(f"{s};X;{d};1;1;{p}\n" for s, d, p in rows)).encode()
    seen = []
    a = OnsEarAdapter({**SRC, **extra}, None, lambda u: (seen.append(u), body)[1], lambda: NOW)
    return a.run(), seen


def test_normal_level_is_quiet_and_year_in_url():
    sigs, seen = run([("SE ", "2026-09-24", 58), ("SE ", "2026-10-01", 56.3), ("S ", "2026-10-01", 83)])
    assert sigs == [] and seen == ["https://ons/EAR_2026.csv"]


def test_low_level_emits_infrastructure_signal():
    sigs, _ = run([("NE", "2026-09-24", 30), ("NE", "2026-10-01", 24.5), ("S ", "2026-10-01", 80)])
    assert len(sigs) == 1 and sigs[0].category == "INFRASTRUCTURE" and "Nordeste 24,5%" in sigs[0].title


def test_fast_drop_emits_and_stale_data_does_not():
    sigs, _ = run([("N", "2026-09-24", 70), ("N", "2026-10-01", 58)])
    assert len(sigs) == 1 and "queda" in sigs[0].text
    assert run([("N", "2026-09-01", 10)])[0] == []
