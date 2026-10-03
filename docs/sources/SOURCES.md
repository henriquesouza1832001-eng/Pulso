# Fontes

Cada integração documenta aqui: fonte, API, limites, credenciais, dados coletados, frequência, fallback e termos relevantes. **Antes de implementar**, verifique API oficial, termos, rate limits, custo, autenticação, licença, retenção e exibição pública. Nunca contorne autenticação ou limites.

| Fonte | Classe | Adaptador | Status |
|---|---|---|---|
| (modelo) Agência Brasil | NEWS_HIGH | RSS | ⏳ `collector/news-rss` |
| (modelo) PRF | OFFICIAL | API | ⏳ verificar termos |
| X (`x-impacto`) | SOCIAL | API oficial v2 (busca recente) | 🧪 código pronto, `enabled: false` até haver token e revisão |
| Reddit | SOCIAL | API oficial | ⏳ aguardando aprovação do app |
| Trânsito, câmeras públicas | — | — | Fase 2/3 |

## Modelo de ficha
```
Fonte / URL:
Tipo de acesso (RSS, API, feed):
Autenticação e secrets necessários:
Limites e custo:
Dados coletados e retenção permitida:
Frequência:
Fallback se cair:
Termos relevantes (link):
Exibição pública permitida:
```

## Ficha: X (`x-impacto`)
```
Fonte / URL: X, GET https://api.x.com/2/tweets/search/recent
Tipo de acesso: API oficial v2 (busca recente). Sem raspagem e sem login por navegador.
Autenticação e secrets: X_BEARER_TOKEN (GitHub Actions / wrangler secret). Nunca no Git.
Limites e custo: plano pago do X (pay-per-use); conferir preço e cota atuais na página de desenvolvedores antes de ativar. Cadência de 900 s e max_results 50 para manter o custo baixo.
Dados coletados e retenção: texto do post (<= 500 car.), link, data. @ guardado só de conta verificada (veículo/órgão); nenhum perfil de pessoa comum. Retenção 30 dias.
Frequência: 900 s.
Fallback se cair: 401/403 -> AUTH_ERROR (não insistir); 429 -> RATE_LIMITED. As demais fontes seguem.
Termos relevantes: https://developer.x.com/en/developer-terms/agreement-and-policy
Exibição pública permitida: a confirmar na revisão (por ora headline_link, sem reproduzir o texto integral).
Filtro de importância: processing/importance.py. Só entra desastre, vítimas, emergência; fofoca é descartada. Limiar em min_importance (padrão 45).
Papel: detecta rápido, nunca confirma sozinho (classe SOCIAL, peso baixo).
```
