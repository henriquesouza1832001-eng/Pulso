# Câmeras ao vivo: levantamento de fontes (2026-10-02)

Objetivo: exibir vídeo/imagem ao vivo de câmeras públicas na plataforma, para todos. Regra do `COLLECTION_PROTOCOL.md` §12: só feeds que o órgão dono libera oficialmente. Este levantamento é de leitura de páginas oficiais; **nenhuma fonte abaixo declara permissão de republicação ou incorporação**, então nenhuma está pronta para entrar.

| Fonte | O que oferece | Reutilização / embed | Situação |
|---|---|---|---|
| CET-SP, `cameras.cetsp.com.br` | Imagens em tempo real, públicas, sem cadastro (mosaico de 7 câmeras) | Página não traz termos de reutilização. Diz que as imagens são controladas pela Central e podem ser retiradas em acidentes graves "para preservar a imagem dos envolvidos". | Pedir autorização por escrito à CET. Obrigatório respeitar a retirada em acidentes. |
| DER-SP, dados abertos `dadosabertos.sp.gov.br/dataset/cameras` | Planilha com **localização** das câmeras das rodovias (CC BY 4.0) | Licença cobre só os dados de localização; não há link de vídeo. | Útil para o mapa; não para vídeo. |
| COR-Rio / Prefeitura do Rio | App COR.Rio e imagens no X; página oficial sobre imagens de câmeras | A página restringe imagens gravadas a fins judiciais/administrativos e não menciona API, licença nem embed. | Sem caminho aberto; exigiria parceria formal. |
| DAER-RS | Mapa com imagens em tempo real das rodovias | Remete a "Termos de Uso" gerais; não detalha reutilização. | Pedir autorização por escrito. |
| DNIT | Portal de dados abertos e videoteca de levantamentos (não é ao vivo); API REST prevista a partir de 2026 | Sem feed ao vivo público conhecido. | Acompanhar a API. |
| ANTT / concessionárias | Aplicativos com imagens de rodovias concedidas | Termos por concessionária, a levantar. | A levantar. |

## Caminhos possíveis para ter vídeo ao vivo
1. **Autorização escrita do órgão** (CET-SP, DAER-RS, concessionárias): o caminho mais direto. Pedir: exibição pública, atribuição, formato (iframe/HLS/imagem por link) e cláusula de retirada.
2. **Player oficial incorporado**: se o órgão transmite em canal próprio (ex.: YouTube) com incorporação habilitada, embutimos o player do próprio canal, com atribuição e link. Não re-transmitimos nem copiamos o fluxo. A confirmar canal a canal.
3. **Link para o painel do órgão**: sem autorização, o PULSO mostra a localização e leva o usuário ao site oficial.

## Regras para qualquer câmera
- Sem reconhecimento facial, leitura de placas nem rastreamento de pessoas (AGENTS.md).
- Não guardar nem re-hospedar o vídeo; só embutir o player ou a imagem do próprio órgão.
- Respeitar retirada de imagem pelo órgão (acidentes, privacidade) e mostrar a atribuição.
- Câmera fictícia nunca em produção (`FRONTEND_DATA_MAP.md`).
- Cada fonte entra com ficha em `SOURCES.md`, `enabled: false` e revisão antes de ligar.
