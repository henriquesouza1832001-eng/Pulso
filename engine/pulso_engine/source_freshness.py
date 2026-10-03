"""Saúde de fonte em 5 dimensões SEPARADAS (RT-002): transporte, frescor do dado, qualidade (parse), cobertura e evidência.

HTTP 200 NÃO é dado novo; fonte vazia NÃO é "normal"; fonte parada NÃO é zero. Este módulo é puro: recebe o resultado de UMA
leitura (estado de transporte já decidido pelo coletor, os registros lidos e os hashes que o banco já conhece) e devolve:

- `transport`: ONLINE | DEGRADED | RATE_LIMITED | OFFLINE | AUTH_ERROR (vem do coletor, não é reinterpretado aqui);
- `freshness.state`: FRESH | STALE | EMPTY | QUIET | UNKNOWN
    FRESH   = há item cuja data de publicação é recente;
    STALE   = o item mais novo está velho OU o conteúdo não avançou (mesmos itens de antes) e o mais novo é velho;
    EMPTY   = transporte ok, zero registros, e a fonte NÃO é de limiar;
    QUIET   = zero registros numa fonte `quiet_ok` (limiar/alerta): silêncio legítimo, não é falha nem é "fresco";
    UNKNOWN = o transporte falhou: nada se afirma sobre o dado (nunca vira zero);
- `quality`: parse e contagens (recebidos, novos, duplicados) para ver deriva de esquema sem guardar conteúdo;
- `last_content_advance`: último instante em que apareceu item novo (o chamador carrega o anterior).
Cardinalidade: um registro pequeno por fonte; nada por item.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

FRESH, STALE, EMPTY, QUIET, UNKNOWN = "FRESH", "STALE", "EMPTY", "QUIET", "UNKNOWN"
TRANSPORT_OK = "ONLINE"
DEFAULT_STALE_AFTER_MIN = {"NEWS_HIGH": 360, "NEWS_REGIONAL": 720, "OFFICIAL": 1440, "SOCIAL": 360, "TRAFFIC_PROVIDER": 60}
FALLBACK_STALE_AFTER_MIN = 720


def stale_after_min(src: dict) -> int:
    """Limite de idade do item mais novo antes de a fonte ser STALE. Configurável por fonte (`stale_after_min`)."""
    return int(src.get("stale_after_min") or DEFAULT_STALE_AFTER_MIN.get(src.get("source_class", ""), FALLBACK_STALE_AFTER_MIN))


@dataclass(frozen=True)
class SourceReading:
    """O que uma leitura produziu, sem conteúdo de terceiros."""
    source_id: str
    transport: str  # ONLINE | DEGRADED | RATE_LIMITED | OFFLINE | AUTH_ERROR
    parse_ok: bool
    item_hashes: tuple[str, ...]  # hash de cada registro lido
    item_times: tuple[datetime | None, ...]  # data de PUBLICAÇÃO de cada registro, alinhada a item_hashes; None = sem data verificável


def content_hash(item_hashes: tuple[str, ...]) -> str:
    return hashlib.sha1("|".join(sorted(item_hashes)).encode()).hexdigest()[:16]


STORE_WINDOW_MIN = 24 * 60  # o motor só guarda itens das últimas 24 h: o que é mais velho é acervo, não avanço de conteúdo


def assess(src: dict, reading: SourceReading, now: datetime, known_hashes: set[str] | frozenset[str] = frozenset(),
           prev_advance_at: datetime | None = None, store_window_min: int = STORE_WINDOW_MIN) -> dict:
    """Avalia UMA fonte. `known_hashes`: hashes que o banco já tem; `prev_advance_at`: último avanço de conteúdo anterior.
    Item "novo" = ainda desconhecido E dentro da janela que o motor guarda (matéria velha reaparecendo no feed não é avanço)."""
    limit = stale_after_min(src)
    n = len(reading.item_hashes)
    unique = set(reading.item_hashes)
    cutoff = now - timedelta(minutes=store_window_min)
    aligned = zip(reading.item_hashes, reading.item_times or (None,) * n)
    fresh_enough = {h for h, t in aligned if t is None or t > cutoff}  # sem data: conta como novo se desconhecido (1ª vez)
    new = len((unique & fresh_enough) - set(known_hashes))
    duplicates = n - len(unique)
    dated = [t for t in reading.item_times if t is not None]
    newest = max(dated) if dated else None
    age = round((now - newest).total_seconds() / 60, 1) if newest else None
    advance_at = now if new > 0 else prev_advance_at
    if reading.transport not in (TRANSPORT_OK, "DEGRADED"):  # DEGRADED = leitura feita, mas com pouco/nenhum item válido
        state, why = UNKNOWN, f"transporte {reading.transport}: nada se afirma sobre o dado"
    elif not reading.parse_ok:
        state, why = UNKNOWN, "falha de parse: conteúdo ilegível"
    elif n == 0:
        state, why = (QUIET, "sem ocorrências no limiar (fonte quiet_ok)") if src.get("quiet_ok") else (EMPTY, "resposta ok, mas sem registros")
    elif age is None:
        state, why = UNKNOWN, "registros sem data de publicação: frescor não verificável"
    elif age > limit:
        state, why = STALE, f"item mais novo tem {age:.0f} min (limite {limit}); " + ("conteúdo repetido" if new == 0 else "só itens antigos novos")
    else:
        state, why = FRESH, f"item mais novo tem {age:.0f} min"
    return {"source_id": reading.source_id, "transport": reading.transport,
            "freshness": {"state": state, "reason": why, "newest_item_age_min": age, "stale_after_min": limit,
                          "last_content_advance": advance_at.strftime("%Y-%m-%dT%H:%M:%SZ") if advance_at else None,
                          "content_hash": content_hash(reading.item_hashes) if n else None},
            "quality": {"parse_ok": reading.parse_ok, "records": n, "new_records": new, "duplicate_records": duplicates}}


def coverage(assessments: list[dict], families: dict[str, str] | None = None) -> dict:
    """Cobertura por família (ou classe): quantas fontes FRESH, STALE, EMPTY/QUIET, UNKNOWN. `ready_ratio` = FRESH / fontes que
    DEVERIAM falar (QUIET não conta contra nem a favor). UNKNOWN pesa como cobertura perdida, não como zero."""
    fam = families or {}
    by: dict[str, Counter] = {}
    for a in assessments:
        by.setdefault(fam.get(a["source_id"], "ALL"), Counter())[a["freshness"]["state"]] += 1
    out = {}
    for f, c in sorted(by.items()):
        expected = sum(v for k, v in c.items() if k != QUIET)
        out[f] = {**{k: c.get(k, 0) for k in (FRESH, STALE, EMPTY, QUIET, UNKNOWN)}, "sources": sum(c.values()),
                  "ready_ratio": round(c.get(FRESH, 0) / expected, 3) if expected else None}
    return out


def freshness_percentiles(assessments: list[dict]) -> dict:
    """p50/p95/max da idade do item mais novo (minutos) entre fontes com idade conhecida; None sem amostra."""
    ages = sorted(a["freshness"]["newest_item_age_min"] for a in assessments if a["freshness"]["newest_item_age_min"] is not None)
    if not ages:
        return {"n": 0, "p50": None, "p95": None, "max": None}
    pick = lambda q: ages[min(len(ages) - 1, max(0, int(round(q * (len(ages) - 1)))))]  # noqa: E731
    return {"n": len(ages), "p50": pick(0.5), "p95": pick(0.95), "max": ages[-1]}


def next_state_transition(prev: str | None, cur: str) -> str | None:
    """Rótulo de transição para log/observabilidade (FRESH->STALE, UNKNOWN->FRESH...). None se não mudou."""
    return None if prev == cur or prev is None else f"{prev}->{cur}"


def old_cutoff(now: datetime, minutes: int) -> datetime:
    return now - timedelta(minutes=minutes)
