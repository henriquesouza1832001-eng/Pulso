import { Hono } from "hono";
import { z } from "zod";
import { CATEGORIES, EVENT_STATUSES, GEO_PRECISIONS, SOURCE_CLASSES, SOURCE_HEALTH } from "@pulso/shared";
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

const sourceSchema = z.object({
	id: z.string().regex(/^[a-z0-9-]{1,60}$/),
	name: z.string().min(1).max(100),
	domain: z.string().max(100).nullable(),
	adapter: z.string().max(20),
	source_class: z.enum(SOURCE_CLASSES),
	url: z.string().url().max(500),
	state: z.string().length(2).nullable(),
});

const signalSchema = z.object({
	signal_id: z.string().min(1).max(80),
	source_id: z.string().min(1).max(60),
	source_class: z.enum(SOURCE_CLASSES),
	timestamp: iso,
	collected_at: iso,
	title: z.string().min(1).max(400),
	text: z.string().max(1000).nullable(),
	url: z.string().url().max(1000).nullable(),
	category: z.enum(CATEGORIES),
	latitude: z.number().min(-35).max(6).nullable(),
	longitude: z.number().min(-75).max(-28).nullable(),
	geo_precision: z.enum(GEO_PRECISIONS).nullable(),
	geo_confidence: score.nullable(),
	reliability: score,
	event_id: z.string().max(80).nullable(),
	hash: z.string().min(8).max(100),
	canonical_url: z.string().max(1000).nullable(),
	author: z.string().max(200).nullable(),
	state: z.string().length(2).nullable(),
	city: z.string().max(100).nullable(),
});

const batchSchema = z.object({
	batch_id: z.string().min(1).max(80),
	sources: z.array(sourceSchema).max(100),
	events: z.array(eventSchema).max(200),
	signals: z.array(signalSchema).max(500),
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
	const { sources, events, signals, pulses, source_health } = parsed.data;

	const db = c.env.DB;
	const stmts: D1PreparedStatement[] = [];
	// Idempotente: reenviar o mesmo lote não duplica nada (upsert por chave).
	for (const src of sources) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO sources (id,name,domain,adapter,source_class,url,state) VALUES (?1,?2,?3,?4,?5,?6,?7)
			 ON CONFLICT(id) DO UPDATE SET name=excluded.name,domain=excluded.domain,adapter=excluded.adapter,source_class=excluded.source_class,url=excluded.url,state=excluded.state`,
				)
				.bind(src.id, src.name, src.domain, src.adapter, src.source_class, src.url, src.state),
		);
	}
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
	// Sinais depois dos eventos (FK). Reenvio atualiza só o vínculo com o evento (dedup por hash).
	for (const g of signals) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO signals (id,source_id,source_class,timestamp,collected_at,title,text,url,canonical_url,author,category,latitude,longitude,geo_precision,geo_confidence,state,city,reliability,hash,event_id)
			 VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)
			 ON CONFLICT(hash) DO UPDATE SET event_id=excluded.event_id,category=excluded.category,state=excluded.state,city=excluded.city`,
				)
				.bind(
					g.signal_id, g.source_id, g.source_class, g.timestamp, g.collected_at, g.title, g.text, g.url,
					g.canonical_url, g.author, g.category, g.latitude, g.longitude, g.geo_precision, g.geo_confidence,
					g.state, g.city, g.reliability, g.hash, g.event_id,
				),
		);
	}
	// Fontes por evento, recalculadas a partir dos sinais gravados.
	for (const pair of new Set(signals.filter((g) => g.event_id).map((g) => `${g.event_id}|${g.source_id}`))) {
		const [eventId, sourceId] = pair.split("|");
		stmts.push(
			db
				.prepare(
					`INSERT INTO event_sources (event_id,source_id,signal_count,first_seen)
			 SELECT ?1,?2,COUNT(*),MIN(timestamp) FROM signals WHERE event_id=?1 AND source_id=?2
			 ON CONFLICT(event_id,source_id) DO UPDATE SET signal_count=excluded.signal_count,first_seen=excluded.first_seen`,
				)
				.bind(eventId, sourceId),
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
	return c.json({ ok: true, sources: sources.length, signals: signals.length, events: events.length, pulses: pulses.length, source_health: source_health.length });
});
