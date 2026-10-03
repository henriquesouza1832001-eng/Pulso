import json

from pulso_engine.catalog_doc import render
from pulso_engine.pipeline import DEFAULT_SOURCES


def test_catalog_lists_every_configured_source_and_counts_active_ones():
    sources = json.loads(DEFAULT_SOURCES.read_text(encoding="utf-8"))
    text = render(sources)
    for s in sources:
        assert f"`{s['id']}`" in text
    active = sum(1 for s in sources if s.get("enabled", True))
    assert f"**{len(sources)} fontes cadastradas, {active} ativas.**" in text
    assert "desligada" in text  # as fontes sociais/GDELT/USGS desligadas aparecem como tal
