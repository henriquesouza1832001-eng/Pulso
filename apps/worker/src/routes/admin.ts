import { Hono } from "hono";
import { z } from "zod";
import type { AppEnv } from "../env";
import { engineAuthorized } from "../lib/auth";
import { budgetMode, CRITICAL_FROM, DAILY_LIMIT, ECONOMY_FROM, utcDay } from "../lib/budget";
import { assess } from "../lib/status";
import { TursoDatabase } from "../lib/turso";

/** Rotas internas (Engine e painel admin). Nunca públicas, nunca cacheadas. */
export const admin = new Hono<AppEnv>();

admin.use("*", async (c, next) => {
	if (!engineAuthorized(c.req.header("Authorization"), c.env.INGEST_TOKEN)) {
		return c.json({ error: "unauthorized" }, 401);
	}
	c.header("Cache-Control", "no-store");
	await next();
});

/**
 * Confere os segredos do Turso DENTRO do Worker (os de produção, os do Wrangler): leitura, escrita transacional e
 * qual backend está ativo. Nunca devolve o token.
 */
admin.get("/turso-ping", async (c) => {
	if (!c.env.TURSO_URL || !c.env.TURSO_TOKEN) return c.json({ ok: false, error: "secrets_ausentes" }, 503);
	const t = new TursoDatabase({ url: c.env.TURSO_URL, token: c.env.TURSO_TOKEN });
	const t0 = Date.now();
	try {
		const v = await t.prepare("SELECT sqlite_version() AS v").first<{ v: string }>();
		const [w] = await t.batch([t.prepare("CREATE TABLE IF NOT EXISTS _worker_ping (k TEXT PRIMARY KEY, n INTEGER)"), t.prepare("INSERT INTO _worker_ping (k,n) VALUES ('x',1) ON CONFLICT(k) DO UPDATE SET n=n+1")]);
		const n = await t.prepare("SELECT n FROM _worker_ping WHERE k = 'x'").first<{ n: number }>("n" as never);
		return c.json({ ok: true, backend_ativo: c.env.DB instanceof TursoDatabase ? "turso" : "d1", sqlite: v?.v, ping_n: n, ms: Date.now() - t0, ddl_ok: w.success });
	} catch (e) {
		return c.json({ ok: false, error: String(e instanceof Error ? e.message : e).slice(0, 240) }, 502);
	}
});

const seriesQuery = z.object({
	hours: z.coerce.number().int().min(1).max(24 * 30).default(48),
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/).optional(),
});

/** Histórico de contagens para o baseline do Engine. */
admin.get("/series", async (c) => {
	const q = seriesQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		`SELECT scope, category, bucket, signals, sources FROM series
		 WHERE bucket >= ?1 AND (?2 IS NULL OR scope = ?2)
		 ORDER BY bucket DESC LIMIT 20000`,
	)
		.bind(since, q.data.scope ?? null)
		.all();
	// MAIS NOVAS primeiro: se passar do limite, perde as janelas antigas (o baseline suporta histórico curto), nunca as recentes.
	return c.json({ since, series: results });
});

const observationsQuery = z.object({
	hours: z.coerce.number().int().min(1).max(24 * 90).default(24 * 14),
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/).optional(),
	category: z.string().regex(/^[A-Z_]{2,20}$/).optional(),
	limit: z.coerce.number().int().min(1).max(50000).default(20000),
});

/** Histórico agregado por hora (base do baseline sazonal e das tendências). Mais novas primeiro, como /series. */
admin.get("/observations", async (c) => {
	const q = observationsQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		`SELECT scope, category, source_class, hour, signals, sources, duplicates FROM signal_observations
		 WHERE hour >= ?1 AND (?2 IS NULL OR scope = ?2) AND (?3 IS NULL OR category = ?3)
		 ORDER BY hour DESC LIMIT ?4`,
	)
		.bind(since, q.data.scope ?? null, q.data.category ?? null, q.data.limit)
		.all();
	return c.json({ since, observations: results });
});

const investigationsQuery = z.object({
	status: z.enum(["active", "all"]).default("active"),
	limit: z.coerce.number().int().min(1).max(1000).default(200),
});

