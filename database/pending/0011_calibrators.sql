-- Artefatos de calibração versionados (docs/engineering/FORECAST_V2_BRIEF.md, §30-§32): o calibrador é um ARTEFATO, não um efeito colateral.
-- O artefato (JSON: método, parâmetros, janela de ajuste, amostras) é IMUTÁVEL: uma linha por versão, gravada uma vez.
-- Só o `status` evolui (candidate -> active -> retired) e `retired` é terminal: uma versão aposentada nunca volta.
-- Nunca calibrar com dado de teste/futuro: `fit_end` registra até onde a janela de ajuste vai.
CREATE TABLE IF NOT EXISTS calibrators (
  id           TEXT PRIMARY KEY,                -- cal-<método>-<versão>
  method       TEXT NOT NULL,                   -- ex.: platt, isotonic, identity
  version      TEXT NOT NULL,
  fit_start    TEXT NOT NULL,
  fit_end      TEXT NOT NULL,
  sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
  artifact     TEXT NOT NULL,                   -- JSON com os parâmetros (até 20 KB)
  status       TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','active','retired')),
  created_at   TEXT NOT NULL
) WITHOUT ROWID;
