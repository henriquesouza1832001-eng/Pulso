import { Hono } from "hono";
import { z } from "zod";
import { CATEGORIES, EVENT_STATUSES, GEO_PRECISIONS, SOURCE_CLASSES, SOURCE_HEALTH } from "@pulso/shared";
import type { AppEnv } from "../env";
import { engineAuthorized } from "../lib/auth";

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
	series: z
		.array(
			z.object({
				scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
				category: z.enum(CATEGORIES),
				bucket: iso,
				signals: z.number().int().min(0).max(100000),
				sources: z.number().int().min(0).max(1000),
			}),
		)
		.max(3000)
		.default([]),
});

const SERIES_RETENTION_DAYS = 90;

ingest.post("/", async (c) => {
	if (!engineAuthorized(c.req.header("Authorization"), c.env.INGEST_TOKEN)) {
		return c.json({ error: "unauthorized" }, 401);
	}

	const parsed = batchSchema.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) {
		return c.json({ error: "invalid_batch", detail: parsed.error.issues[0]?.message }, 400);
	}
	const { sources, events, signals, pulses, source_health, series } = parsed.data;

	const db = c.env.DB;
	// O D1 limita as consultas por invocação (50 no plano gratuito): uma instrução por tabela,
	// lendo o array JSON com json_each. Ordem respeita as chaves estrangeiras.
	// Idempotente: reenviar o mesmo lote não duplica nada (upsert por chave).
	const stmts: D1PreparedStatement[] = [];
	const json = (v: unknown) => JSON.stringify(v);
	const f = (path: string) => `json_extract(j.value,'$.${path}')`;

	if (sources.length) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO sources (id,name,domain,adapter,source_class,url,state)
			 SELECT ${f("id")},${f("name")},${f("domain")},${f("adapter")},${f("source_class")},${f("url")},${f("state")}
			 FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET name=excluded.name,domain=excluded.domain,adapter=excluded.adapter,source_class=excluded.source_class,url=excluded.url,state=excluded.state`,
				)
				.bind(json(sources)),
		);
	}
	if (events.length) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO events (id,title,summary,category,status,latitude,longitude,geo_precision,geo_confidence,state,city,severity,confidence,pulse,alert_level,score_breakdown,signal_count,source_count,detected_at,updated_at)
			 SELECT ${f("event_id")},${f("title")},${f("summary")},${f("category")},${f("status")},${f("latitude")},${f("longitude")},${f("geo_precision")},${f("geo_confidence")},${f("state")},${f("city")},${f("severity")},${f("confidence")},${f("pulse")},${f("alert_level")},${f("score_breakdown")},${f("signal_count")},${f("source_count")},${f("detected_at")},${f("updated_at")}
			 FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET title=excluded.title,summary=excluded.summary,category=excluded.category,status=excluded.status,
			   latitude=excluded.latitude,longitude=excluded.longitude,geo_precision=excluded.geo_precision,geo_confidence=excluded.geo_confidence,
			   state=excluded.state,city=excluded.city,severity=excluded.severity,confidence=excluded.confidence,pulse=excluded.pulse,
			   alert_level=excluded.alert_level,score_breakdown=excluded.score_breakdown,signal_count=excluded.signal_count,
			   source_count=excluded.source_count,updated_at=excluded.updated_at`,
				)
				.bind(json(events)),
		);
	}
	if (signals.length) {
		// Reenvio atualiza só o vínculo com o evento (dedup por hash).
		stmts.push(
			db
				.prepare(
					`INSERT INTO signals (id,source_id,source_class,timestamp,collected_at,title,text,url,canonical_url,author,category,latitude,longitude,geo_precision,geo_confidence,state,city,reliability,hash,event_id)
			 SELECT ${f("signal_id")},${f("source_id")},${f("source_class")},${f("timestamp")},${f("collected_at")},${f("title")},${f("text")},${f("url")},${f("canonical_url")},${f("author")},${f("category")},${f("latitude")},${f("longitude")},${f("geo_precision")},${f("geo_confidence")},${f("state")},${f("city")},${f("reliability")},${f("hash")},${f("event_id")}
			 FROM json_each(?1) j WHERE true
			 ON CONFLICT(hash) DO UPDATE SET event_id=excluded.event_id,category=excluded.category,state=excluded.state,city=excluded.city`,
				)
				.bind(json(signals)),
		);
		// Retenção: sinais ficam 90 dias (docs/COLLECTION_PROTOCOL.md §7).
		stmts.push(
			db
				.prepare("DELETE FROM signals WHERE timestamp < ?1")
				.bind(new Date(Date.now() - SERIES_RETENTION_DAYS * 86400_000).toISOString()),
		);
		// Fontes por evento, recalculadas a partir dos sinais gravados.
		stmts.push(
			db
				.prepare(
					`INSERT INTO event_sources (event_id,source_id,signal_count,first_seen)
			 SELECT event_id,source_id,COUNT(*),MIN(timestamp) FROM signals
			 WHERE event_id IN (SELECT DISTINCT json_extract(value,'$.event_id') FROM json_each(?1))
			 GROUP BY event_id,source_id
			 ON CONFLICT(event_id,source_id) DO UPDATE SET signal_count=excluded.signal_count,first_seen=excluded.first_seen`,
				)
				.bind(json(signals.map((g) => ({ event_id: g.event_id })))),
		);
	}
	if (pulses.length) {
		stmts.push(
			db
				.prepare(
					`INSERT OR REPLACE INTO pulse_history (scope,timestamp,score,alert_level,contributors)
			 SELECT ${f("scope")},${f("timestamp")},${f("score")},${f("alert_level")},${f("contributors")} FROM json_each(?1) j`,
				)
				.bind(json(pulses)),
		);
	}
	if (source_health.length) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO source_health (source_id,status,last_check,last_success,detail)
			 SELECT ${f("source_id")},${f("status")},?2,${f("last_success")},${f("detail")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(source_id) DO UPDATE SET status=excluded.status,last_check=excluded.last_check,last_success=excluded.last_success,detail=excluded.detail`,
				)
				.bind(json(source_health), new Date().toISOString()),
		);
	}
	if (series.length) {
		// A janela pode ser reenviada com contagem menor (o feed já descartou itens antigos):
		// nunca reduzimos o que já foi observado, e reenvio é idempotente.
		stmts.push(
			db
				.prepare(
					`INSERT INTO series (scope,category,bucket,signals,sources)
			 SELECT ${f("scope")},${f("category")},${f("bucket")},${f("signals")},${f("sources")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(scope,category,bucket) DO UPDATE SET signals=MAX(signals,excluded.signals),sources=MAX(sources,excluded.sources)`,
				)
				.bind(json(series)),
		);
		// Retenção: contagens agregadas ficam 90 dias.
		stmts.push(
			db
				.prepare("DELETE FROM series WHERE bucket < ?1")
				.bind(new Date(Date.now() - SERIES_RETENTION_DAYS * 86400_000).toISOString()),
		);
	}
	if (stmts.length) await db.batch(stmts);
	return c.json({
		ok: true,
		sources: sources.length,
		signals: signals.length,
		events: events.length,
		pulses: pulses.length,
		source_health: source_health.length,
		series: series.length,
	});
});
