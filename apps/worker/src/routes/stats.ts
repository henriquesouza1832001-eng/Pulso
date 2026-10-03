import { Hono } from "hono";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";

export const stats = new Hono<AppEnv>();

/**
 * Números do cabeçalho do indicador nacional, calculados no servidor com a janela correta
 * (o front não deve somar `signal_count` dos eventos: isso mistura janelas de até 24 h).
 */
stats.get("/", async (c) => {
	const now = Date.now();
	const since24 = new Date(now - 24 * 3600_000).toISOString();
	const since2h = new Date(now - 2 * 3600_000).toISOString();
	const row = await c.env.DB.prepare(
		`SELECT
		   (SELECT COUNT(*) FROM events WHERE resolved_at IS NULL AND updated_at >= ?1) AS active_events,
		   (SELECT COUNT(DISTINCT state) FROM events WHERE resolved_at IS NULL AND updated_at >= ?1 AND state IS NOT NULL) AS states_active,
		   (SELECT COUNT(*) FROM events WHERE resolved_at IS NULL AND updated_at >= ?1 AND alert_level >= 3) AS alerts,
		   (SELECT COUNT(*) FROM signals WHERE timestamp >= ?2) AS signals_2h,
		   (SELECT COUNT(*) FROM signals WHERE timestamp >= ?1) AS signals_24h,
		   (SELECT COUNT(*) FROM source_health WHERE status = 'ONLINE') AS sources_online,
		   (SELECT COUNT(*) FROM sources WHERE enabled = 1) AS sources_total,
		   (SELECT MAX(timestamp) FROM pulse_history WHERE scope = 'BR') AS last_pulse_at`,
	)
		.bind(since24, since2h)
		.first();
	c.header("Cache-Control", cacheControl(15));
	return c.json({ ...row, generated_at: new Date(now).toISOString() });
});
