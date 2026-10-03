# 0003 — X pela API oficial e filtro de importância

**Contexto.** O X é onde as notícias aparecem primeiro, mas não há leitura gratuita e legítima. Surgiu a ideia de ler o X com Chromium e uma conta dedicada ao bot. O `COLLECTION_PROTOCOL.md` (§1 e §12) e o `AGENTS.md` proíbem contornar autenticação e termos, e o X proíbe coleta automatizada fora da API.

**Decisão.** (1) O X é coletado só pela API v2 oficial, com `X_BEARER_TOKEN`; a fonte nasce com `enabled: false` e liga quando houver token, orçamento e revisão. A raspagem com login por navegador NÃO foi implementada; mudá-la exige decisão humana explícita, com exceção escrita no `AGENTS.md` e neste ADR. (2) O motor foca em fatos de impacto: `processing/importance.py` pontua o texto (desastre e vítimas > evento físico > contexto fraco) e penaliza ruído de entretenimento; sinais abaixo de `min_importance` não entram.

**Consequências.** Custo da API do X a confirmar antes de ligar. O filtro é uma heurística de palavras: pode perder notícia importante sem esses termos, então a lista deve ser revisada com dados reais (`--dry-run`). Posts de pessoas comuns não guardam autoria.
