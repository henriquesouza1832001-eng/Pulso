import { describe, expect, it } from "vitest";
import { BATCH, NOW, setup } from "./helpers/ingest";

/**
 * Estado por fonte (frescor + circuit breaker) e resumo do ciclo: persistência econômica, idempotente e que NUNCA derruba o dado
 * de verdade. Roda o Worker real sobre SQLite real (helpers/ingest.ts).
 */
type Row = Record<string, unknown>;
const runtime = (over: Row = {}) => ({ ...BATCH.source_runtime[0], ...over });
const only = (extra: Record<string, unknown>) => ({ batch_id: "obs-1", sources: [], events: [], signals: [], pulses: [], source_health: [], ...extra });
const dbRows = (s: ReturnType<typeof setup>, table: string) => s.sqlite.prepare(`SELECT * FROM ${table}`).all() as Row[];

describe("source_runtime: persistência econômica e idempotente", () => {
	it("grava, ignora reenvio idêntico e ignora estado mais VELHO; só o mais novo atualiza", async () => {
		const s = setup();
		const w = async (rows: Row[], id: string) => ((await (await s.post(only({ batch_id: id, source_runtime: rows }))).json()) as { budget: { written: number } }).budget.written;
		expect(await w([runtime()], "a")).toBe(1);
		expect(await w([runtime()], "b")).toBe(0); // reenvio idêntico (retry): nada
		expect(await w([runtime({ freshness_state: "STALE", updated_at: "2026-10-03T11:00:00Z" })], "c")).toBe(0); // atrasado: nunca regride
		expect(dbRows(s, "source_runtime")[0].freshness_state).toBe("FRESH");
		expect(await w([runtime({ freshness_state: "STALE", breaker_state: "OPEN", consecutive_failures: 3, opened_count: 1, next_attempt_at: "2026-10-03T12:20:00Z", breaker_reason: "OFFLINE", updated_at: "2026-10-03T12:05:00Z" })], "d")).toBe(1);
		const row = dbRows(s, "source_runtime")[0];
		expect(row).toMatchObject({ freshness_state: "STALE", breaker_state: "OPEN", consecutive_failures: 3, opened_count: 1, breaker_reason: "OFFLINE" });
	});

	it("engine_cycle: uma linha 'latest', só o ciclo mais novo substitui", async () => {
		const s = setup();
		const cyc = (at: string, records: number) => ({ ...BATCH.engine_cycle, cycle_at: at, records });
		await s.post(only({ batch_id: "c1", engine_cycle: cyc("2026-10-03T12:05:00Z", 10) }));
		await s.post(only({ batch_id: "c2", engine_cycle: cyc("2026-10-03T12:00:00Z", 99) })); // ciclo velho chegando atrasado
		expect(dbRows(s, "engine_cycle")).toHaveLength(1);
		expect(JSON.parse(dbRows(s, "engine_cycle")[0].summary as string).records).toBe(10);
		await s.post(only({ batch_id: "c3", engine_cycle: cyc("2026-10-03T12:10:00Z", 20) }));
		expect(JSON.parse(dbRows(s, "engine_cycle")[0].summary as string).records).toBe(20);
	});

	it("valor inválido é 400 (nunca 500): estado de frescor, breaker e contagem negativa", async () => {
		const s = setup();
		for (const bad of [runtime({ freshness_state: "ALEGRE" }), runtime({ breaker_state: "SEMI" }), runtime({ records: -1 }), runtime({ source_id: "Fonte Com Espaço" }), runtime({ transport: "OK" })]) {
			expect((await s.post(only({ source_runtime: [bad] }))).status).toBe(400);
		}
		expect((await s.post(only({ engine_cycle: { ...BATCH.engine_cycle, duration_s: -5 } }))).status).toBe(400);
		expect(dbRows(s, "source_runtime")).toHaveLength(0);
	});
});

