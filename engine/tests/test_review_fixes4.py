"""Achados da QUARTA revisão independente (coletores, nível máximo, 2026-10-03): uma resposta malformada de uma API não pode
derrubar o coletor inteiro; cada um vira um teste que falha sem a correção."""
import json
from datetime import datetime, timedelta, timezone

from pulso_engine.collectors.news.gdelt import GdeltAdapter
from pulso_engine.collectors.official.bcb_ptax import BcbPtaxAdapter
from pulso_engine.collectors.official.idap_cap import IdapCapAdapter
from pulso_engine.collectors.official.inmet import InmetAdapter
from pulso_engine.collectors.official.infodengue import CAPITALS, InfoDengueAdapter
from pulso_engine.collectors.official.inpe_fires import InpeFiresAdapter
from pulso_engine.collectors.official.usgs import UsgsAdapter
from pulso_engine.collectors.social.mastodon import MastodonAdapter

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


# ---- 1) Mastodon: erro da instância vem como objeto, não como lista -------------------------------------------------
def test_mastodon_error_object_does_not_crash_and_good_instances_still_count():
    good = [{"id": "1", "url": "https://m/1", "content": "<p>Enchente deixa 3 mortos em Porto Alegre</p>", "language": "pt",
             "created_at": "2026-10-03T14:00:00.000Z"}]

    def fetch(url):
        return json.dumps({"error": "Rate limited"} if "ruim" in url else good).encode()

    src = {"id": "m", "adapter": "mastodon", "source_class": "SOCIAL", "url": "https://x", "instances": ["ruim.social", "bom.social"], "tags": ["enchente"]}
    assert len(MastodonAdapter(src, None, fetch, lambda: NOW).run()) == 1


# ---- 2 + 3) IDAP: UF inválida e referências de Update/Cancel ---------------------------------------------------------------
def cap(ident, area="Manaus/AM", msg="Alert", refs=""):
    ref = f"<references>{refs}</references>" if refs else ""
    return (f"<entry><content type='text/xml'><alert xmlns='urn:oasis:names:tc:emergency:cap:1.2'><identifier>{ident}</identifier>"
            f"<sent>2026-10-03T10:00:00-03:00</sent><status>Actual</status><msgType>{msg}</msgType>{ref}"
            f"<info><event>CHUVAS INTENSAS</event><severity>Severe</severity><expires>2026-10-03T23:55:00-03:00</expires>"
            f"<description>d</description><area><areaDesc>{area}</areaDesc></area></info></alert></content></entry>")


def idap(*entries):
    xml = ("<feed xmlns='http://www.w3.org/2005/Atom'>" + "".join(entries) + "</feed>").encode()
    src = {"id": "idap", "adapter": "idap_cap", "source_class": "OFFICIAL", "url": "https://x"}
    return IdapCapAdapter(src, None, lambda u: xml, lambda: NOW).run()


def test_idap_area_with_a_non_uf_code_does_not_crash_the_whole_feed():
    sigs = idap(cap("1/2026", area="Brasil/BR"), cap("2/2026", area="Região/XX"), cap("3/2026", area="Manaus/AM"))
    assert len(sigs) == 3  # as três entram; só a de Manaus tem estado
    assert [s.state for s in sigs if s.state] == ["AM"]


def test_idap_update_replaces_and_cancel_removes_the_alerts_they_reference():
    original = cap("1/2026")
    update = cap("2/2026", msg="Update", refs="CENAD,1/2026,2026-10-03T10:00:00-03:00")
    assert [s.title for s in idap(original, update)] == [idap(update)[0].title] and len(idap(original, update)) == 1  # sem duplicata
    cancel = cap("3/2026", msg="Cancel", refs="CENAD,1/2026,2026-10-03T10:00:00-03:00")
    assert idap(original, cancel) == []  # o alerta cancelado deixa de valer
    assert len(idap(original, cap("9/2026", msg="Cancel", refs="CENAD,outro/2026,x"))) == 1  # referência a outro alerta não afeta


# ---- 4) Banco Central: vários boletins no mesmo dia ----------------------------------------------------------------------------
def test_ptax_compares_days_not_bulletins_of_the_same_day():
    def body(*q):
        return json.dumps({"value": [{"cotacaoCompra": v, "cotacaoVenda": v, "dataHoraCotacao": t} for t, v in q]}).encode()
    src = {"id": "b", "adapter": "bcb_ptax", "source_class": "OFFICIAL", "url": "https://olinda/x"}
    now = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)
    # dois boletins no dia 02 (10h: 5,10; 13h: 5,60) e um no dia 01 (5,00): a variação é 02 vs 01 (+12%), não 13h vs 10h
    rows = body(("2026-10-02 13:03:00", 5.60), ("2026-10-02 10:03:00", 5.10), ("2026-10-01 13:03:00", 5.00))
    (s,) = BcbPtaxAdapter(src, None, lambda u: rows, lambda: now).run()
    assert s.title.startswith("Dólar sobe 12,0%") and "R$ 5,0000 no pregão anterior" in s.text
    calm = body(("2026-10-02 13:03:00", 5.01), ("2026-10-02 10:03:00", 5.60), ("2026-10-01 13:03:00", 5.00))  # oscilou no dia, fechou igual
    assert BcbPtaxAdapter(src, None, lambda u: calm, lambda: now).run() == []


