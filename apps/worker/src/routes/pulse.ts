import { Hono, type Context } from "hono";
import { z } from "zod";
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
	// Variação em 2 h: só com um ponto REAL perto de 2 h atrás (±20 min). Sem ele, null: nunca comparar
	// com um ponto distante e apresentar como "variação das últimas 2 h".
	const target = Date.parse(row.timestamp) - 2 * 3600_000;
	const past = await db
		.prepare(
			`SELECT score FROM pulse_history WHERE scope = ?1 AND timestamp BETWEEN ?2 AND ?3
			 ORDER BY ABS(julianday(timestamp) - julianday(?4)) LIMIT 1`,
		)
		.bind(
			scope,
			new Date(target - 20 * 60_000).toISOString(),
			new Date(target + 20 * 60_000).toISOString(),
			new Date(target).toISOString(),
		)
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

const historyQuery = z.object({
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/).default("BR"),
	hours: z.coerce.number().int().min(1).max(168).default(24),
});

/** Série do Pulso para o gráfico "últimas 24 h" (pontos reais; lacunas ficam como lacunas). */
pulse.get("/history", async (c) => {
	const q = historyQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const since = new Date(Date.now() - q.data.hours * 3600_000).toISOString();
	const { results } = await c.env.DB.prepare(
		"SELECT timestamp, score, alert_level FROM pulse_history WHERE scope = ?1 AND timestamp >= ?2 ORDER BY timestamp ASC LIMIT 2100",
	)
		.bind(q.data.scope, since)
		.all<{ timestamp: string; score: number; alert_level: number }>();
	c.header("Cache-Control", cacheControl(30));
	return c.json({ scope: q.data.scope, hours: q.data.hours, points: results });
});

/** Pulso mais recente de cada UF com atividade (snapshots com mais de 30 min são descartados). */
pulse.get("/states", async (c) => {
	const since = new Date(Date.now() - 30 * 60_000).toISOString();
	const { results } = await c.env.DB.prepare(
		`SELECT substr(h.scope,4) AS uf, h.score, h.alert_level, h.timestamp
		 FROM pulse_history h
		 WHERE h.scope LIKE 'UF:%' AND h.timestamp >= ?1
		   AND h.timestamp = (SELECT MAX(timestamp) FROM pulse_history x WHERE x.scope = h.scope)
		 ORDER BY h.score DESC`,
	)
		.bind(since)
		.all<{ uf: string; score: number; alert_level: number; timestamp: string }>();
	c.header("Cache-Control", cacheControl(15));
	return c.json({ states: results });
});

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
