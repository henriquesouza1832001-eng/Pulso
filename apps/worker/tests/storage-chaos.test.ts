import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { Hono } from "hono";
import { ingest } from "../src/routes/ingest";
import { errorHandler, requestContext } from "../src/lib/http";
import type { AppEnv } from "../src/env";
import { mockHrana, type Fault } from "./helpers/hrana";

/**
 * ENSAIO DE FALHA DO STORAGE (RT-005). O adaptador Turso, sob falha induzida, nunca pode: perder dado confirmado, duplicar ao
 * reenviar, nem deixar escrita parcial. Roda o `/api/ingest` REAL sobre SQLite real (via Hrana de mentira com injeção de falha).
 * Não prova o servidor remoto: prova a lógica do Worker e do adaptador diante de rede caída, resposta perdida e HTTP 5xx.
 */
const MIGRATIONS = [join(__dirname, "../../../database/migrations"), join(__dirname, "../../../database/pending")];
const TABLES = ["sources", "events", "signals", "pulse_history", "source_health", "series", "forecasts", "signal_observations", "investigations", "forecast_registry", "calibrators"];
const NOW = "2026-10-03T12:00:00Z";

function setup(fault?: (n: number, body: any) => Fault | undefined) {
	const m = mockHrana(fault);
	for (const dir of MIGRATIONS) {
		for (const f of readdirSync(dir).filter((x) => x.endsWith(".sql")).sort()) m.sqlite.exec(readFileSync(join(dir, f), "utf8"));
	}
	const app = new Hono<AppEnv>();
	app.use("*", requestContext);
	app.onError(errorHandler);
	app.route("/api/ingest", ingest);
	const post = (batch: unknown) =>
		app.request("/api/ingest", { method: "POST", headers: { Authorization: "Bearer segredo-de-teste", "Content-Type": "application/json" }, body: JSON.stringify(batch) }, { DB: m.db, INGEST_TOKEN: "segredo-de-teste", ALLOWED_ORIGINS: "", GITHUB_REPO: "x/y" } as never);
	const counts = () => Object.fromEntries(TABLES.map((t) => [t, (m.sqlite.prepare(`SELECT COUNT(*) AS c FROM ${t}`).get() as { c: number }).c]));
	return { ...m, post, counts };
}

const forecast = {
	forecast_id: "fc-chaos-1", kind: "QUANTITY", question: "Pulso BR >= 60 em 1h?", scope: "BR", metric: "pulse_score", comparator: "gte", threshold: 60,
	method: "ewma_v1", method_version: "1", probability: 0.2, interval_low: 0.1, interval_high: 0.3, horizon_minutes: 60, created_at: NOW,
	resolves_at: "2026-10-03T13:00:00Z", evidence: {}, status: "open", outcome: null, observed_value: null, resolved_at: null, brier: null,
};
const BATCH = {
	batch_id: "chaos-1",
	sources: [{ id: "fonte-a", name: "Fonte A", domain: "a.com", adapter: "rss", source_class: "NEWS_HIGH", url: "https://a.com/rss", state: null }],
	events: [{ event_id: "ev-1", title: "Evento de teste", summary: null, category: "TRAFFIC", status: "DETECTED", latitude: null, longitude: null, geo_precision: null, geo_confidence: null, state: "SP", city: null, severity: 40, confidence: 50, pulse: 45, alert_level: 2, score_breakdown: [], signal_count: 2, source_count: 1, detected_at: NOW, updated_at: NOW }],
	signals: [1, 2].map((i) => ({ signal_id: `sg-${i}`, source_id: "fonte-a", source_class: "NEWS_HIGH", timestamp: NOW, collected_at: NOW, title: `Sinal ${i}`, text: null, url: null, category: "TRAFFIC", latitude: null, longitude: null, geo_precision: null, geo_confidence: null, reliability: 70, event_id: "ev-1", hash: `hash-numero-${i}`, canonical_url: null, author: null, state: "SP", city: null })),
	pulses: [{ scope: "BR", timestamp: NOW, score: 45, alert_level: 2, contributors: [] }],
	source_health: [{ source_id: "fonte-a", status: "ONLINE", last_success: NOW, detail: null }],
	series: [{ scope: "BR", category: "TRAFFIC", bucket: NOW, signals: 2, sources: 1 }],
	forecasts: [forecast],
	observations: [{ scope: "BR", category: "TRAFFIC", source_class: "NEWS_HIGH", hour: "2026-10-03T11:00:00Z", signals: 2, sources: 1, duplicates: 0 }],
	investigations: [{ id: "inv-0123456789", scope: "BR", category: "TRAFFIC", status: "NEW", started_at: NOW, last_update: NOW, last_anomalous_at: NOW, initial_anomaly: 3, anomaly: 3, evidence_count: 2, official_confirmation: false, reasons: ["teste"] }],
	forecast_registry: [{ forecast_id: "fc-chaos-1", created_at: NOW, snapshot: '{"a":1}', snapshot_hash: "a".repeat(64) }],
	calibrators: [{ id: "cal-platt-v1", method: "platt", version: "v1", fit_start: "2026-09-01T00:00:00Z", fit_end: "2026-09-30T00:00:00Z", sample_count: 250, artifact: '{"a":1}', status: "candidate", created_at: NOW }],
};
const onlyWrite = (f: Fault) => (_n: number, body: any) => (body.requests?.[0]?.type === "batch" ? f : undefined);

