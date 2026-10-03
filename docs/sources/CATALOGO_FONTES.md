# Catálogo de fontes

> Gerado de `engine/config/sources.json` por `py -m pulso_engine.catalog_doc`. **Não edite à mão**: mude a configuração e gere de novo. Fichas detalhadas (termos, limites, retenção) estão em `SOURCES.md`.

**116 fontes cadastradas, 109 ativas.** Ativas por classe: Imprensa nacional/internacional 60, Imprensa regional 31, Oficial 18.

Critérios: feed público oficial do veículo/órgão, testado ao vivo com o coletor real; publicação recente; sem filiação política declarada (para não enviesar a amostra); feeds em inglês ficam de fora enquanto o vocabulário do motor for em português. `revisão pendente` = ainda falta uma pessoa conferir os termos (COLLECTION_PROTOCOL §4).

## Oficial

| id | Nome | Estado | Intervalo | Situação |
|---|---|---|---|---|
| `agencia-camara` | Agência Câmara de Notícias | BR | 300 s | ativa |
| `agencia-fiocruz` | Agência Fiocruz | BR | 900 s | ativa, revisão pendente |
| `agencia-senado` | Agência Senado | BR | 300 s | ativa |
| `bcb-ptax` | Banco Central: dólar PTAX (choque cambial) | BR | 1800 s | ativa, revisão pendente |
| `defesa-civil-idap` | Defesa Civil Nacional: alertas oficiais (IDAP/CAP) | BR | 900 s | ativa, revisão pendente |
| `gov-cemaden` | CEMADEN | BR | 300 s | ativa, revisão pendente |
| `gov-ibama` | IBAMA | BR | 600 s | ativa, revisão pendente |
| `gov-inpe` | INPE | BR | 900 s | ativa, revisão pendente |
| `gov-mdr` | MIDR (Defesa Civil Nacional) | BR | 300 s | ativa, revisão pendente |
| `gov-receita` | Receita Federal | BR | 900 s | ativa, revisão pendente |
| `gov-saude` | Ministério da Saúde | BR | 600 s | ativa, revisão pendente |
| `infodengue-capitais` | InfoDengue: alerta de dengue nas capitais | BR | 21600 s | ativa, revisão pendente |
| `inmet-avisos` | INMET — avisos meteorológicos | BR | 900 s | ativa |
| `inpe-queimadas` | INPE Queimadas (focos de calor) | BR | 600 s | ativa, revisão pendente |
| `tcu` | TCU | BR | 900 s | ativa, revisão pendente |
| `usgs-terremotos` | USGS terremotos significativos | BR | 900 s | ativa, revisão pendente |
| `governo-goias` | Governo de Goiás | GO | 900 s | ativa, revisão pendente |
| `prefeitura-rio` | Prefeitura do Rio | RJ | 600 s | ativa, revisão pendente |

## Imprensa nacional/internacional

