import { Hono } from "hono";
import { z } from "zod";
import type { AppEnv } from "../env";
import { engineAuthorized } from "../lib/auth";

/** Rotas internas (Engine e painel admin). Nunca públicas, nunca cacheadas. */
export const admin = new Hono<AppEnv>();

admin.use("*", async (c, next) => {
	if (!engineAuthorized(c.req.header("Authorization"), c.env.INGEST_TOKEN)) {
		return c.json({ error: "unauthorized" }, 401);
	}
	c.header("Cache-Control", "no-store");
	await next();
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
			        (SELECT COUNT(*) FROM series) AS series_points`,
		)
			.bind(since)
			.first(),
	]);
	return c.json({ totals, sources: bySource.results });
});
