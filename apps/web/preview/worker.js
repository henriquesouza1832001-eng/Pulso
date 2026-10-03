// Prévia por branch (pulso-web-<branch>): serve o front e repassa SÓ leituras públicas da API.
// O repasse é feito no servidor, então a API de produção não precisa liberar CORS para a prévia.
const API = "https://pulso-api.henriquesouza.workers.dev";

export default {
	async fetch(request, env) {
		const url = new URL(request.url);
		if (url.pathname.startsWith("/api/")) {
			// Prévia é somente leitura: nada de ingestão nem rotas administrativas.
			if (request.method !== "GET" || url.pathname.startsWith("/api/admin")) {
				return Response.json({ error: "preview_read_only" }, { status: 403 });
			}
			const req = new Request(API + url.pathname + url.search, {
				headers: { accept: request.headers.get("accept") ?? "application/json" },
			});
			// Publicado: Service Binding (env.API). Local (wrangler dev sem a API rodando): fetch comum.
			const upstream = env.API ? await env.API.fetch(req) : await fetch(req);
			return new Response(upstream.body, { status: upstream.status, headers: upstream.headers });
		}
		// Só /api/* chega aqui (run_worker_first); o resto é servido direto pelos assets.
		return env.ASSETS.fetch(request);
	},
};
