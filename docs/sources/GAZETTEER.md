# Gazetteer dos municípios brasileiros (`geo_v2`)

Base local com **os 5.571 municípios** do IBGE, usada pela geolocalização V2 (`engine/pulso_engine/processing/geo_v2.py`, flag `GEO_V2`). Resolve o problema de um município do interior cair no centro da capital do estado.

| Item | Valor |
|---|---|
| Arquivo | `engine/data/br_municipalities.json` (1 MB) + `br_municipalities.meta.json` (origem, data, hash) |
| Gerador | `scripts/build_gazetteer.py` (roda só quando o IBGE atualizar a base) |
| Campos | `ibge_id`, `name`, `normalized_name` (sem acento, minúsculo), `uf`, `latitude`, `longitude`, `coord_quality`, `population`, `aliases` |
| Nomes, UF, código | API de localidades do IBGE (`/api/v1/localidades/municipios`) |
| Coordenadas | **centroide do polígono** do município (malha IBGE por UF, qualidade mínima), calculado no gerador. Não é a sede. |
| População | estimativa 2026 (SIDRA 6579, variável 9324) |
| Licença | dados abertos do IBGE: uso livre com citação da fonte (**Fonte: IBGE**) |
| Exceção conhecida | `Boa Esperança do Norte` (MT, município novo) ainda não tem malha: coordenada = média dos vizinhos da região imediata, marcada `coord_quality: microregion_avg` (a confiança cai 10 pontos) |

## Regras de resolução
1. **Contexto de lugar obrigatório.** O nome só vira município com UF logo depois (`Itaúna, MG`, `(MG)`, `- MG`, `/MG`), preposição de lugar antes (`em`, `na`, `no`, `de`, `para`...) e inicial maiúscula, ou nome composto. Evita confundir `Serra`, `Natal` ou `Bonito` com palavra comum.
2. **Ambíguo não se chuta.** Nome que existe em vários estados (`Bom Jesus`, `Santa Luzia`, `Lagoa Santa`) só resolve com a UF no texto ou a UF da fonte regional; sem isso só se um município tiver pelo menos 5x a população do segundo e 100 mil habitantes, e a confiança cai 25 (campo `ambiguous`). Senão devolve `None`.
3. **Evidência explícita.** Cada resultado traz `geo_precision`, `geo_confidence` (0-95) e `geo_evidence` (por que).
4. **Nunca a capital por padrão.** O ponto é o do próprio município. Sinal cuja geografia veio da fonte (INPE, Defesa Civil, USGS, InfoDengue) nunca é trocado.

## Integração
`pipeline.refine_geo` aplica o V2 nos sinais novos **e** nos gravados (senão o lugar do evento oscilaria entre V1 e V2). Com `GEO_V2` desligada (padrão), o pipeline só registra em sombra quantos sinais ganhariam município (`geo_v2 (sombra)` no log do ciclo). Ligar só depois do portão de promoção (`docs/engineering/ENGINE_V2_PLAN.md` §5): comparar a acurácia de cidade e de estado do V1 e do V2 sobre uma amostra rotulada.

## Medição inicial (informativa)
Em 9 manchetes reais do interior de MG/RJ/SC/CE: o V1 devolveu só o estado em 5 (ex.: `Itaúna`, `Brumadinho`, `Paracatu`, `Tubarão`) e o V2 achou o município nas 5; nos 2 casos ambíguos (`Santa Luzia`, `Lagoa Santa`) o V2 corretamente não localizou.