/** Investigações do Sentinela. `active` = tudo que não está CLOSED. O Engine reconstrói o estado a partir daqui. */
admin.get("/investigations", async (c) => {
	const q = investigationsQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { results } = await c.env.DB.prepare(
		`SELECT id, scope, category, status, started_at, last_update, last_anomalous_at, initial_anomaly, anomaly,
		        evidence_count, official_confirmation, reasons
		 FROM investigations WHERE (?1 = 'all' OR status != 'CLOSED') ORDER BY last_update DESC LIMIT ?2`,
	)
		.bind(q.data.status, q.data.limit)
		.all();
	return c.json({ investigations: results });
});

const shadowQuery = z.object({
	method: z.string().regex(/^[a-z0-9_]{1,60}$/).optional(),
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/).optional(),
	limit: z.coerce.number().int().min(1).max(20000).default(5000),
});

/** V1 x V2 x desfecho: matéria-prima do portão de promoção (validation/shadow_compare.promotion_gate). */
admin.get("/shadow-results", async (c) => {
	const q = shadowQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { results } = await c.env.DB.prepare(
		`SELECT item_id, method, scope, p_v1, p_v2, outcome, created_at FROM shadow_results
		 WHERE (?1 IS NULL OR method = ?1) AND (?2 IS NULL OR scope = ?2) ORDER BY created_at DESC LIMIT ?3`,
	)
		.bind(q.data.method ?? null, q.data.scope ?? null, q.data.limit)
		.all();
	return c.json({ shadow_results: results });
});

const driversQuery = z.object({
	state: z.enum(["CANDIDATE", "TESTING", "ACTIVE", "DEGRADED", "DISABLED"]).optional(),
	limit: z.coerce.number().int().min(1).max(2000).default(500),
});

/** Registro de drivers antecedentes (só ACTIVE pode alterar a probabilidade de uma previsão). */
admin.get("/drivers", async (c) => {
	const q = driversQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { results } = await c.env.DB.prepare(
		`SELECT driver, target, scope, lag_hours, correlation, pairs, samples, brier_without, brier_with, state, reason, updated_at
		 FROM driver_registry WHERE (?1 IS NULL OR state = ?1) ORDER BY updated_at DESC LIMIT ?2`,
	)
		.bind(q.data.state ?? null, q.data.limit)
		.all();
	return c.json({ drivers: results });
});

const calibratorsQuery = z.object({
	status: z.enum(["candidate", "active", "retired"]).optional(),
	limit: z.coerce.number().int().min(1).max(200).default(50),
});

/** Calibradores versionados (artefato + status). O Engine usa só o `active`; o histórico fica para auditoria. */
admin.get("/calibrators", async (c) => {
	const q = calibratorsQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { results } = await c.env.DB.prepare(
		`SELECT id, method, version, fit_start, fit_end, sample_count, artifact, status, created_at FROM calibrators
		 WHERE (?1 IS NULL OR status = ?1) ORDER BY created_at DESC LIMIT ?2`,
	)
		.bind(q.data.status ?? null, q.data.limit)
		.all();
	return c.json({ calibrators: results });
});

const trajectoryQuery = z.object({
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
	metric: z.string().regex(/^[a-z_]{1,40}$/),
	hours: z.coerce.number().int().min(1).max(24 * 30).default(48),
});

/**
 * TRAJETÓRIA das previsões de um escopo e métrica ao longo do tempo (12:00 18%, 12:15 27%, ... evento): como a previsão evoluiu e
 * como terminou. A tabela `forecasts` é imutável, então cada ponto é uma previsão distinta e nenhuma foi reescrita. Se a
 * previsão tiver `evidence.shadow_v2`, a probabilidade do V2 em sombra vem junto para comparar as duas trajetórias.
 */
admin.get("/forecast-trajectory", async (c) => {
	const q = trajectoryQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		`SELECT id, threshold, probability, interval_low, interval_high, method, method_version, created_at, resolves_at, status, outcome, observed_value, evidence
		 FROM forecasts WHERE scope = ?1 AND metric = ?2 AND created_at >= ?3 ORDER BY created_at ASC LIMIT 2000`,
	)
		.bind(q.data.scope, q.data.metric, since)
		.all<Record<string, unknown>>();
	const points = results.map(({ evidence, ...rest }) => {
		let v2: number | null = null;
		try {
			const ev = typeof evidence === "string" ? JSON.parse(evidence) : null;
			v2 = typeof ev?.shadow_v2?.probability === "number" ? ev.shadow_v2.probability : null;
		} catch {
			v2 = null;
		}
		return { ...rest, p_v2_shadow: v2 };
	});
	return c.json({ scope: q.data.scope, metric: q.data.metric, since, points });
});