# ---- 5) USGS: coordenadas nulas ou incompletas ------------------------------------------------------------------------------
def test_usgs_bad_geometry_does_not_drop_the_other_quakes():
    def q(title, geometry):
        return {"properties": {"title": title, "url": "https://u/" + title, "time": 1790990000000}, "geometry": geometry}
    body = {"features": [q("M 6 - A, Brazil", None), q("M 6 - B, Brazil", {"coordinates": []}), q("M 6 - C, Brazil", {"coordinates": None}),
                         q("M 6 - D, Brazil", {"coordinates": [-70.0, -9.0, 10]})]}
    src = {"id": "u", "adapter": "usgs", "source_class": "OFFICIAL", "url": "https://x"}
    sigs = UsgsAdapter(src, None, lambda u: json.dumps(body).encode(), lambda: NOW).run()
    assert len(sigs) == 4 and [s.latitude for s in sigs if s.latitude is not None] == [-9.0]


# ---- 6 + 7) INPE: hash estável no ciclo e FRP ausente (-999) -------------------------------------------------------------------
HEADER = "id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,municipio_id,estado_id,pais_id,numero_dias_sem_chuva,precipitacao,risco_fogo,bioma,frp\n"


def fires(rows, now):
    body = (HEADER + "".join(f"{i},-3.2,-52.2,{t},NOAA,ALTAMIRA,PARÁ,Brasil,1,15,33,,,,Amazônia,{frp}\n" for i, (t, frp) in enumerate(rows))).encode()
    src = {"id": "i", "adapter": "inpe_fires", "source_class": "OFFICIAL", "url": "https://d/", "min_focos": 3, "window_h": 3}
    return InpeFiresAdapter(src, None, lambda u: body, lambda: now).run()


def test_inpe_hash_stays_the_same_across_cycles_in_the_same_clock_window_and_ignores_missing_frp():
    now1 = datetime(2026, 10, 3, 13, 40, tzinfo=timezone.utc)
    a = fires([("2026-10-03 13:00:00", "50.0"), ("2026-10-03 13:10:00", "-999"), ("2026-10-03 13:20:00", "25.0")], now1)[0]
    # 10 min depois chegam detecções mais novas: a janela de relógio é a mesma, então o sinal é o mesmo
    b = fires([("2026-10-03 13:00:00", "50.0"), ("2026-10-03 13:10:00", "-999"), ("2026-10-03 13:20:00", "25.0"),
               ("2026-10-03 13:55:00", "10.0")], now1 + timedelta(minutes=15))[0]
    assert a.hash == b.hash
    assert "75 MW" in a.text and "-" not in a.text.split("somada:")[1].split("MW")[0]  # 50 + 25 (o -999 não entra)


# ---- 8) INMET: resposta em Latin-1 -------------------------------------------------------------------------------------------------
def test_inmet_latin1_response_does_not_take_the_source_offline():
    alert = {"id": 1, "severidade": "Perigo", "descricao": "Tempestade", "estados": "Paraná", "inicio": "2026-10-03 09:00",
             "fim": "2026-10-03 23:59", "riscos": ["Ventos de 60-100 km/h, risco de queda de árvores."], "encerrado": False}
    payload = json.dumps({"hoje": [{**alert, "descricao": "Tempestade com granizo e ventania"}]}, ensure_ascii=False).replace("Tempestade", "Tempestáde").encode("cp1252")
    src = {"id": "inmet", "adapter": "inmet", "source_class": "OFFICIAL", "url": "https://x", "min_severity": "Perigo"}
    assert len(InmetAdapter(src, fetcher=lambda u: payload, now=lambda: NOW).run()) == 1


# ---- 9) InfoDengue: objeto de erro da API ------------------------------------------------------------------------------------------
def test_infodengue_error_object_skips_that_capital_only():
    mg = CAPITALS["MG"][1]

    def fetch(url):
        if f"geocode={mg}" in url:
            return json.dumps([{"SE": 202638, "nivel": 4, "casos_est": 100.0}]).encode()
        return json.dumps({"error": "invalid geocode"}).encode()  # as outras 26 devolvem erro em objeto

    src = {"id": "d", "adapter": "infodengue", "source_class": "OFFICIAL", "url": "https://x"}
    sigs = InfoDengueAdapter(src, None, fetch, lambda: NOW).run()
    assert [s.state for s in sigs] == ["MG"]


# ---- 10) GDELT: URL repetida não gera dois sinais com o mesmo id ------------------------------------------------------------------
def test_gdelt_repeated_url_yields_a_single_signal():
    art = {"url": "https://g1.globo.com/x", "title": "Enchente atinge Porto Alegre", "seendate": "20261003T140000Z"}
    body = json.dumps({"articles": [art, art, {**art, "url": "https://g1.globo.com/y"}]}).encode()
    src = {"id": "g", "adapter": "gdelt", "source_class": "NEWS_REGIONAL", "url": "https://x"}
    assert len(GdeltAdapter(src, None, lambda u: body, lambda: NOW).run()) == 2
