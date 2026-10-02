import { Hono, type Context } from "hono";
import type { PulseSnapshot } from "@pulso/shared";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";

export const pulse = new Hono<AppEnv>();

const LABELS = ["", "NORMAL", "ATENÇÃO", "ELEVADO", "CRÍTICO", "EMERGÊNCIA"];

async function snapshot(db: D1Database, scope: string): Promise<PulseSnapshot | null> {
	const row = await db
		.prepare(
			"SELECT timestamp, score, alert_level, contributors FROM pulse_history WHERE scope = ?1 ORDER BY timestamp DESC LIMIT 1",
		)
		.bind(scope)
		.first<{ timestamp: string; score: number; alert_level: number; contributors: string }>();
	if (!row) return null;
	const past = await db
		.prepare(
			"SELECT score FROM pulse_history WHERE scope = ?1 AND timestamp <= ?2 ORDER BY timestamp DESC LIMIT 1",
		)
		.bind(scope, new Date(Date.parse(row.timestamp) - 2 * 3600_000).toISOString())
		.first<{ score: number }>();
	let contributors: PulseSnapshot["contributors"] = [];
	try {
		contributors = JSON.parse(row.contributors);
	} catch {
		// ignora contributors corrompidos
	}
	return {
		scope,
		timestamp: row.timestamp,
		score: row.score,
		alert_level: row.alert_level as PulseSnapshot["alert_level"],
		label: LABELS[row.alert_level] ?? "NORMAL",
		contributors,
		delta_2h: past ? row.score - past.score : null,
	};
}

async function respond(c: Context<AppEnv>, scope: string) {
	const snap = await snapshot(c.env.DB, scope);
	c.header("Cache-Control", cacheControl(10));
	// Sem dados ainda: score 0, nível 1. Nunca inventar atividade.
	return c.json(
		snap ?? {
			scope,
			timestamp: new Date().toISOString(),
			score: 0,
			alert_level: 1,
			label: "NORMAL",
			contributors: [],
			delta_2h: null,
		},
	);
}

pulse.get("/", (c) => respond(c, "BR"));
pulse.get("/br", (c) => respond(c, "BR"));
pulse.get("/state/:uf", (c) => {
	const uf = c.req.param("uf").toUpperCase();
	if (!/^[A-Z]{2}$/.test(uf)) return c.json({ error: "invalid_uf" }, 400);
	return respond(c, `UF:${uf}`);
});
pulse.get("/city/:slug", (c) => {
	const slug = c.req.param("slug").toLowerCase();
	if (!/^[a-z0-9-]{1,80}$/.test(slug)) return c.json({ error: "invalid_city" }, 400);
	return respond(c, `CITY:${slug}`);
});
