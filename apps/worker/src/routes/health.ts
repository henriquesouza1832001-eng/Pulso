import { Hono } from "hono";
import type { SourceHealth } from "@pulso/shared";
import type { AppEnv } from "../env";

export const health = new Hono<AppEnv>();

health.get("/", async (c) => {
	let db = "ONLINE";
	try {
		await c.env.DB.prepare("SELECT 1").first();
	} catch {
		db = "OFFLINE";
	}
	const { results } = await c.env.DB.prepare(
		`SELECT s.id AS source_id, s.name, COALESCE(h.status,'UNKNOWN') AS status,
		        h.last_success, h.detail
		 FROM sources s LEFT JOIN source_health h ON h.source_id = s.id
		 WHERE s.enabled = 1 ORDER BY s.name`,
	)
		.all<SourceHealth>()
		.catch(() => ({ results: [] as SourceHealth[] }));
	// Atraso da coleta: sem Pulso novo há mais de 15 min (3 ciclos), o sistema está "velho".
	const last = await c.env.DB.prepare("SELECT MAX(timestamp) AS t FROM pulse_history WHERE scope = 'BR'")
		.first<{ t: string | null }>()
		.catch(() => null);
	const ageSeconds = last?.t ? Math.max(0, Math.round((Date.now() - Date.parse(last.t)) / 1000)) : null;
	c.header("Cache-Control", "no-store");
	return c.json({
		api: "ONLINE",
		db,
		collection: {
			last_pulse_at: last?.t ?? null,
			age_seconds: ageSeconds,
			stale: ageSeconds === null || ageSeconds > 900,
			scheduler_configured: Boolean(c.env.GH_DISPATCH_TOKEN),
		},
		sources: results,
	});
});
