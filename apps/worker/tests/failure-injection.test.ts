import { describe, expect, it } from "vitest";
import type { Fault } from "./helpers/hrana";
import { BATCH, onlyWrite, setup, TABLES } from "./helpers/ingest";

/**
 * Injeção de falha complementar ao storage-chaos (docs/reliability/FAILURE_INJECTION_REPORT.md): o que a matriz anterior não
 * cobria — limite de taxa e DNS do banco, reenvio em massa (10 e 100 vezes) e ciclos repetidos de "commit + resposta perdida".
 */
const OPTIONAL = ["signal_observations", "investigations", "forecast_registry", "calibrators", "source_runtime", "engine_cycle", "shadow_results", "driver_registry"];
const spent = (s: ReturnType<typeof setup>) => (s.sqlite.prepare("SELECT COALESCE(SUM(rows),0) AS r FROM write_budget").get() as { r: number }).r;
const dump = (s: ReturnType<typeof setup>, t: string) => JSON.stringify(s.sqlite.prepare(`SELECT * FROM ${t}`).all());

describe("banco com limite de taxa ou DNS fora", () => {
	it.each<[string, Fault]>([["HTTP 429 do banco", "http429"], ["DNS do banco não resolve", "dns"]])("%s: 500 com request_id, sem vazar detalhe, nada gravado; o reenvio grava uma vez", async (_n, kind) => {
		const clean = setup();
		await clean.post(BATCH);
		const expected = clean.counts();

		let armed = true;
		const s = setup((n, body) => (armed ? onlyWrite(kind)(n, body) : undefined));
		const r = await s.post(BATCH);
		const txt = await r.text();
		expect(r.status).toBe(500);
		expect(JSON.parse(txt).request_id).toBeTruthy();
		expect(txt).not.toMatch(/turso|429|ENOTFOUND|getaddrinfo|rate limited/i); // nada do backend vaza para o chamador
		expect(Object.values(s.counts()).every((n) => n === 0)).toBe(true);

		armed = false;
		expect((await s.post(BATCH)).status).toBe(200);
		expect(s.counts()).toEqual(expected);
	});

	it.each<[string, Fault]>([["HTTP 429", "http429"], ["DNS", "dns"]])("%s permanente: liveness 200, readiness 503 (vivo != pronto)", async (_n, kind) => {
		const s = setup(() => kind);
		expect((await s.get("/api/health/live")).status).toBe(200);
		const ready = await s.get("/api/health/ready");
		expect(ready.status).toBe(503);
		expect(((await ready.json()) as { status: string }).status).toBe("not_ready");
	});
});

describe("idempotência em massa: o mesmo ciclo reenviado 1, 2, 3, 10 e 100 vezes", () => {
	it.each([1, 2, 3, 10, 100])("%i reenvio(s): nenhuma linha nova e nenhum conteúdo alterado (só o batimento de saúde)", async (times) => {
		const s = setup();
		expect((await s.post(BATCH)).status).toBe(200);
		const before = s.counts();
		const stable = TABLES.filter((t) => t !== "source_health" && t !== "sources");
		const content = Object.fromEntries(stable.map((t) => [t, dump(s, t)]));
		for (let i = 0; i < times; i++) expect((await s.post(BATCH)).status).toBe(200);
		expect(s.counts()).toEqual(before);
		for (const t of stable) expect(dump(s, t), t).toBe(content[t]);
	}, 60_000);
});

describe("write_budget sob 'commit + resposta perdida + retry' repetido", () => {
	it("10 ciclos seguidos: dado nunca duplica e o contador nunca desce nem fica abaixo do realmente gravado", async () => {
		const clean = setup();
		const firstReal = ((await (await clean.post(BATCH)).json()) as { budget: { written: number } }).budget.written;
		const expected = clean.counts();

		let lose = true;
		const s = setup((n, body) => (lose ? onlyWrite("after")(n, body) : undefined));
		let last = 0;
		for (let i = 0; i < 10; i++) {
			lose = i % 2 === 0; // perde a resposta, depois o retry dá certo, e assim por diante
			await s.post(BATCH);
			const now = spent(s);
			expect(now, `ciclo ${i}`).toBeGreaterThanOrEqual(last); // contador monotônico: nunca "devolve" escrita
			expect(now, `ciclo ${i}`).toBeGreaterThanOrEqual(firstReal); // nunca subconta o que foi confirmado
			last = now;
		}
		const core = (c: Record<string, number>) => ({ ...c, ...Object.fromEntries(OPTIONAL.map((t) => [t, 0])) });
		expect(core(s.counts())).toEqual(core(expected)); // nenhuma linha de produto duplicada
		lose = false;
		await s.post(BATCH);
		expect(s.counts()).toEqual(expected); // o último retry completa o opcional, sem duplicar
	});
});

describe("sanitização de erro do painel do operador", () => {
	it.each<[string, Fault]>([["HTTP 500", "http500"], ["DNS", "dns"], ["HTTP 429", "http429"]])("engine-status com banco fora (%s): 500 com request_id e sem a mensagem interna do driver", async (_n, kind) => {
		const s = setup(() => kind);
		const r = await s.getAdmin("/engine-status");
		const txt = await r.text();
		expect(r.status).toBe(500);
		expect(JSON.parse(txt)).toMatchObject({ error: "engine_status_failed" });
		expect(JSON.parse(txt).request_id).toBeTruthy();
		expect(txt).not.toMatch(/turso|boom|ENOTFOUND|getaddrinfo|rate limited|sqlite|no such table/i);
	});
});

describe("CORS: só as origens configuradas recebem Access-Control-Allow-Origin", () => {
	const SITE = "https://pulso-web.henriquesouza.workers.dev";
	const ALLOWED = { ALLOWED_ORIGINS: `${SITE},http://localhost:5173` };
	const acao = (r: Response) => r.headers.get("access-control-allow-origin");

	it("origem do site: GET e preflight do ingest ecoam a origem exata (nunca '*')", async () => {
		const s = setup();
		expect(acao(await s.raw("/api/health", { headers: { Origin: SITE } }, ALLOWED))).toBe(SITE);
		const pre = await s.raw("/api/ingest", { method: "OPTIONS", headers: { Origin: SITE, "Access-Control-Request-Method": "POST" } }, ALLOWED);
		expect(acao(pre)).toBe(SITE);
	});

	it.each(["https://evil.example", "null", `${SITE}.evil.example`, "https://evil.example/https://pulso-web.henriquesouza.workers.dev", SITE.toUpperCase()])(
		"origem estranha (%s): sem Access-Control-Allow-Origin no GET nem no preflight",
		async (origin) => {
			const s = setup();
			expect(acao(await s.raw("/api/health", { headers: { Origin: origin } }, ALLOWED))).toBeNull();
			const pre = await s.raw("/api/ingest", { method: "OPTIONS", headers: { Origin: origin, "Access-Control-Request-Method": "POST" } }, ALLOWED);
			expect(acao(pre)).toBeNull();
		},
	);

	it("sem nenhuma origem configurada, nenhuma origem é liberada (fail-closed)", async () => {
		const s = setup();
		expect(acao(await s.raw("/api/health", { headers: { Origin: SITE } }, { ALLOWED_ORIGINS: "" }))).toBeNull();
	});
});
