/**
 * Comparação em tempo constante. O laço percorre o SEGREDO (`b`), nunca a entrada: o tempo não depende do que o
 * chamador envia, então não revela o comprimento do segredo; a diferença de comprimento entra no resultado.
 */
export function safeEqual(a: string, b: string) {
	let d = a.length ^ b.length;
	for (let i = 0; i < b.length; i++) d |= (a.charCodeAt(i) || 0) ^ b.charCodeAt(i);
	return d === 0;
}

/** Autoriza o Engine via `Authorization: Bearer <INGEST_TOKEN>`. Sem segredo configurado, fecha tudo (fail-closed). */
export function engineAuthorized(authHeader: string | undefined, token: string | undefined): boolean {
	if (!token) return false;
	const m = /^Bearer (.+)$/.exec(authHeader ?? ""); // o esquema é obrigatório: o token cru, sem "Bearer ", não vale
	return m !== null && safeEqual(m[1], token);
}

/** Rotas internas que o ENGINE lê para operar (o Engine só tem o INGEST_TOKEN). As demais são de OPERADOR. */
export const ENGINE_READ_ROUTES = new Set(["/series", "/signals", "/observations", "/investigations", "/events-digest", "/pulse-history", "/forecasts/open", "/source-runtime"]);

/**
 * Menor privilégio nas rotas `/api/admin/*`.
 * - Rota que o Engine usa: vale `INGEST_TOKEN` ou `ADMIN_TOKEN`.
 * - Rota de operador (status, calibradores, registro, ping do banco...): se `ADMIN_TOKEN` existe, SÓ ele vale: quem tem o token de
 *   escrita do ingest não lê o painel. Sem `ADMIN_TOKEN`, cai no `INGEST_TOKEN` (compatibilidade até o dono criar o segredo).
 */
export function adminAuthorized(authHeader: string | undefined, env: { INGEST_TOKEN?: string; ADMIN_TOKEN?: string }, path: string): boolean {
	const isEngineRoute = ENGINE_READ_ROUTES.has(path);
	if (env.ADMIN_TOKEN && engineAuthorized(authHeader, env.ADMIN_TOKEN)) return true;
	if (env.ADMIN_TOKEN && !isEngineRoute) return false; // separado: o token do ingest não abre rota de operador
	return engineAuthorized(authHeader, env.INGEST_TOKEN);
}
