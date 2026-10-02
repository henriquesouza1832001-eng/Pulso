/** Estratégia de cache por endpoint (ver docs/api/API.md). Valores em segundos. */
export const cacheControl = (maxAge: number, swr = maxAge * 3) =>
	`public, max-age=${maxAge}, stale-while-revalidate=${swr}`;
