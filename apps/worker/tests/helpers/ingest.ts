import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Hono } from "hono";
import { admin } from "../../src/routes/admin";
import { ingest } from "../../src/routes/ingest";
import { errorHandler, requestContext } from "../../src/lib/http";
import type { AppEnv } from "../../src/env";
import { mockHrana, type Fault } from "./hrana";

/** Harness de ingest compartilhado: Worker REAL (/api/ingest) sobre SQLite real (Hrana de mentira, com injeção de falha). */
export const MIGRATIONS = [join(__dirname, "../../../../database/migrations"), join(__dirname, "../../../../database/pending")];
export const TABLES = ["sources", "events", "signals", "pulse_history", "source_health", "series", "forecasts", "signal_observations", "investigations", "forecast_registry", "calibrators", "source_runtime", "engine_cycle"];
export const NOW = "2026-10-03T12:00:00Z";

export function setup(fault?: (n: number, body: any) => Fault | undefined) {
	const m = mockHrana(fault);
	for (const dir of MIGRATIONS) {
		for (const f of readdirSync(dir).filter((x) => x.endsWith(".sql")).sort()) m.sqlite.exec(readFileSync(join(dir, f), "utf8"));
	}
	const app = new Hono<AppEnv>();
	app.use("*", requestContext);
	app.onError(errorHandler);
	app.route("/api/ingest", ingest);
	app.route("/api/admin", admin);
	const env = (extra: Record<string, string> = {}) => ({ DB: m.db, INGEST_TOKEN: "segredo-de-teste", ALLOWED_ORIGINS: "", GITHUB_REPO: "x/y", ...extra }) as never;
	const post = (batch: unknown) =>
		app.request("/api/ingest", { method: "POST", headers: { Authorization: "Bearer segredo-de-teste", "Content-Type": "application/json" }, body: JSON.stringify(batch) }, env());
	const getAdmin = (path: string, token = "segredo-de-teste", extra: Record<string, string> = {}) =>
		app.request(`/api/admin${path}`, { headers: { Authorization: `Bearer ${token}` } }, env(extra));
	const counts = () => Object.fromEntries(TABLES.map((t) => [t, (m.sqlite.prepare(`SELECT COUNT(*) AS c FROM ${t}`).get() as { c: number }).c]));
	return { ...m, post, getAdmin, counts };
}

export const forecast = {
	forecast_id: "fc-chaos-1", kind: "QUANTITY", question: "Pulso BR >= 60 em 1h?", scope: "BR", metric: "pulse_score", comparator: "gte", threshold: 60,
	method: "ewma_v1", method_version: "1", probability: 0.2, interval_low: 0.1, interval_high: 0.3, horizon_minutes: 60, created_at: NOW,
	resolves_at: "2026-10-03T13:00:00Z", evidence: {}, status: "open", outcome: null, observed_value: null, resolved_at: null, brier: null,
};
export const BATCH = {
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
	source_runtime: [{ source_id: "fonte-a", transport: "ONLINE", freshness_state: "FRESH", newest_item_age_min: 12.5, last_content_advance: NOW, records: 10, new_records: 3, duplicate_records: 1, breaker_state: "CLOSED", consecutive_failures: 0, next_attempt_at: null, opened_count: 0, breaker_reason: null, updated_at: NOW }],
	engine_cycle: { cycle_at: NOW, duration_s: 41.2, sources_due: 20, sources_skipped: 0, records: 120, new_records: 30, duplicate_records: 5, signals_sent: 2, events: 1, freshness: { FRESH: 15, STALE: 3, EMPTY: 1, QUIET: 1, UNKNOWN: 0 }, coverage: { NEWS_HIGH: { FRESH: 15, ready_ratio: 0.8 } }, age: { n: 18, p50: 40, p95: 600, max: 900 }, breakers_open: 0, flags: { SOURCE_FRESHNESS: true }, engine_ref: "abc1234" },
	calibrators: [{ id: "cal-platt-v1", method: "platt", version: "v1", fit_start: "2026-09-01T00:00:00Z", fit_end: "2026-09-30T00:00:00Z", sample_count: 250, artifact: '{"a":1}', status: "candidate", created_at: NOW }],
};
export const onlyWrite = (f: Fault) => (_n: number, body: any) => (body.requests?.[0]?.type === "batch" ? f : undefined);
