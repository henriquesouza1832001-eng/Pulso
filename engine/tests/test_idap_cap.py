from datetime import datetime, timezone

import pytest

from pulso_engine.collectors.official.idap_cap import IdapCapAdapter, iter_alerts

NOW = datetime(2026, 10, 3, 3, 30, tzinfo=timezone.utc)
SRC = {"id": "defesa-civil-idap", "adapter": "idap_cap", "source_class": "OFFICIAL", "url": "https://idap/rss/cap"}


def alert(ident, event="CHUVAS INTENSAS", severity="Severe", areas=("Manaus/AM",), sent="2026-10-03T00:10:00-03:00",
          expires="2026-10-03T23:55:00-03:00", status="Actual", msg="Alert", poly="1,2 3,4 5,6"):
    area_xml = "".join(f"<area><areaDesc>{a}</areaDesc><polygon>{poly}</polygon></area>" for a in areas)
    return f"""<entry><title>{event}</title><id>{ident}</id><content type="text/xml">
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>{ident}</identifier><sender>CENAD</sender>
    <sent>{sent}</sent><status>{status}</status><msgType>{msg}</msgType>
    <info><event>{event}</event><severity>{severity}</severity><expires>{expires}</expires>
    <senderName>Defesa Civil Nacional</senderName><description>Risco de alagamentos e queda de árvores.</description>
    {area_xml}</info></alert></content></entry>"""


def feed(*entries):
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Rss Idap</title>'
            + "".join(entries) + "</feed>").encode("utf-8")


def run(*entries, **src):
    return IdapCapAdapter({**SRC, **src}, None, lambda url: feed(*entries), lambda: NOW).run()


def test_active_alerts_become_official_signals_with_state_and_place():
    sigs = run(alert("1/2026"), alert("2/2026", areas=("AMAZONAS/AM",), severity="Extreme", event="ESTIAGEM"))
    by = {s.title.split(":")[1].split("(")[0].strip(): s for s in sigs}
    assert set(by) == {"Chuvas intensas", "Estiagem"}
    rain, dry = by["Chuvas intensas"], by["Estiagem"]
    assert rain.source_class == "OFFICIAL" and rain.category == "WEATHER" and rain.state == "AM"
    assert "severo" in rain.title and "Manaus/AM" in rain.title and rain.latitude is not None
    assert dry.category == "EMERGENCY" and "extremo" in dry.title  # severidade Extreme = emergência
    assert rain.timestamp == datetime(2026, 10, 3, 3, 10, tzinfo=timezone.utc) and "alagamentos" in rain.text


def test_minor_expired_cancelled_and_test_alerts_are_dropped():
    sigs = run(
        alert("1/2026", severity="Minor"),
        alert("2/2026", expires="2026-10-02T23:55:00-03:00"),     # venceu
        alert("3/2026", msg="Cancel"),
        alert("4/2026", status="Test"),
        alert("5/2026"),                                            # este fica
    )
    assert len(sigs) == 1 and "Manaus" in sigs[0].title
    assert len(run(alert("1/2026", severity="Minor"), min_severity="Minor")) == 1  # limiar configurável


def test_multi_state_alert_has_no_single_state_and_same_identifier_is_not_duplicated():
    s = run(alert("9/2026", areas=("Manaus/AM", "Belém/PA", "Recife/PE", "Natal/RN")))[0]
    assert s.state is None and "e mais 1 áreas" in s.title
    assert len(run(alert("7/2026"), alert("7/2026"))) == 1


def test_polygons_are_not_kept_and_xml_is_read_in_chunks():
    huge = "1.0,2.0 " * 200_000  # ~1,6 MB de polígono por alerta
    entries = [alert(f"{i}/2026", poly=huge) for i in range(3)]
    sigs = run(*entries)
    assert len(sigs) == 3 and all(len(s.text or "") <= 500 for s in sigs)


def test_security_doctype_entity_and_size_limit_are_refused():
    evil = (b'<?xml version="1.0"?><!DOCTYPE feed [<!ENTITY x "boom">]><feed xmlns="http://www.w3.org/2005/Atom"></feed>')
    with pytest.raises(ValueError, match="DOCTYPE"):
        list(iter_alerts(__import__("io").BytesIO(evil)))
    big = feed(alert("1/2026", poly="1,2 " * 100_000))
    with pytest.raises(ValueError, match="tamanho máximo"):
        list(iter_alerts(__import__("io").BytesIO(big), max_bytes=10_000))
