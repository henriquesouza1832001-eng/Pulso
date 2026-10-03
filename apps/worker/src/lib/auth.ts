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
