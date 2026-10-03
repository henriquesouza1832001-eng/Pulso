"""Todo adaptador registrado precisa funcionar do jeito que o pipeline o constrói (fetcher ou None)."""
from pulso_engine.collectors.registry import ADAPTERS, URL_FETCH_ADAPTERS, build_adapter


def test_every_adapter_that_receives_the_url_fetcher_is_registered():
    assert URL_FETCH_ADAPTERS <= set(ADAPTERS)


def test_adapters_outside_the_url_list_must_tolerate_fetcher_none():
    """O pipeline passa `None` aos adaptadores fora de URL_FETCH_ADAPTERS (sociais com credencial própria, IDAP em fluxo).
    Um adaptador que guarda `None` como função de busca quebraria (TypeError) só em produção: aqui isso é pego."""
    from datetime import datetime, timezone
    base = {"id": "t", "name": "t", "source_class": "OFFICIAL", "url": "https://x", "state": None}
    for name in sorted(set(ADAPTERS) - URL_FETCH_ADAPTERS):
        src = {**base, "adapter": name, "query": "x", "subreddit": "brasil"}
        try:
            adapter = build_adapter(src, None, None, lambda: datetime(2026, 10, 3, tzinfo=timezone.utc))
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"{name}: não constrói com fetcher=None: {exc}") from exc
        # A função de busca guardada precisa ser chamável: `None` guardado quebraria só ao rodar (TypeError).
        for attr in ("_fetch", "_open", "fetcher"):
            if hasattr(adapter, attr):
                assert callable(getattr(adapter, attr)), f"{name}.{attr} ficou None quando o pipeline passa fetcher=None"