| id | Nome | Estado | Intervalo | Situação |
|---|---|---|---|---|
| `agencia-brasil` | Agência Brasil | BR | 300 s | ativa, revisão pendente |
| `agencia-brasil-economia` | Agência Brasil Economia | BR | 600 s | ativa, revisão pendente |
| `agencia-brasil-geral` | Agência Brasil Geral | BR | 300 s | ativa, revisão pendente |
| `agencia-brasil-internacional` | Agência Brasil Internacional | BR | 600 s | ativa, revisão pendente |
| `agencia-brasil-politica` | Agência Brasil Política | BR | 300 s | ativa, revisão pendente |
| `agencia-brasil-saude` | Agência Brasil Saúde | BR | 600 s | ativa, revisão pendente |
| `agencia-infra` | Agência iNFRA | BR | 600 s | ativa, revisão pendente |
| `agencia-publica` | Agência Pública | BR | 900 s | ativa, revisão pendente |
| `bbc-brasil` | BBC News Brasil | BR | 300 s | ativa, revisão pendente |
| `bloomberg-linea` | Bloomberg Línea | BR | 600 s | ativa, revisão pendente |
| `canal-rural` | Canal Rural | BR | 900 s | ativa, revisão pendente |
| `canaltech` | Canaltech | BR | 600 s | ativa, revisão pendente |
| `cnn-brasil` | CNN Brasil | BR | 300 s | ativa, revisão pendente |
| `conjur` | Consultor Jurídico | BR | 600 s | ativa, revisão pendente |
| `drauzio-varella` | Drauzio Varella | BR | 900 s | ativa, revisão pendente |
| `estadao` | Estadão | BR | 300 s | ativa, revisão pendente |
| `euronews-pt` | Euronews Português | BR | 600 s | ativa, revisão pendente |
| `exame` | Exame | BR | 600 s | ativa, revisão pendente |
| `folha` | Folha de S.Paulo | BR | 300 s | ativa, revisão pendente |
| `folha-ambiente` | Folha Ambiente | BR | 600 s | ativa, revisão pendente |
| `folha-ciencia` | Folha Ciência | BR | 900 s | ativa, revisão pendente |
| `folha-cotidiano` | Folha Cotidiano | BR | 300 s | ativa, revisão pendente |
| `folha-mercado` | Folha Mercado | BR | 300 s | ativa, revisão pendente |
| `folha-mundo` | Folha Mundo | BR | 300 s | ativa, revisão pendente |
| `folha-poder` | Folha Poder | BR | 300 s | ativa, revisão pendente |
| `g1` | G1 | BR | 300 s | ativa, revisão pendente |
| `g1-economia` | G1 Economia | BR | 300 s | ativa, revisão pendente |
| `g1-mundo` | G1 Mundo | BR | 300 s | ativa, revisão pendente |
| `g1-politica` | G1 Política | BR | 300 s | ativa, revisão pendente |
| `g1-tecnologia` | G1 Tecnologia | BR | 600 s | ativa, revisão pendente |
| `gazeta-do-povo` | Gazeta do Povo | BR | 300 s | ativa, revisão pendente |
| `ig-ultimo-segundo` | iG Último Segundo | BR | 300 s | ativa, revisão pendente |
| `infomoney` | InfoMoney | BR | 300 s | ativa, revisão pendente |
| `investing-br` | Investing.com Brasil | BR | 600 s | ativa, revisão pendente |
| `istoe` | IstoÉ | BR | 600 s | ativa, revisão pendente |
| `jornal-da-usp` | Jornal da USP | BR | 900 s | ativa, revisão pendente |
| `jota` | JOTA | BR | 600 s | ativa, revisão pendente |
| `jovem-pan` | Jovem Pan | BR | 300 s | ativa, revisão pendente |
| `metropoles` | Metrópoles | BR | 300 s | ativa, revisão pendente |
| `metropoles-brasil` | Metrópoles Brasil | BR | 300 s | ativa, revisão pendente |
| `metropoles-mundo` | Metrópoles Mundo | BR | 600 s | ativa, revisão pendente |
| `metropoles-saude` | Metrópoles Saúde | BR | 600 s | ativa, revisão pendente |
| `metsul` | MetSul Meteorologia | BR | 600 s | desligada |
| `money-times` | Money Times | BR | 600 s | ativa, revisão pendente |
| `nexo` | Nexo Jornal | BR | 900 s | ativa, revisão pendente |
| `olhar-digital` | Olhar Digital | BR | 600 s | ativa, revisão pendente |
| `onu-news-pt` | ONU News Português | BR | 900 s | ativa, revisão pendente |
| `petronoticias` | Petronotícias | BR | 600 s | ativa, revisão pendente |
| `poder360` | Poder360 | BR | 300 s | ativa, revisão pendente |
| `revista-piaui` | Revista piauí | BR | 900 s | ativa, revisão pendente |
| `rfi-pt` | RFI Português | BR | 600 s | ativa, revisão pendente |
| `saude-abril` | Saúde Abril | BR | 900 s | ativa, revisão pendente |
| `seu-dinheiro` | Seu Dinheiro | BR | 600 s | ativa, revisão pendente |
| `suno` | Suno Notícias | BR | 900 s | ativa, revisão pendente |
| `tecnoblog` | Tecnoblog | BR | 600 s | ativa, revisão pendente |
| `terra-brasil` | Terra Brasil | BR | 600 s | ativa, revisão pendente |
| `terra-noticias` | Terra Notícias | BR | 600 s | ativa, revisão pendente |
| `uol` | UOL | BR | 300 s | ativa, revisão pendente |
| `uol-economia` | UOL Economia | BR | 300 s | ativa, revisão pendente |
| `valor` | Valor Econômico | BR | 300 s | ativa, revisão pendente |
| `veja` | Veja | BR | 300 s | ativa, revisão pendente |

