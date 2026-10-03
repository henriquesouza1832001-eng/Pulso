import { describe, expect, it } from "vitest";
import { BATCH, setup } from "./helpers/ingest";

/**
 * AUTH E ABUSO DE ENTRADA (RT-007). Worker REAL sobre SQLite real. Regra: entrada ruim é 4xx com `request_id`, NUNCA 5xx e nunca vaza
 * stack. O que o CÓDIGO protege está aqui; o que depende de borda (rate limit/WAF) não pode ser provado por teste de código e está
 * marcado como EDGE em docs/engineering/BACKEND_HARDENING.md.
 */
const TOKEN = "segredo-de-teste";
const ADMIN = { ADMIN_TOKEN: "token-do-operador" };
const post = (s: ReturnType<typeof setup>, body: BodyInit | null, headers: Record<string, string> = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" }) =>
	s.raw("/api/ingest", { method: "POST", headers, body });

describe("autenticação: INGEST_TOKEN x ADMIN_TOKEN (menor privilégio)", () => {
	it("ingest só aceita o INGEST_TOKEN: o token de operador NÃO escreve lote", async () => {
		const s = setup();
		const r = await s.raw("/api/ingest", { method: "POST", headers: { Authorization: "Bearer token-do-operador", "Content-Type": "application/json" }, body: JSON.stringify(BATCH) }, ADMIN);
		expect(r.status).toBe(401);
		expect((s.sqlite.prepare("SELECT COUNT(*) AS n FROM events").get() as { n: number }).n).toBe(0);
	});

	it("o token do ingest não abre rota de operador quando ADMIN_TOKEN existe, mas abre as rotas do Engine", async () => {
		const s = setup();
		expect((await s.getAdmin("/engine-status", TOKEN, ADMIN)).status).toBe(401);
		expect((await s.getAdmin("/calibrators", TOKEN, ADMIN)).status).toBe(401);
		expect((await s.getAdmin("/observations", TOKEN, ADMIN)).status).toBe(200);
		expect((await s.getAdmin("/engine-status", "token-do-operador", ADMIN)).status).toBe(200);
	});

	it.each([
		["sem cabeçalho", undefined],
		["esquema errado (Basic)", "Basic c2VncmVkbw=="],
		["Bearer vazio", "Bearer "],
		["bearer minúsculo", `bearer ${TOKEN}`],
		["token cru, sem esquema", TOKEN],
		["token com sufixo", `Bearer ${TOKEN}x`],
		["token com prefixo", `Bearer x${TOKEN}`],
		["dois tokens no mesmo cabeçalho (duplicado combinado)", `Bearer ${TOKEN}, Bearer ${TOKEN}`],
		["token com espaço no meio", `Bearer ${TOKEN} extra`],
		["muito longo (10 KB)", `Bearer ${"a".repeat(10_000)}`],
	])("ingest e admin recusam: %s", async (_n, auth) => {
		const s = setup();
		const headers: Record<string, string> = auth === undefined ? {} : { Authorization: auth };
		const i = await s.raw("/api/ingest", { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(BATCH) });
		const a = await s.raw("/api/admin/engine-status", { headers });
		expect([i.status, a.status]).toEqual([401, 401]);
		expect(((await i.json()) as { request_id: string }).request_id).toBeTruthy();
	});

	it("sem segredo configurado o ingest e o admin ficam FECHADOS (fail-closed), mesmo com um token qualquer", async () => {
		const s = setup();
		const noSecret = { INGEST_TOKEN: "" };
		const i = await s.raw("/api/ingest", { method: "POST", headers: { Authorization: "Bearer ", "Content-Type": "application/json" }, body: JSON.stringify(BATCH) }, noSecret);
		const a = await s.raw("/api/admin/engine-status", { headers: { Authorization: "Bearer " } }, noSecret);
		expect([i.status, a.status]).toEqual([401, 401]);
	});

	it("rajada de tentativas erradas nunca autoriza e nunca vira 5xx (o freio em si é de borda: EDGE/WAF)", async () => {
		const s = setup();
		const codes = await Promise.all(Array.from({ length: 60 }, (_, i) => s.getAdmin("/engine-status", `errado-${i}`).then((r) => r.status)));
		expect(new Set(codes)).toEqual(new Set([401]));
	});
});

describe("entrada inválida no ingest: 4xx, nunca 5xx, nunca stack", () => {
	const cases: [string, () => BodyInit | null][] = [
		["corpo vazio", () => ""],
		["JSON truncado", () => '{"batch_id":"x","sources":[{"id":'],
		["texto que não é JSON", () => "isto não é json"],
		["NaN literal", () => '{"batch_id":"x","sources":[],"events":[],"signals":[],"pulses":[{"scope":"BR","timestamp":"2026-10-03T12:00:00Z","score":NaN,"alert_level":2,"contributors":[]}],"source_health":[]}'],
		["array no lugar do objeto", () => "[1,2,3]"],
		["null", () => "null"],
		["número no lugar do objeto", () => "42"],
		["JSON profundamente aninhado (100 mil níveis)", () => "[".repeat(100_000) + "]".repeat(100_000)],
		["UTF-8 inválido", () => new Uint8Array([0x7b, 0x22, 0xff, 0xfe, 0x22, 0x3a, 0x31, 0x7d])],
		["número que estoura para Infinity (1e999)", () => '{"batch_id":"x","sources":[],"events":[],"signals":[],"pulses":[{"scope":"BR","timestamp":"2026-10-03T12:00:00Z","score":1e999,"alert_level":2,"contributors":[]}],"source_health":[]}'],
		["campo gigante (título de 1 MB)", () => JSON.stringify({ ...BATCH, events: [{ ...BATCH.events[0], title: "x".repeat(1_000_000) }] })],
		["lista gigante (10 mil eventos)", () => JSON.stringify({ ...BATCH, events: Array.from({ length: 10_000 }, () => BATCH.events[0]) })],
		["tipos trocados", () => JSON.stringify({ ...BATCH, batch_id: 123, sources: "nao-e-lista" })],
		["id de lote vazio", () => JSON.stringify({ ...BATCH, batch_id: "" })],
	];
	it.each(cases)("%s", async (_n, body) => {
		const s = setup();
		const r = await post(s, body());
		const txt = await r.text();
		expect(r.status).toBeGreaterThanOrEqual(400);
		expect(r.status).toBeLessThan(500);
		expect(txt).not.toMatch(/at .*\.(ts|js):\d+|node_modules|SyntaxError|RangeError/); // nunca stack nem mensagem interna
		expect(JSON.parse(txt).request_id).toBeTruthy();
		expect((s.sqlite.prepare("SELECT COUNT(*) AS n FROM events").get() as { n: number }).n).toBe(0); // nada gravado
	});

	it("corpo acima do teto é 413 ANTES de ser lido (8 MB)", async () => {
		const s = setup();
		const r = await post(s, "a".repeat(9 * 1024 * 1024));
		expect(r.status).toBe(413);
	});

	it("texto parecido com SQL é só texto: gravado literal, com parâmetros, e a tabela continua existindo", async () => {
		const s = setup();
		const evil = "x'); DROP TABLE events;-- \" OR 1=1";
		const r = await post(s, JSON.stringify({ ...BATCH, events: [{ ...BATCH.events[0], title: evil }] }));
		expect(r.status).toBe(200);
		const row = s.sqlite.prepare("SELECT title FROM events").get() as { title: string };
		expect(row.title).toBe(evil);
	});

	it("ingest só aceita POST; outros métodos não executam nada", async () => {
		const s = setup();
		for (const method of ["GET", "PUT", "DELETE", "PATCH"]) {
			const r = await s.raw("/api/ingest", { method, headers: { Authorization: `Bearer ${TOKEN}` } });
			expect([404, 405]).toContain(r.status);
		}
	});
});

describe("entrada inválida nas rotas públicas: 400, nunca 500", () => {
	const bad = [
		"/api/events?limit=999999", "/api/events?limit=-1", "/api/events?limit=0", "/api/events?limit=NaN", "/api/events?limit=Infinity", "/api/events?limit=1e400",
		"/api/events?limit=abc", "/api/events?limit=1.5", "/api/events?limit=", "/api/events?category=%3Cscript%3E", "/api/events?state=%27%20OR%201%3D1", "/api/events?state=SPP",
		`/api/events?category=${"A".repeat(5000)}`,
		"/api/history?days=0", "/api/history?days=9999", "/api/history?min_level=1", "/api/history?min_level=6", "/api/history?limit=-5", "/api/history?days=NaN",
		"/api/forecasts?limit=100000", "/api/forecasts?status=hacked", "/api/forecasts?scope=ZZ%3B", "/api/forecasts?scope=UF%3Asp",
		"/api/pulse/history?hours=0", "/api/pulse/history?hours=100000", "/api/pulse/history?scope=XX", "/api/pulse/history?scope=BR%27--",
	];
	it.each(bad)("%s", async (path) => {
		const s = setup();
		const r = await s.get(path);
		expect(r.status, path).toBe(400);
		expect(((await r.json()) as { request_id: string }).request_id).toBeTruthy();
	});

	it("parâmetro desconhecido, repetido e 'offset/cursor' (que não existem) são ignorados com segurança, sem erro", async () => {
		const s = setup();
		for (const path of ["/api/events?offset=-5", "/api/events?cursor=%00%00", "/api/events?limit=5&limit=500", "/api/events?x=1&x=2", "/api/forecasts?cursor=lixo"]) {
			const r = await s.get(path);
			expect(r.status, path).toBeLessThan(500);
		}
	});

	it("id e slug absurdos (SQL, 10 mil caracteres, unicode, bytes nulos) dão 404/400, nunca 500", async () => {
		const s = setup();
		const ids = ["x'%20OR%20'1'='1", "a".repeat(10_000), "%E2%80%AE%F0%9F%92%A5", "%00", "..%2f..%2fetc%2fpasswd", "DROP%20TABLE%20events"];
		for (const id of ids) {
			for (const base of ["/api/events/", "/api/forecasts/", "/api/pulse/state/", "/api/pulse/city/"]) {
				const r = await s.get(`${base}${id}`);
				expect(r.status, `${base}${id.slice(0, 30)}`).toBeLessThan(500);
			}
		}
		expect((s.sqlite.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE name = 'events'").get() as { n: number }).n).toBe(1);
	});

	it("rotas públicas são só GET (POST não executa nada)", async () => {
		const s = setup();
		for (const path of ["/api/events", "/api/pulse", "/api/forecasts", "/api/map", "/api/stats"]) {
			const r = await s.raw(path, { method: "POST", body: "{}" });
			expect([404, 405]).toContain(r.status);
		}
	});

	it("o 500 interno nunca vaza mensagem: banco quebrado devolve internal_error com request_id", async () => {
		const s = setup();
		s.sqlite.exec("DROP TABLE events;");
		const r = await s.get("/api/events");
		const txt = await r.text();
		expect(r.status).toBe(500);
		expect(txt).not.toMatch(/no such table|sqlite|events/i);
		expect(JSON.parse(txt)).toMatchObject({ error: "internal_error" });
	});
});

describe("rotas admin: entrada inválida e método", () => {
	it("parâmetros fora do contrato nas rotas admin são 400, nunca 500", async () => {
		const s = setup();
		for (const path of ["/series?hours=0", "/series?hours=100000", "/series?scope=XX", "/observations?hours=-1", "/investigations?limit=99999", "/calibrators?status=hacked", "/forecast-trajectory?scope=ZZ&metric=a", "/forecast-trajectory?scope=BR&metric=A%27--", "/shadow-results?limit=-1"]) {
			const r = await s.getAdmin(path);
			expect(r.status, path).toBe(400);
		}
	});
});