describe("a observabilidade nunca custa dado de verdade", () => {
	it("tabela de observabilidade ausente (migration atrasada): 200, dado gravado, observability=failed", async () => {
		const s = setup();
		s.sqlite.exec("DROP TABLE source_runtime; DROP TABLE engine_cycle;");
		const r = await s.post(BATCH);
		const body = (await r.json()) as { ok: boolean; observability: string };
		expect(r.status).toBe(200);
		expect(body.observability).toBe("failed");
		expect((s.sqlite.prepare("SELECT COUNT(*) AS n FROM events").get() as { n: number }).n).toBe(1);
		expect((s.sqlite.prepare("SELECT COUNT(*) AS n FROM signals").get() as { n: number }).n).toBe(2);
	});

	it("lote sem observabilidade (Engine antigo) continua válido e reporta skipped", async () => {
		const s = setup();
		const { source_runtime: _a, engine_cycle: _b, ...old } = BATCH;
		const body = (await (await s.post(old)).json()) as { observability: string };
		expect(body.observability).toBe("skipped");
	});
});

describe("engine-status e rota do Engine", () => {
	it("agrega frescor por estado e família, breakers abertos e o último ciclo; veredito degrada com breaker aberto", async () => {
		const s = setup();
		await s.post(BATCH); // fonte-a FRESH (NEWS_HIGH), ciclo de NOW
		await s.post(only({ batch_id: "x", source_runtime: [runtime({ source_id: "fonte-b", freshness_state: "UNKNOWN", transport: "OFFLINE", breaker_state: "OPEN", consecutive_failures: 3, opened_count: 1, next_attempt_at: "2099-01-01T00:00:00Z", breaker_reason: "OFFLINE", updated_at: "2026-10-03T12:01:00Z" })] }));
		const st = (await (await s.getAdmin("/engine-status")).json()) as any;
		expect(st.freshness.by_state).toEqual({ FRESH: 1, UNKNOWN: 1 });
		expect(st.freshness.by_family.NEWS_HIGH).toEqual({ FRESH: 1 });
		expect(st.freshness.sources_reporting).toBe(2);
		expect(st.breakers.by_state.OPEN).toBe(1);
		expect(st.breakers.open[0]).toMatchObject({ source_id: "fonte-b", breaker_state: "OPEN" });
		expect(st.cycle.records).toBe(120);
		expect(st.engine.last_cycle_at).toBe(NOW);
		expect(st.schema.missing).toEqual([]);
		expect(st.verdict.status).toBe("degraded");
		expect(st.verdict.reasons.join(" ")).toMatch(/circuit breaker/);
		expect(JSON.stringify(st)).not.toMatch(/segredo-de-teste/); // nunca vaza segredo
	});

	it("sem as tabelas novas o engine-status responde 200, diz o que falta e não inventa zero", async () => {
		const s = setup();
		s.sqlite.exec("DROP TABLE source_runtime; DROP TABLE engine_cycle;");
		const r = await s.getAdmin("/engine-status");
		const st = (await r.json()) as any;
		expect(r.status).toBe(200);
		expect(st.schema.missing).toEqual(["source_runtime", "engine_cycle"]);
		expect(st.engine.reporting).toBe(false);
		expect(st.cycle).toBeNull();
		expect(st.freshness.sources_reporting).toBe(0);
	});

	it("/source-runtime devolve o estado ao Engine e vale para o token do ingest mesmo com ADMIN_TOKEN configurado", async () => {
		const s = setup();
		await s.post(BATCH);
		const withAdmin = { ADMIN_TOKEN: "token-do-operador" };
		const ok = await s.getAdmin("/source-runtime", "segredo-de-teste", withAdmin);
		expect(ok.status).toBe(200);
		expect(((await ok.json()) as any).source_runtime[0].source_id).toBe("fonte-a");
		expect((await s.getAdmin("/engine-status", "segredo-de-teste", withAdmin)).status).toBe(401); // rota de operador: só o ADMIN_TOKEN
		expect((await s.getAdmin("/engine-status", "token-do-operador", withAdmin)).status).toBe(200);
	});
});
