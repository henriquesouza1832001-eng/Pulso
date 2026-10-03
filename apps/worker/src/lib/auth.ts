/** Comparação em tempo constante. */
function safeEqual(a: string, b: string) {
	if (a.length !== b.length) return false;
	let d = 0;
	for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
	return d === 0;
}

/** Autoriza o Engine via `Authorization: Bearer <INGEST_TOKEN>`. Sem segredo configurado, fecha tudo (fail-closed). */
export function engineAuthorized(authHeader: string | undefined, token: string | undefined): boolean {
	if (!token) return false;
	return safeEqual((authHeader ?? "").replace(/^Bearer /, ""), token);
}
