import { Hono } from "hono";
import type { SourceHealth } from "@pulso/shared";
import type { AppEnv } from "../env";
import { assess } from "../lib/status";

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

/** LIVENESS: o Worker responde. Não toca o banco de propósito: serve para saber se o processo está vivo, nada mais. */
health.get("/live", (c) => {
	c.header("Cache-Control", "no-store");
	return c.json({ status: "alive" });
});

/**
 * READINESS: o sistema consegue SERVIR dados. Worker 200 + banco fora = vivo, mas NÃO PRONTO (503). Coleta atrasada ou orçamento
 * em economia = pronto porém `degraded` (200, com os motivos), para o front mostrar STALE/PARTIAL em vez de fingir normalidade.
 */
health.get("/ready", async (c) => {
	const t0 = Date.now();
	let dbOk = true;
	let lastPulse: string | null = null;
	try {
		const r = await c.env.DB.prepare("SELECT MAX(timestamp) AS t FROM pulse_history WHERE scope = 'BR'").first<{ t: string | null }>();
		lastPulse = r?.t ?? null;
	} catch {
		dbOk = false;
	}
	const a = assess({
		dbOk,
		dbLatencyMs: dbOk ? Date.now() - t0 : null,
		collectionAgeSeconds: lastPulse ? Math.max(0, Math.round((Date.now() - Date.parse(lastPulse)) / 1000)) : null,
		budgetMode: "normal", // o orçamento é assunto do operador (engine-status); readiness pública não o expõe
		investigationsActive: 0,
	});
	c.header("Cache-Control", "no-store");
	return c.json({ status: a.status === "ok" ? "ready" : a.status, reasons: a.reasons, db: dbOk ? "ONLINE" : "OFFLINE", last_pulse_at: lastPulse }, a.status === "not_ready" ? 503 : 200);
});