const registryQuery = z.object({
	hours: z.coerce.number().int().min(1).max(24 * 180).default(72),
	forecast_id: z.string().regex(/^fc-[a-z0-9-]{1,100}$/).optional(),
});

/** Trilha de auditoria. Sem `forecast_id`: só os ids já registrados (o Engine envia apenas o que falta). Com ele: a entrada completa. */
admin.get("/forecast-registry", async (c) => {
	const q = registryQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	if (q.data.forecast_id) {
		const row = await c.env.DB.prepare("SELECT forecast_id, created_at, snapshot, snapshot_hash FROM forecast_registry WHERE forecast_id = ?1")
			.bind(q.data.forecast_id)
			.first();
		return row ? c.json({ entry: row }) : c.json({ error: "not_found" }, 404);
	}
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare("SELECT forecast_id FROM forecast_registry WHERE created_at >= ?1 ORDER BY created_at DESC LIMIT 5000")
		.bind(since)
		.all();
	return c.json({ forecast_ids: results.map((r) => (r as { forecast_id: string }).forecast_id) });
});

const signalsQuery = z.object({
	hours: z.coerce.number().int().min(1).max(72).default(24),
});

/** Sinais recentes, para o Engine agrupar com estado (reaproveitar o event_id de cada história). */
admin.get("/signals", async (c) => {
	const q = signalsQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		`SELECT id AS signal_id, source_id, source_class, timestamp, collected_at, title, text, url, canonical_url,
		        author, category, latitude, longitude, geo_precision, geo_confidence, state, city, reliability, hash, event_id
		 FROM signals WHERE timestamp >= ?1 ORDER BY timestamp DESC LIMIT 10000`,
	)
		.bind(since)
		.all();
	// MAIS NOVOS primeiro: se passar do limite, descarta os antigos (já quase fora da janela), nunca os recentes.
	return c.json({ since, signals: results });
});

const digestQuery = z.object({
	hours: z.coerce.number().int().min(1).max(72).default(24),
});

/**
 * Resumo dos eventos já gravados (só o que decide se vale reescrever). O Engine envia apenas eventos novos ou
 * que mudaram: o D1 gratuito limita as linhas escritas por dia, e reenviar centenas de eventos iguais a cada
 * 5 min estouraria o limite.
 */
admin.get("/events-digest", async (c) => {
	const q = digestQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		`SELECT id AS event_id, pulse, alert_level, status, signal_count, source_count
		 FROM events WHERE updated_at >= ?1 ORDER BY updated_at DESC LIMIT 5000`,
	)
		.bind(since)
		.all();
	return c.json({ since, events: results });
});

const pulseHistoryQuery = z.object({
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/).default("BR"),
	hours: z.coerce.number().int().min(1).max(24 * 30).default(72),
});

/** Série do Pulso por escopo: matéria-prima dos previsores e da resolução. */
admin.get("/pulse-history", async (c) => {
	const q = pulseHistoryQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		"SELECT timestamp, score FROM pulse_history WHERE scope = ?1 AND timestamp >= ?2 ORDER BY timestamp ASC LIMIT 20000",
	)
		.bind(q.data.scope, since)
		.all();
	return c.json({ scope: q.data.scope, since, points: results });
});

/** Previsões ainda abertas, para o Engine resolver as que venceram. */
admin.get("/forecasts/open", async (c) => {
	const { results } = await c.env.DB.prepare(
		`SELECT id AS forecast_id, kind, question, scope, metric, comparator, threshold, method, method_version,
		        probability, interval_low, interval_high, horizon_minutes, created_at, resolves_at, evidence
		 FROM forecasts WHERE status = 'open' ORDER BY resolves_at ASC LIMIT 1000`,
	).all();
	return c.json({ forecasts: results });
});

/** Visão do painel admin: volume por fonte nas últimas 24 h e estado de saúde. */
/**
 * Painel do motor em uma chamada: banco ativo, orçamento de escrita do dia (e o modo do governador) e o que cada camada do V2
 * já acumulou (investigações, auditoria de previsões, comparação V1 x V2, drivers). Serve ao dono, ao Reliability Gate e ao red team.
 * `promotion.shadow_samples` é o que o portão de promoção conta (mínimo de 200 desfechos resolvidos).
 */
