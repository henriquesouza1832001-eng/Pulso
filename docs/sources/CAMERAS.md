# Câmeras ao vivo: levantamento de fontes (verificado em 2026-10-03)

Objetivo: exibir imagem/vídeo ao vivo de câmeras públicas na plataforma, para todos. Regra do `COLLECTION_PROTOCOL.md` §12: só feeds que o órgão dono libera oficialmente. Este levantamento foi feito lendo páginas e termos oficiais. **Nenhuma câmera de órgão público brasileiro declara permissão de republicação ou incorporação**; a única via que declara essa permissão é um provedor que licencia as imagens (Windy).

## Lista A: pode entrar sem pedir permissão a órgão (condições abaixo)
| Fonte | O que oferece | Condição verificada | Pendência |
|---|---|---|---|
| **Windy Webcams API** (`api.windy.com/webcams`) | Webcams do mundo todo (inclui praias e cidades), imagens e player | Plano gratuito existe; exige **chave de API** (`x-windy-api-key`); URLs das imagens expiram em 10 min no plano gratuito; termos exigem **atribuição** ("Webcams provided by Windy.com"), **link** de cada imagem para a página da webcam ou o player, usar **só as URLs da API** e não esticar a imagem. Ver https://api.windy.com/webcams/terms | Criar a chave (só o dono do projeto pode, é cadastro pessoal); confirmar cobertura no Brasil e os termos completos antes de ativar. |

## Lista B: visualização pública, mas só com **link** para o painel oficial (não embutir, não copiar)
| Fonte | O que oferece | Por que só link |
|---|---|---|
| CET-SP, `cameras.cetsp.com.br` | Imagens em tempo real, sem cadastro (mosaico de 7 câmeras) | A página não traz termos de reutilização e diz que as imagens são controladas pela Central e podem ser retiradas em acidentes graves "para preservar a imagem dos envolvidos". Embutir exigiria autorização. |
| DAER-RS, `daer.rs.gov.br/cameras-de-monitoramento` | Mapa com imagens em tempo real das rodovias | Remete a "Termos de Uso" gerais; não detalha reutilização. |
| COR-Rio, `cor.rio` | App e imagens no X | A página oficial restringe imagens gravadas a fins judiciais; sem API, licença nem embed. |

## Lista C: sem caminho aberto hoje
| Fonte | Situação |
|---|---|
| DER-SP, dados abertos `dadosabertos.sp.gov.br/dataset/cameras` | A licença é CC BY 4.0, **mas só para a localização**, sem vídeo. Além disso, em 2026-10-03 o link do arquivo XLSX redireciona (301) para a página inicial do DER: o arquivo não está baixável. Acompanhar. |
| DNIT | Dados abertos e videoteca de levantamentos (não é ao vivo). API REST prevista a partir de 2026. |
| ANTT e concessionárias | Aplicativos com imagens; termos por concessionária, a levantar. |

## Como chegar ao vídeo ao vivo para todos
1. **Windy** (Lista A): o caminho mais rápido e dentro das regras. Precisa da chave; o Worker guarda a chave como secret e a plataforma mostra a atribuição e o link exigidos.
2. **Autorização escrita do órgão** (CET-SP, DAER-RS, concessionárias): pedir exibição pública, atribuição, formato (iframe/HLS/imagem por link) e cláusula de retirada.
3. **Player oficial incorporado**: se o órgão transmite em canal próprio (ex.: YouTube) com incorporação habilitada, embutimos o player dele, sem retransmitir o fluxo.
4. **Link para o painel do órgão** (Lista B): já pode entrar hoje.

## Regras para qualquer câmera
- Sem reconhecimento facial, leitura de placas nem rastreamento de pessoas (AGENTS.md).
- Não guardar nem re-hospedar o vídeo; só embutir o player ou a imagem pela URL do próprio provedor.
- Respeitar retirada de imagem pelo órgão (acidentes, privacidade) e mostrar a atribuição.
- Câmera fictícia nunca em produção (`FRONTEND_DATA_MAP.md`).
- Cada fonte entra com ficha em `SOURCES.md`, `enabled: false` e revisão antes de ligar.

## O que foi verificado do Windy (2026-10-03)
- O endpoint de lista existe: `GET https://api.windy.com/webcams/api/v3/webcams`; sem chave responde `403 Missing Header 'x-windy-api-key' with API key`. Ou seja, o nome do cabeçalho está confirmado.
- **Não verificado**: o formato JSON da resposta (campos, `include`, filtros por país/região). A documentação é uma página Swagger interativa e o esquema só fica visível com uma chave. Por isso o backend **não foi escrito às cegas**: escrever um mapeador contra um esquema adivinhado daria a falsa impressão de que funciona.
- Passo seguinte, com a chave em mãos: chamar o endpoint uma vez, salvar a resposta real, e só então escrever o mapeador e os testes em cima dela.

## Para construir (quando houver a chave do Windy)
1. Contrato de `/api/cameras`: `id`, `label`, `city`, `state`, `lat`, `lon`, `provider`, `attribution`, `page_url`, `embed` (tipo e URL). Atualizar `contracts.ts`, `models.py` e `API.md` no mesmo PR, com a label `contract`.
2. Worker: rota que consulta a API do Windy com a chave em secret e devolve só os campos acima (a chave nunca vai ao navegador); cache curto respeitando a expiração de 10 min.
3. Front: o `Cameras.tsx` já recebe uma lista; trocar `DEMO_CAMERAS` por essa rota e exibir atribuição e link.
