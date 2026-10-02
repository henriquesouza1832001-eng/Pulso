import { Hono } from "hono";
import { z } from "zod";
import { CATEGORIES, EVENT_STATUSES, GEO_PRECISIONS, SOURCE_HEALTH } from "@pulso/shared";
import type { AppEnv } from "../env";

export const ingest = new Hono<AppEnv>();

const iso = z.iso.datetime();
const score = z.number().int().min(0).max(100);

const eventSchema = z.object({
	event_id: z.string().min(1).max(80),
	title: z.string().min(1).max(300),
	summary: z.string().max(2000).nullable(),
	category: z.enum(CATEGORIES),
	status: z.enum(EVENT_STATUSES),
	latitude: z.number().min(-35).max(6).nullable(),
	longitude: z.number().min(-75).max(-28).nullable(),
	geo_precision: z.enum(GEO_PRECISIONS).nullable(),
	geo_confidence: score.nullable(),
	state: z.string().length(2).nullable(),
	city: z.string().max(100).nullable(),
	severity: score,
	confidence: score,
	pulse: score,
	alert_level: z.number().int().min(1).max(5),
	score_breakdown: z
		.array(z.object({ key: z.string(), label: z.string(), points: z.number() }))
		.max(20),
	signal_count: z.number().int().min(0),
	source_count: z.number().int().min(0),
	detected_at: iso,
	updated_at: iso,
});

const batchSchema = z.object({
	batch_id: z.string().min(1).max(80),
	events: z.array(eventSchema).max(500),
	pulses: z
		.array(
			z.object({
				scope: z.string().regex(/^(BR|UF:[A-Z]{2}|CITY:[a-z0-9-]{1,80})$/),
				timestamp: iso,
				score,
				alert_level: z.number().int().min(1).max(5),
				contributors: z.array(z.object({ scope: z.string(), delta: z.number() })).max(10),
			}),
		)
		.max(200),
	source_health: z
		.array(
			z.object({
				source_id: z.string(),
				status: z.enum(SOURCE_HEALTH),
				last_success: iso.nullable(),
				detail: z.string().max(300).nullable(),
			}),
		)
		.max(200),
});

/** Comparação em tempo constante. */
function safeEqual(a: string, b: string) {
	if (a.length !== b.length) return false;
	let d = 0;
	for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
	return d === 0;
}

ingest.post("/", async (c) => {
	const token = c.env.INGEST_TOKEN;
	const given = (c.req.header("Authorization") ?? "").replace(/^Bearer /, "");
	// Sem segredo configurado, o endpoint fica fechado (fail-closed).
	if (!token || !safeEqual(given, token)) return c.json({ error: "unauthorized" }, 401);

	const parsed = batchSchema.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) {
		return c.json({ error: "invalid_batch", detail: parsed.error.issues[0]?.message }, 400);
	}
	const { events, pulses, source_health } = parsed.data;

	const db = c.env.DB;
	const stmts: D1PreparedStatement[] = [];
	// Idempotente: reenviar o mesmo lote não duplica nada (upsert por chave).
	for (const e of events) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO events (id,title,summary,category,status,latitude,longitude,geo_precision,geo_confidence,state,city,severity,confidence,pulse,alert_level,score_breakdown,signal_count,source_count,detected_at,updated_at)
			 VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)
			 ON CONFLICT(id) DO UPDATE SET title=excluded.title,summary=excluded.summary,category=excluded.category,status=excluded.status,
			   latitude=excluded.latitude,longitude=excluded.longitude,geo_precision=excluded.geo_precision,geo_confidence=excluded.geo_confidence,
			   state=excluded.state,city=excluded.city,severity=excluded.severity,confidence=excluded.confidence,pulse=excluded.pulse,
			   alert_level=excluded.alert_level,score_breakdown=excluded.score_breakdown,signal_count=excluded.signal_count,
			   source_count=excluded.source_count,updated_at=excluded.updated_at`,
				)
				.bind(
					e.event_id, e.title, e.summary, e.category, e.status, e.latitude, e.longitude,
					e.geo_precision, e.geo_confidence, e.state, e.city, e.severity, e.confidence, e.pulse,
					e.alert_level, JSON.stringify(e.score_breakdown), e.signal_count, e.source_count,
					e.detected_at, e.updated_at,
				),
		);
	}
	for (const p of pulses) {
		stmts.push(
			db
				.prepare(
					"INSERT OR REPLACE INTO pulse_history (scope,timestamp,score,alert_level,contributors) VALUES (?1,?2,?3,?4,?5)",
				)
				.bind(p.scope, p.timestamp, p.score, p.alert_level, JSON.stringify(p.contributors)),
		);
	}
	for (const h of source_health) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO source_health (source_id,status,last_check,last_success,detail) VALUES (?1,?2,?3,?4,?5)
			 ON CONFLICT(source_id) DO UPDATE SET status=excluded.status,last_check=excluded.last_check,last_success=excluded.last_success,detail=excluded.detail`,
				)
				.bind(h.source_id, h.status, new Date().toISOString(), h.last_success, h.detail),
		);
	}
	if (stmts.length) await db.batch(stmts);
	return c.json({ ok: true, events: events.length, pulses: pulses.length, source_health: source_health.length });
});