admin.get("/engine-status", async (c) => {
	const day = utcDay();
	const t0 = Date.now();
	try {
		const budget = await c.env.DB.prepare("SELECT rows FROM write_budget WHERE day = ?1").bind(day).first<{ rows: number }>();
		const counts = await c.env.DB.prepare(
			`SELECT
			   (SELECT COUNT(*) FROM investigations WHERE status != 'CLOSED') AS investigations_active,
			   (SELECT COUNT(*) FROM investigations) AS investigations_total,
			   (SELECT COUNT(*) FROM forecasts WHERE status = 'open') AS forecasts_open,
			   (SELECT COUNT(*) FROM forecasts WHERE status = 'resolved') AS forecasts_resolved,
			   (SELECT COUNT(*) FROM forecast_registry) AS forecast_registry,
			   (SELECT COUNT(*) FROM shadow_results) AS shadow_results,
			   (SELECT COUNT(*) FROM driver_registry WHERE state = 'ACTIVE') AS drivers_active,
			   (SELECT COUNT(*) FROM driver_registry) AS drivers_total,
			   (SELECT COUNT(*) FROM calibrators WHERE status = 'active') AS calibrators_active,
			   (SELECT COUNT(*) FROM calibrators) AS calibrators_total,
			   (SELECT MAX(timestamp) FROM pulse_history WHERE scope = 'BR') AS last_pulse_at,
			   (SELECT MAX(hour) FROM signal_observations) AS observations_last_hour,
			   (SELECT COUNT(*) FROM (SELECT 1 FROM signal_observations LIMIT 200000)) AS observations_rows`,
		).first<Record<string, number | string | null>>();
		const used = budget?.rows ?? 0;
		const lastPulse = typeof counts?.last_pulse_at === "string" ? counts.last_pulse_at : null;
		const health = assess({
			dbOk: true,
			dbLatencyMs: Date.now() - t0,
			collectionAgeSeconds: lastPulse ? Math.max(0, Math.round((Date.now() - Date.parse(lastPulse)) / 1000)) : null,
			budgetMode: budgetMode(used),
			investigationsActive: Number(counts?.investigations_active ?? 0),
		});
		return c.json({
			verdict: health, // {status: ok|degraded|not_ready, reasons[]}: a resposta curta para o operador
			backend: c.env.DB instanceof TursoDatabase ? "turso" : "d1", // o banco REALMENTE em uso (a variável sozinha mentiria sem os segredos)
			write_budget: { day, rows_today: used, mode: budgetMode(used), economy_from: ECONOMY_FROM, critical_from: CRITICAL_FROM, daily_limit: DAILY_LIMIT },
			...counts,
			promotion: { min_samples: 200, shadow_samples: counts?.shadow_results ?? 0 },
		});
	} catch (e) {
		return c.json({ error: "engine_status_failed", detail: String(e instanceof Error ? e.message : e).slice(0, 200) }, 500);
	}
});

admin.get("/overview", async (c) => {
	const since = new Date(Date.now() - 24 * 3600_000).toISOString();
	const [bySource, totals] = await Promise.all([
		c.env.DB.prepare(
			`SELECT s.id AS source_id, s.name, s.source_class, COALESCE(h.status,'UNKNOWN') AS status,
			        h.last_success, h.detail,
			        (SELECT COUNT(*) FROM signals g WHERE g.source_id = s.id AND g.collected_at >= ?1) AS signals_24h
			 FROM sources s LEFT JOIN source_health h ON h.source_id = s.id ORDER BY s.name`,
		)
			.bind(since)
			.all(),
		c.env.DB.prepare(
			`SELECT (SELECT COUNT(*) FROM events WHERE resolved_at IS NULL) AS active_events,
			        (SELECT COUNT(*) FROM signals WHERE collected_at >= ?1) AS signals_24h,
			        (SELECT MAX(timestamp) FROM pulse_history WHERE scope='BR') AS last_pulse_at,
			        (SELECT COUNT(*) FROM series) AS series_points,
			        (SELECT COUNT(*) FROM investigations WHERE status != 'CLOSED') AS active_investigations`,
		)
			.bind(since)
			.first(),
	]);
	return c.json({ totals, sources: bySource.results });
});