describe("ensaio de falha: ingest sobre Turso", () => {
	it("referência: lote limpo grava tudo uma vez; no reenvio idêntico só o batimento de saúde das fontes muda", async () => {
		const s = setup();
		const r1 = await s.post(BATCH);
		expect(r1.status, JSON.stringify(await r1.clone().json())).toBe(200);
		const base = s.counts();
		expect(Object.values(base).every((n) => n >= 1)).toBe(true);
		const dump = () => JSON.stringify(TABLES.map((x) => s.sqlite.prepare(`SELECT * FROM ${x}`).all()).map((rows, i) => [TABLES[i], rows]));
		const before = JSON.parse(dump());
		const r2 = (await (await s.post(BATCH)).json()) as { budget: { written: number } };
		const after = JSON.parse(dump());
		const changed = before.filter((b: any, i: number) => JSON.stringify(b) !== JSON.stringify(after[i])).map((b: any) => b[0]);
		// `source_health` é ESTADO de batimento (last_check/last_success avançam a cada ciclo por desenho), não evento: é a única exceção, e é 1 linha por fonte.
		expect(changed).toEqual(["source_health"]);
		expect(r2.budget.written).toBe(1); // só a linha do batimento
		expect(s.counts()).toEqual(base);
	});

	it.each<[string, Fault]>([["rede cai antes do servidor agir", "before"], ["servidor responde HTTP 500", "http500"]])("%s: 5xx com request_id, NADA gravado, e o reenvio grava exatamente uma vez", async (_name, kind) => {
		const clean = setup();
		await clean.post(BATCH);
		const expected = clean.counts();

		let armed = true;
		const s = setup((n, body) => (armed ? onlyWrite(kind)(n, body) : undefined));
		const r = await s.post(BATCH);
		const body = (await r.json()) as { error: string; request_id: string };
		expect(r.status).toBe(500);
		expect(body.error).toBe("internal_error");
		expect(body.request_id).toBeTruthy();
		expect(Object.values(s.counts()).every((n) => n === 0)).toBe(true); // sem escrita parcial

		armed = false; // a rede volta: o Engine reenvia o MESMO lote
		expect((await s.post(BATCH)).status).toBe(200);
		expect(s.counts()).toEqual(expected);
	});

	it("resposta PERDIDA depois do commit: o dado está lá e o reenvio não duplica nada", async () => {
		const clean = setup();
		await clean.post(BATCH);
		const expected = clean.counts();

		let armed = true;
		const s = setup((n, body) => (armed ? onlyWrite("after")(n, body) : undefined));
		const lost = await s.post(BATCH);
		expect(lost.status).toBe(500); // o Engine não sabe se gravou: vai reenviar
		expect(s.counts()).toEqual(expected); // mas o servidor JÁ gravou: nada se perdeu

		armed = false;
		const retry = (await (await s.post(BATCH)).json()) as { budget: { written: number } };
		expect(retry.budget.written).toBe(1); // idempotente: só o batimento de saúde (1 linha) muda; nenhuma linha nova
		expect(s.counts()).toEqual(expected);
	});

	it("limitação conhecida e VISÍVEL: com a resposta perdida, o contador de orçamento fica abaixo do real (subestima, nunca superestima)", async () => {
		let armed = true;
		const s = setup((n, body) => (armed ? onlyWrite("after")(n, body) : undefined));
		await s.post(BATCH);
		const spent = (s.sqlite.prepare("SELECT COALESCE(SUM(rows),0) AS r FROM write_budget").get() as { r: number }).r;
		expect(spent).toBe(0); // gravou linhas, mas não contou: o governador pode ser otimista por um lote (documentado em BACKEND_HARDENING.md)
	});

	it("lote que falha NO MEIO desfaz tudo (transação do adaptador)", async () => {
		const s = setup();
		await s.db.exec("CREATE TABLE IF NOT EXISTS parcial (id TEXT PRIMARY KEY)");
		const stmts = [s.db.prepare("INSERT INTO parcial VALUES (?1)").bind("a"), s.db.prepare("INSERT INTO parcial VALUES (?1)").bind("b"), s.db.prepare("INSERT INTO parcial VALUES (?1)").bind("a")];
		await expect(s.db.batch(stmts)).rejects.toThrow(/turso_batch_failed/);
		expect((s.sqlite.prepare("SELECT COUNT(*) AS c FROM parcial").get() as { c: number }).c).toBe(0);
	});
});
