# 0004 — Eventos separados por UF e avisos do INMET como fonte oficial de clima

**Contexto.** O mapa (`BrazilMap`, `UfPanel`, `/api/pulse/states`) agrupa tudo pelo `state` do evento. Um aviso do INMET cobre vários estados e a clusterização é só textual: avisos iguais para MG, ES e RJ viravam um evento só, e ES/RJ sumiam do mapa. Também queremos só clima **impactante**, mas o `Signal` não tem campo de severidade (criar um seria mudança de contrato).

**Decisão.**
1. Clusterização: dois sinais da **mesma fonte** com **UFs diferentes** nunca entram no mesmo evento (`Cluster.matches`). Fontes diferentes continuam podendo se juntar entre estados (ex.: matéria nacional + aviso estadual).
2. Coletor `inmet` (`collectors/official/inmet.py`): lê `GET /avisos/ativos` (só `hoje`; `futuro` não é evento) e gera **um sinal por UF** do aviso, `OFFICIAL`, precisão `STATE`, link para o aviso.
3. Impacto sem mudar contrato: `min_severity` (padrão `Perigo`) descarta "Perigo Potencial" (amarelo); "Grande Perigo" vira categoria `EMERGENCY` (severidade-base 70) e "Perigo" vira `WEATHER` (55).
4. Geolocalização ganha marcadores estaduais (gentílicos, siglas de assembleias, `TRE-UF`) com prioridade menor que cidade/estado explícitos; o Reddit usa a UF da comunidade regional (`subreddit_states`) só quando o título não traz local.

**Consequências.** Um mesmo assunto de um só portal em dois estados vira dois eventos (desejado para o mapa). Avisos "Grande Perigo" podem chegar a nível alto por serem oficiais: o nível 5 continua exigindo ≥ 3 fontes independentes (SCORING.md). Se o `Signal` ganhar `severity` no futuro (mudança de contrato combinada com o front), o mapeamento grau→categoria pode ser trocado por severidade direta.
