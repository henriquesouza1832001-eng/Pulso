# Golden datasets de confiabilidade

Esta pasta reserva o formato de replay histórico para a campanha de confiabilidade. Ela não contém evidência sintética apresentada como real.

Um caso `COMPLETE` deve ficar em `events/<case-id>/` ou `negatives/<case-id>/` e conter:

- `metadata.json`: identificador, tipo, escopo, fonte primária verificável e condição de resolução;
- `timeline.jsonl`: uma observação por linha, com `event_time`, `published_at`, `observed_at` e `fetched_at` quando conhecidos;
- `expected.json`: somente fatos observáveis na data de corte e a classificação esperada da janela.

O replay deve entregar ao modelo apenas observações cujo tempo de disponibilidade seja menor ou igual a `data_cutoff`. Campos ausentes permanecem ausentes: nunca devem ser preenchidos por estimativa para tornar uma métrica possível.

`manifest.json` é deliberadamente uma fila de aquisição. Casos `INCOMPLETE` não entram em métricas, gates ou scorecards. Uma mudança para `COMPLETE` exige fonte verificável, revisão humana e o conjunto de três arquivos acima.
