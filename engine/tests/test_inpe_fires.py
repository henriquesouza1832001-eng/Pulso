import io
from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.official import inpe_fires as inpe
from pulso_engine.collectors.official.inpe_fires import InpeFiresAdapter

NOW = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
SRC = {"id": "inpe-queimadas", "adapter": "inpe_fires", "source_class": "OFFICIAL",
       "url": "https://dados/diario/Brasil/", "min_focos": 5, "window_h": 3}
HEADER = "id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,municipio_id,estado_id,pais_id,numero_dias_sem_chuva,precipitacao,risco_fogo,bioma,frp\n"


def row(i, ts, estado="PARÁ", municipio="ALTAMIRA", lat=-3.2, lon=-52.2, frp="50.0", bioma="Amazônia"):
    return f"{i},{lat:.4f},{lon:.4f},{ts},NOAA-21,{municipio},{estado},Brasil,1,15,33,,,,{bioma},{frp}\n"


def csv_bytes(*rows):
    return (HEADER + "".join(rows)).encode("utf-8")


def adapter(files, src=SRC):
    calls = []

    def fetch(url):
        calls.append(url)
        for key, data in files.items():
            if key in url:
                return data
        raise OSError("404")

    return InpeFiresAdapter(src, None, fetch, lambda: NOW), calls


def test_signal_per_state_only_above_threshold_and_inside_window():
    rows = [row(i, "2026-10-03 13:%02d:00" % (i % 50)) for i in range(8)]              # PA: 8 na janela
    rows += [row(100 + i, "2026-10-03 13:10:00", estado="BAHIA", municipio="BARREIRAS") for i in range(3)]  # BA: 3 (< limiar)
    rows += [row(200 + i, "2026-10-03 09:00:00") for i in range(9)]                    # PA: fora da janela de 3 h
    a, calls = adapter({"20261003": csv_bytes(*rows)})
    sigs = a.run()
    assert [s.state for s in sigs] == ["PA"]
    s = sigs[0]
    assert "8 detecções" in s.title and "Pará" in s.title and s.source_class == "OFFICIAL" and s.category == "WEATHER"
    assert "Altamira (8)" in s.text and "Amazônia" in s.text and s.timestamp <= NOW
    assert s.geo_precision == "STATE" and -4 < s.latitude < -2
    assert len(calls) == 1  # 14:30 UTC: a janela de 3 h cabe no arquivo de hoje


def test_signal_hash_is_stable_across_cycles_in_the_same_window():
    rows = [row(i, "2026-10-03 13:%02d:00" % i) for i in range(8)]
    a, _ = adapter({"20261003": csv_bytes(*rows)})
    first = a.run()[0]
    more = rows + [row(50 + i, "2026-10-03 13:%02d:30" % i) for i in range(4)]  # mais detecções, mesma janela de 3 h
    b, _ = adapter({"20261003": csv_bytes(*more)})
    second = b.run()[0]
    assert first.hash == second.hash and "8 detecções" in first.title and "12 detecções" in second.title


def test_near_midnight_reads_yesterdays_file_too_and_tolerates_a_missing_today_file():
    global NOW
    saved = NOW
    try:
        NOW = datetime(2026, 10, 3, 0, 40, tzinfo=timezone.utc)
        rows = [row(i, "2026-10-02 22:%02d:00" % (30 + i)) for i in range(7)]
        a, calls = adapter({"20261002": csv_bytes(*rows)})  # o de hoje ainda não existe (404)
        sigs = a.run()
        assert len(calls) == 2 and "20261002" in calls[0] and "20261003" in calls[1]
        assert [s.state for s in sigs] == ["PA"]
    finally:
        NOW = saved


def test_all_files_missing_is_an_error_and_bad_rows_are_skipped():
    a, _ = adapter({})
    try:
        a.run()
    except OSError:
        pass
    else:
        raise AssertionError("sem nenhum arquivo deve falhar (a fonte fica OFFLINE)")
    rows = [row(i, "2026-10-03 13:%02d:00" % i) for i in range(6)] + ["x,y,z\n", "1,abc,def,2026-10-03 13:00:00,N,M,PARÁ,Brasil\n"]
    a2, _ = adapter({"20261003": csv_bytes(*rows)})
    assert len(a2.run()) == 1  # as linhas malformadas não derrubam nem entram na contagem


# ---- leitura por HTTP Range (arquivo de pico passa de 5 MB) -------------------------------------------------------------
class _Resp(io.BytesIO):
    def __init__(self, data, status):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_tail_joins_header_with_the_tail_and_drops_the_cut_first_line(monkeypatch):
    header = HEADER.encode()
    body = (row(1, "2026-10-03 13:00:00") + row(2, "2026-10-03 13:10:00")).encode("utf-8")
    cut = b"3,-3.2000,-52.2000,2026-10-03 12:5"  # linha cortada pelo Range
    calls = []

    def urlopen(req, timeout=0):
        calls.append(req.headers.get("Range"))
        if req.headers.get("Range", "").startswith("bytes=0-"):
            return _Resp(header + body, 206)
        return _Resp(cut + b"\n" + body, 206)

    monkeypatch.setattr(inpe.urllib.request, "urlopen", urlopen)
    data = inpe.fetch_tail("https://dados/x.csv", tail_bytes=1000)
    assert calls == ["bytes=-1000", "bytes=0-1023"]
    text = data.decode("utf-8")
    assert text.startswith("id,lat,lon,data_hora_gmt") and "12:5" not in text.replace("2026-10-03 13", "")  # linha cortada fora
    assert len(list(__import__("csv").DictReader(io.StringIO(text)))) == 2


def test_fetch_tail_falls_back_to_the_whole_file_when_range_is_ignored_and_enforces_a_cap(monkeypatch):
    whole = csv_bytes(row(1, "2026-10-03 13:00:00"))
    monkeypatch.setattr(inpe.urllib.request, "urlopen", lambda req, timeout=0: _Resp(whole, 200))  # 200 = sem Range
    assert inpe.fetch_tail("https://dados/x.csv") == whole
    monkeypatch.setattr(inpe, "MAX_FULL_BYTES", 50)
    with pytest.raises(ValueError, match="tamanho máximo"):
        inpe.fetch_tail("https://dados/x.csv")


def test_default_fetcher_is_the_range_reader_not_the_5mb_limited_one():
    a = InpeFiresAdapter(SRC, None, None, lambda: NOW)
    assert a._fetch is inpe.fetch_tail  # o pipeline passa fetcher=None para este adaptador
