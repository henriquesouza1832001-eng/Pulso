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
		 ORDER BY bucket ASC LIMIT 20000`,
	)
		.bind(since, q.data.scope ?? null)
		.all();
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
		 FROM signals WHERE timestamp >= ?1 ORDER BY timestamp ASC LIMIT 5000`,
	)
		.bind(since)
		.all();
	return c.json({ since, signals: results });
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