## Imprensa regional

| id | Nome | Estado | Intervalo | Situação |
|---|---|---|---|---|
| `gdelt-br` | GDELT cobertura de notícias | BR | 900 s | desligada |
| `g1-ac` | G1 Acre | AC | 600 s | ativa, revisão pendente |
| `g1-al` | G1 Alagoas | AL | 600 s | ativa, revisão pendente |
| `amazonia-real` | Amazônia Real | AM | 900 s | ativa, revisão pendente |
| `g1-am` | G1 Amazonas | AM | 600 s | ativa, revisão pendente |
| `g1-ap` | G1 Amapá | AP | 600 s | ativa, revisão pendente |
| `bahia-noticias` | Bahia Notícias | BA | 600 s | ativa, revisão pendente |
| `bnews-ba` | BNews (BA) | BA | 600 s | ativa, revisão pendente |
| `metropoles-df` | Metrópoles DF | DF | 300 s | ativa, revisão pendente |
| `a-gazeta-es` | A Gazeta (ES) | ES | 600 s | ativa, revisão pendente |
| `folha-vitoria` | Folha Vitória (ES) | ES | 600 s | ativa, revisão pendente |
| `g1-ma` | G1 Maranhão | MA | 600 s | ativa, revisão pendente |
| `o-imparcial-ma` | O Imparcial (MA) | MA | 600 s | ativa, revisão pendente |
| `bhaz-mg` | BHAZ (MG) | MG | 600 s | ativa, revisão pendente |
| `uai-mg` | UAI (MG) | MG | 600 s | ativa, revisão pendente |
| `g1-mt` | G1 Mato Grosso | MT | 600 s | ativa, revisão pendente |
| `diario-do-para` | Diário do Pará | PA | 600 s | ativa, revisão pendente |
| `g1-pa` | G1 Pará | PA | 600 s | ativa, revisão pendente |
| `g1-pb` | G1 Paraíba | PB | 600 s | ativa, revisão pendente |
| `g1-pi` | G1 Piauí | PI | 600 s | ativa, revisão pendente |
| `g1-pr` | G1 Paraná | PR | 600 s | ativa, revisão pendente |
| `g1-rn` | G1 Rio Grande do Norte | RN | 600 s | ativa, revisão pendente |
| `tribuna-do-norte` | Tribuna do Norte (RN) | RN | 900 s | ativa, revisão pendente |
| `g1-ro` | G1 Rondônia | RO | 600 s | ativa, revisão pendente |
| `g1-rr` | G1 Roraima | RR | 600 s | ativa, revisão pendente |
| `g1-rs` | G1 Rio Grande do Sul | RS | 600 s | ativa, revisão pendente |
| `g1-sc` | G1 Santa Catarina | SC | 600 s | ativa, revisão pendente |
| `nd-mais` | ND Mais (SC) | SC | 600 s | ativa, revisão pendente |
| `nsc-total` | NSC Total (SC) | SC | 600 s | ativa, revisão pendente |
| `g1-se` | G1 Sergipe | SE | 600 s | ativa, revisão pendente |
| `metropoles-sp` | Metrópoles SP | SP | 300 s | ativa, revisão pendente |
| `g1-to` | G1 Tocantins | TO | 600 s | ativa, revisão pendente |

## Rede social

| id | Nome | Estado | Intervalo | Situação |
|---|---|---|---|---|
| `mastodon-impacto` | Mastodon hashtags de impacto | BR | 900 s | desligada |
| `reddit-clima` | Reddit clima BR (piloto) | BR | 900 s | desligada |
| `reddit-politics` | Reddit política BR (piloto) | BR | 900 s | desligada |
| `x-clima` | X clima BR (piloto) | BR | 900 s | desligada |
| `x-politics` | X política BR (piloto) | BR | 900 s | desligada |

