import type { Context, MiddlewareHandler } from "hono";
import type { AppEnv } from "../env";

/**
 * Envelope de erro uniforme. Toda resposta 4xx/5xx em JSON ganha `request_id` (o mesmo do cabeçalho `X-Request-Id`), sem trocar o
 * campo `error` que o front já lê: quem reporta um problema cita o id, e o log do Worker traz o mesmo id. Nunca stack trace público.
 */
export const requestContext: MiddlewareHandler<AppEnv> = async (c, next) => {
	const incoming = c.req.header("x-request-id");
	// Aceita o id do chamador só se for curto e inofensivo (ele vai para log e cabeçalho): senão gera um novo.
	const id = incoming && /^[A-Za-z0-9._-]{8,64}$/.test(incoming) ? incoming : crypto.randomUUID();
	c.set("requestId", id);
	await next();
	c.res.headers.set("X-Request-Id", id);
	if (c.res.status < 400 || !(c.res.headers.get("content-type") ?? "").includes("application/json")) return;
	try {
		const body = (await c.res.clone().json()) as unknown;
		if (body && typeof body === "object" && !Array.isArray(body) && !("request_id" in body)) {
			const headers = new Headers(c.res.headers);
			headers.delete("content-length");
			c.res = new Response(JSON.stringify({ ...(body as object), request_id: id }), { status: c.res.status, headers });
		}
	} catch {
		// corpo não era JSON legível: mantém a resposta original (o cabeçalho X-Request-Id já está nela)
	}
};

/** Teto do corpo de /api/ingest (o Engine divide o lote em partes bem menores que isto). */
export const INGEST_MAX_BYTES = 8 * 1024 * 1024;

/** Handler de erro não tratado: detalhe só no log (com o request_id); a resposta nunca vaza stack nem mensagem interna. */
export const errorHandler = (err: unknown, c: Context<AppEnv>) => {
	console.error("unhandled", c.get("requestId"), err);
	return c.json({ error: "internal_error" }, 500);
};
