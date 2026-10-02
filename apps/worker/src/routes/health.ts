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
	c.header("Cache-Control", "no-store");
	return c.json({ api: "ONLINE", db, sources: results });
});
