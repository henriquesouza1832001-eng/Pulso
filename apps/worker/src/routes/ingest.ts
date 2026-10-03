import { Hono } from "hono";
import { z } from "zod";
import {
	CATEGORIES,
	EVENT_STATUSES,
	BREAKER_STATES,
	CALIBRATOR_STATUSES,
	FRESHNESS_STATES,
	DRIVER_STATES,
	FORECAST_KINDS,
	GEO_PRECISIONS,
	INVESTIGATION_STATUSES,
	SOURCE_CLASSES,
	SOURCE_HEALTH,
} from "@pulso/shared";
import type { AppEnv } from "../env";
import { budgetMode, RESERVE_FIXED, RESERVE_ROWS_PER_ITEM, shedBatch, utcDay } from "../lib/budget";
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

export const forecastSchema = z
	.object({
		forecast_id: z.string().regex(/^fc-[a-z0-9-]{1,100}$/),
		kind: z.enum(FORECAST_KINDS),
		question: z.string().min(5).max(300),
		scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
		metric: z.string().regex(/^[a-z_]{1,40}$/),
		comparator: z.enum(["gte", "lte"]),
		threshold: z.number().finite(),
		method: z.string().regex(/^[a-z0-9_]{1,60}$/),
		method_version: z.string().max(20),
		// Nunca 0 nem 1: certeza absoluta não existe numa previsão.
		probability: z.number().gt(0).lt(1),
		interval_low: z.number().min(0).max(1),
		interval_high: z.number().min(0).max(1),
		horizon_minutes: z.number().int().min(1).max(60 * 24 * 30),
		created_at: iso,
		resolves_at: iso,
		evidence: z.record(z.string(), z.unknown()),
		status: z.enum(["open", "resolved", "void"]),
		outcome: z.union([z.literal(0), z.literal(1)]).nullable(),
		observed_value: z.number().finite().nullable(),
		resolved_at: iso.nullable(),
		brier: z.number().min(0).max(1).nullable(),
	})
	.refine((f) => f.interval_low <= f.probability && f.probability <= f.interval_high, {
		message: "probability fora do intervalo",
	})
	.refine(
		(f) => {
			if (f.status === "resolved") return f.outcome !== null && f.brier !== null && f.observed_value !== null && f.resolved_at !== null;
			if (f.status === "void") return f.outcome === null && f.brier === null && f.observed_value === null; // anulada: sem resultado
			return f.outcome === null && f.brier === null && f.observed_value === null && f.resolved_at === null; // aberta
		},
		{ message: "status da previsão incoerente com os campos de resolução" },
	);

const batchSchema = z.object({
	batch_id: z.string().min(1).max(80),
	// Catálogo completo cabe em um lote (hoje ~110 fontes); margem para crescer sem derrubar a ingestão.
	sources: z.array(sourceSchema).max(500),
	/** true = `sources` é o catálogo COMPLETO de fontes ativas: as que não vierem são desativadas. */
	catalog_complete: z.boolean().optional().default(false),
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
	forecasts: z.array(forecastSchema).max(200).default([]),
	/** Histórico agregado por HORA (docs/research/SPEC_01_HISTORY.md). Opcional: um Engine antigo não manda. */
	observations: z
		.array(
			z.object({
				scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
				category: z.enum(CATEGORIES),
				source_class: z.enum(SOURCE_CLASSES),
				hour: iso.refine((h) => /T\d{2}:00:00(\.0+)?Z$/.test(h), { message: "hour deve ser o início de uma hora" }),
				signals: z.number().int().min(0).max(100000),
				sources: z.number().int().min(0).max(1000),
				duplicates: z.number().int().min(0).max(100000).default(0),
			}),
		)
		.max(2000)
		.default([]),
	/** Investigações do Sentinela (docs/research/SPEC_05_SENTINEL.md). Opcional: só o que MUDOU nesta rodada. */
	investigations: z
		.array(
			z.object({
				id: z.string().regex(/^inv-[a-f0-9]{10}$/),
				scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
				category: z.enum(CATEGORIES),
				status: z.enum(INVESTIGATION_STATUSES),
				started_at: iso,
				last_update: iso,
				last_anomalous_at: iso.nullable().default(null),
				initial_anomaly: z.number().min(0).max(1000),
				anomaly: z.number().min(0).max(1000),
				evidence_count: z.number().int().min(0).max(1_000_000),
				official_confirmation: z.boolean(),
				reasons: z.array(z.string().max(200)).max(12),
			}),
		)
		.max(200)
		.default([]),
	/** Validação V2 (docs/engineering/ENGINE_V2_PLAN.md). Tudo opcional e aditivo. */
	forecast_registry: z
		.array(
			z.object({
				forecast_id: z.string().regex(/^fc-[a-z0-9-]{1,100}$/),
				created_at: iso,
				snapshot: z.string().min(2).max(8000),
				snapshot_hash: z.string().regex(/^[a-f0-9]{64}$/),
			}),
		)
		.max(200)
		.default([]),
	shadow_results: z
		.array(
			z.object({
				item_id: z.string().min(1).max(120),
				method: z.string().regex(/^[a-z0-9_]{1,60}$/),
				scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
				p_v1: z.number().min(0).max(1),
				p_v2: z.number().min(0).max(1),
				outcome: z.union([z.literal(0), z.literal(1)]),
			}),
		)
		.max(500)
		.default([]),
	driver_registry: z
		.array(
			z.object({
				driver: z.string().regex(/^[A-Z_]{2,20}$/),
				target: z.string().regex(/^[A-Z_]{2,20}$/),
				scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/),
				lag_hours: z.number().int().min(0).max(168),
				correlation: z.number().min(-1).max(1),
				pairs: z.number().int().min(0).max(1_000_000),
				samples: z.number().int().min(0).max(1_000_000),
				brier_without: z.number().min(0).max(1).nullable().default(null),
				brier_with: z.number().min(0).max(1).nullable().default(null),
				state: z.enum(DRIVER_STATES),
				reason: z.string().max(200).default(""),
			}),
		)
		.max(200)
		.default([]),
	/** Artefatos de calibração versionados (docs/engineering/FORECAST_V2_BRIEF.md §30). Raros: no máximo 20 por lote. */
	calibrators: z
		.array(
			z.object({
				id: z.string().regex(/^cal-[a-z0-9_.-]{3,80}$/),
				method: z.string().regex(/^[a-z0-9_]{1,40}$/),
				version: z.string().min(1).max(40),
				fit_start: iso,
				fit_end: iso,
				sample_count: z.number().int().min(0).max(100_000_000),
				artifact: z
					.string()
					.max(20_000)
					.refine(
						(a) => {
							try {
								JSON.parse(a);
								return true;
							} catch {
								return false;
							}
						},
						{ message: "artifact precisa ser JSON válido" },
					),
				status: z.enum(CALIBRATOR_STATUSES).default("candidate"),
				created_at: iso,
			}),
		)
		.max(20)
		.default([]),
	/** Estado por fonte (frescor + breaker): só o que mudou ou o batimento periódico. No máximo 400 por lote. */
	source_runtime: z
		.array(
			z.object({
				source_id: z.string().regex(/^[a-z0-9-]{1,60}$/),
				transport: z.enum(SOURCE_HEALTH),
				freshness_state: z.enum(FRESHNESS_STATES),
				newest_item_age_min: z.number().min(0).max(10_000_000).nullable(),
				last_content_advance: iso.nullable(),
				records: z.number().int().min(0).max(1_000_000),
				new_records: z.number().int().min(0).max(1_000_000),
				duplicate_records: z.number().int().min(0).max(1_000_000),
				breaker_state: z.enum(BREAKER_STATES),
				consecutive_failures: z.number().int().min(0).max(1_000_000),
				next_attempt_at: iso.nullable(),
				opened_count: z.number().int().min(0).max(1_000_000),
				breaker_reason: z.string().max(80).nullable(),
				updated_at: iso,
			}),
		)
		.max(400)
		.default([]),
	/** Resumo do último ciclo do Engine (uma linha 'latest'; JSON limitado, sem segredos). */
	engine_cycle: z
		.object({
			cycle_at: iso,
			duration_s: z.number().min(0).max(100_000),
			sources_due: z.number().int().min(0).max(100_000),
			sources_skipped: z.number().int().min(0).max(100_000),
			records: z.number().int().min(0).max(100_000_000),
			new_records: z.number().int().min(0).max(100_000_000),
			duplicate_records: z.number().int().min(0).max(100_000_000),
			signals_sent: z.number().int().min(0).max(100_000_000),
			events: z.number().int().min(0).max(100_000_000),
			freshness: z.record(z.string().max(20), z.number().int().min(0).max(100_000)),
			coverage: z.record(z.string().max(40), z.unknown()),
			age: z.object({ n: z.number().int().min(0), p50: z.number().nullable(), p95: z.number().nullable(), max: z.number().nullable() }),
			breakers_open: z.number().int().min(0).max(100_000),
			flags: z.record(z.string().max(40), z.boolean()),
			engine_ref: z.string().max(64).nullable(),
		})
		.nullable()
		.default(null),
});

const SERIES_RETENTION_DAYS = 90;
const INVESTIGATION_RETENTION_DAYS = 30;
const VALIDATION_RETENTION_DAYS = 180;

ingest.post("/", async (c) => {
	if (!engineAuthorized(c.req.header("Authorization"), c.env.INGEST_TOKEN)) {
		return c.json({ error: "unauthorized" }, 401);
	}

	const parsed = batchSchema.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) {
		return c.json({ error: "invalid_batch", detail: parsed.error.issues[0]?.message }, 400);
	}
	const db = c.env.DB;
	// Orçamento diário de escrita do D1 (lib/budget.ts): conforme o consumo do dia, descarta o que é de baixa prioridade
	// ANTES de gravar, em vez de deixar a cota estourar e derrubar tudo com erro 500. Se a tabela ainda não existe, segue normal.
	const day = utcDay();
	let budgetTable = true; // a tabela pode não existir (D1 sem a migration 0005): então não há reserva nem contagem, e o ingest segue
	const used = await db
		.prepare("SELECT rows FROM write_budget WHERE day = ?1")
		.bind(day)
		.first<{ rows: number }>()
		.then((r) => r?.rows ?? 0)
		.catch(() => {
			budgetTable = false;
			return 0;
		});
	const mode = budgetMode(used);
	const { batch: plan, shed } = shedBatch(parsed.data, mode);
	const { sources, catalog_complete, events, signals, pulses, source_health, series, forecasts, observations, investigations } = plan;
	const { forecast_registry, shadow_results, driver_registry, calibrators, source_runtime, engine_cycle } = plan;

	// O D1 limita as consultas por invocação (50 no plano gratuito): uma instrução por tabela,
	// lendo o array JSON com json_each. Ordem respeita as chaves estrangeiras.
	// Idempotente: reenviar o mesmo lote não duplica nada (upsert por chave).
	const stmts: D1PreparedStatement[] = [];
	// Observabilidade (estado por fonte, resumo do ciclo): lote À PARTE e best-effort. Se a tabela ainda não existe (migration atrasada)
	// ou o banco falha aqui, o dado de verdade (eventos, sinais, Pulso) já foi gravado e NUNCA se perde por causa disto.
	const obsStmts: D1PreparedStatement[] = [];
	const json = (v: unknown) => JSON.stringify(v);
	const f = (path: string) => `json_extract(j.value,'$.${path}')`;

	if (sources.length) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO sources (id,name,domain,adapter,source_class,url,state)
			 SELECT ${f("id")},${f("name")},${f("domain")},${f("adapter")},${f("source_class")},${f("url")},${f("state")}
			 FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET name=excluded.name,domain=excluded.domain,adapter=excluded.adapter,source_class=excluded.source_class,url=excluded.url,state=excluded.state,enabled=1
				 -- só regrava se algo mudou: linha idêntica não custa escrita no D1
				 WHERE sources.name IS NOT excluded.name OR sources.domain IS NOT excluded.domain OR sources.adapter IS NOT excluded.adapter OR sources.source_class IS NOT excluded.source_class OR sources.url IS NOT excluded.url OR sources.state IS NOT excluded.state OR sources.enabled != 1`,
				)
				.bind(json(sources)),
		);
		if (catalog_complete) {
			// Fonte desligada ou removida do config/sources.json some do /api/health (e do painel do front).
			stmts.push(
				db
					.prepare(`UPDATE sources SET enabled = 0 WHERE id NOT IN (SELECT ${f("id")} FROM json_each(?1) j)`)
					.bind(json(sources)),
			);
		}
	}
	if (events.length) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO events (id,title,summary,category,status,latitude,longitude,geo_precision,geo_confidence,state,city,severity,confidence,pulse,alert_level,score_breakdown,signal_count,source_count,detected_at,updated_at,peak_alert_level,peak_pulse,peak_at)
			 SELECT ${f("event_id")},${f("title")},${f("summary")},${f("category")},${f("status")},${f("latitude")},${f("longitude")},${f("geo_precision")},${f("geo_confidence")},${f("state")},${f("city")},${f("severity")},${f("confidence")},${f("pulse")},${f("alert_level")},${f("score_breakdown")},${f("signal_count")},${f("source_count")},${f("detected_at")},${f("updated_at")},${f("alert_level")},${f("pulse")},${f("updated_at")}
			 FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET title=excluded.title,summary=excluded.summary,category=excluded.category,status=excluded.status,
			   latitude=excluded.latitude,longitude=excluded.longitude,geo_precision=excluded.geo_precision,geo_confidence=excluded.geo_confidence,
			   state=excluded.state,city=excluded.city,severity=excluded.severity,confidence=excluded.confidence,pulse=excluded.pulse,
			   alert_level=excluded.alert_level,score_breakdown=excluded.score_breakdown,signal_count=excluded.signal_count,
			   source_count=excluded.source_count,updated_at=excluded.updated_at,
			   -- pico: o máximo já atingido e quando (as expressões leem os valores ANTIGOS da linha)
			   peak_at=CASE WHEN excluded.peak_pulse > events.peak_pulse THEN excluded.peak_at ELSE events.peak_at END,
			   peak_alert_level=MAX(events.peak_alert_level,excluded.peak_alert_level),
			   peak_pulse=MAX(events.peak_pulse,excluded.peak_pulse)
			 -- reenvio idêntico não grava (idempotência e orçamento): só se algum campo mudou
			 WHERE events.updated_at IS NOT excluded.updated_at OR events.title IS NOT excluded.title OR events.summary IS NOT excluded.summary
			   OR events.category IS NOT excluded.category OR events.status IS NOT excluded.status OR events.latitude IS NOT excluded.latitude
			   OR events.longitude IS NOT excluded.longitude OR events.geo_precision IS NOT excluded.geo_precision OR events.geo_confidence IS NOT excluded.geo_confidence
			   OR events.state IS NOT excluded.state OR events.city IS NOT excluded.city OR events.severity IS NOT excluded.severity
			   OR events.confidence IS NOT excluded.confidence OR events.pulse IS NOT excluded.pulse OR events.alert_level IS NOT excluded.alert_level
			   OR events.score_breakdown IS NOT excluded.score_breakdown OR events.signal_count IS NOT excluded.signal_count
			   OR events.source_count IS NOT excluded.source_count OR excluded.peak_pulse > events.peak_pulse OR excluded.peak_alert_level > events.peak_alert_level`,
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
			 ON CONFLICT(hash) DO UPDATE SET event_id=excluded.event_id,category=excluded.category,state=excluded.state,city=excluded.city
				 WHERE signals.event_id IS NOT excluded.event_id OR signals.category IS NOT excluded.category OR signals.state IS NOT excluded.state OR signals.city IS NOT excluded.city`,
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
			 ON CONFLICT(event_id,source_id) DO UPDATE SET signal_count=excluded.signal_count,first_seen=excluded.first_seen
				 WHERE event_sources.signal_count != excluded.signal_count OR event_sources.first_seen != excluded.first_seen`,
				)
				.bind(json(signals.map((g) => ({ event_id: g.event_id })))),
		);
	}
	if (pulses.length) {
		stmts.push(
			db
				.prepare(
					`INSERT INTO pulse_history (scope,timestamp,score,alert_level,contributors)
			 SELECT ${f("scope")},${f("timestamp")},${f("score")},${f("alert_level")},${f("contributors")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(scope,timestamp) DO UPDATE SET score=excluded.score,alert_level=excluded.alert_level,contributors=excluded.contributors
			 WHERE pulse_history.score IS NOT excluded.score OR pulse_history.alert_level IS NOT excluded.alert_level OR pulse_history.contributors IS NOT excluded.contributors`,
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
			 ON CONFLICT(scope,category,bucket) DO UPDATE SET signals=MAX(signals,excluded.signals),sources=MAX(sources,excluded.sources)
			 WHERE excluded.signals > series.signals OR excluded.sources > series.sources`,
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
	if (observations.length) {
		// Só sobe: uma hora fechada pode receber um sinal tardio, mas a contagem nunca diminui (o feed descarta itens
		// antigos) e reenvio idêntico não grava nada (o WHERE evita a escrita).
		stmts.push(
			db
				.prepare(
					`INSERT INTO signal_observations (scope,category,source_class,hour,signals,sources,duplicates)
			 SELECT ${f("scope")},${f("category")},${f("source_class")},${f("hour")},${f("signals")},${f("sources")},${f("duplicates")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(scope,category,source_class,hour) DO UPDATE SET
			   signals=MAX(signal_observations.signals,excluded.signals),
			   sources=MAX(signal_observations.sources,excluded.sources),
			   duplicates=MAX(signal_observations.duplicates,excluded.duplicates)
			 WHERE excluded.signals > signal_observations.signals OR excluded.sources > signal_observations.sources OR excluded.duplicates > signal_observations.duplicates`,
				)
				.bind(json(observations)),
		);
		// Retenção de 90 dias UMA vez por dia (03:00 UTC): a tabela não tem índice por hora, então a limpeza varre a tabela.
		const now = new Date();
		if (now.getUTCHours() === 3 && now.getUTCMinutes() < 10) {
			stmts.push(
				db
					.prepare("DELETE FROM signal_observations WHERE hour < ?1")
					.bind(new Date(Date.now() - SERIES_RETENTION_DAYS * 86400_000).toISOString()),
			);
		}
	}
	if (investigations.length) {
		// Abre uma vez; depois só avança o estado (started_at e initial_anomaly nunca mudam) e só regrava se algo mudou.
		stmts.push(
			db
				.prepare(
					`INSERT INTO investigations (id,scope,category,status,started_at,last_update,last_anomalous_at,initial_anomaly,anomaly,evidence_count,official_confirmation,reasons)
			 SELECT ${f("id")},${f("scope")},${f("category")},${f("status")},${f("started_at")},${f("last_update")},${f("last_anomalous_at")},${f("initial_anomaly")},${f("anomaly")},${f("evidence_count")},${f("official_confirmation")},${f("reasons")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET status=excluded.status,last_update=excluded.last_update,last_anomalous_at=excluded.last_anomalous_at,
			   anomaly=excluded.anomaly,evidence_count=excluded.evidence_count,official_confirmation=excluded.official_confirmation,reasons=excluded.reasons
			 WHERE investigations.status IS NOT excluded.status OR investigations.evidence_count IS NOT excluded.evidence_count
			    OR investigations.anomaly IS NOT excluded.anomaly OR investigations.official_confirmation IS NOT excluded.official_confirmation
			    OR investigations.last_anomalous_at IS NOT excluded.last_anomalous_at`,
				)
				.bind(json(investigations.map((i) => ({ ...i, official_confirmation: i.official_confirmation ? 1 : 0, reasons: JSON.stringify(i.reasons) })))),
		);
	}
	if (forecast_registry.length) {
		// IMUTÁVEL: a trilha de auditoria de uma previsão nunca é reescrita (DO NOTHING); reenvio não grava nada.
		stmts.push(
			db
				.prepare(
					`INSERT INTO forecast_registry (forecast_id,created_at,snapshot,snapshot_hash)
			 SELECT ${f("forecast_id")},${f("created_at")},${f("snapshot")},${f("snapshot_hash")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(forecast_id) DO NOTHING`,
				)
				.bind(json(forecast_registry)),
		);
	}
	if (shadow_results.length) {
		// Só linhas já resolvidas e imutáveis por (item, método).
		stmts.push(
			db
				.prepare(
					`INSERT INTO shadow_results (item_id,method,scope,p_v1,p_v2,outcome,created_at)
			 SELECT ${f("item_id")},${f("method")},${f("scope")},${f("p_v1")},${f("p_v2")},${f("outcome")},?2 FROM json_each(?1) j WHERE true
			 ON CONFLICT(item_id,method) DO NOTHING`,
				)
				.bind(json(shadow_results), new Date().toISOString()),
		);
	}
	if (driver_registry.length) {
		// DISABLED é manual: o ingest nunca reativa um driver desligado. Só regrava se algo mudou.
		stmts.push(
			db
				.prepare(
					`INSERT INTO driver_registry (driver,target,scope,lag_hours,correlation,pairs,samples,brier_without,brier_with,state,reason,updated_at)
			 SELECT ${f("driver")},${f("target")},${f("scope")},${f("lag_hours")},${f("correlation")},${f("pairs")},${f("samples")},${f("brier_without")},${f("brier_with")},${f("state")},${f("reason")},?2 FROM json_each(?1) j WHERE true
			 ON CONFLICT(driver,target,scope,lag_hours) DO UPDATE SET correlation=excluded.correlation,pairs=excluded.pairs,samples=excluded.samples,
			   brier_without=excluded.brier_without,brier_with=excluded.brier_with,state=excluded.state,reason=excluded.reason,updated_at=excluded.updated_at
			 WHERE driver_registry.state != 'DISABLED'
			   AND (driver_registry.state IS NOT excluded.state OR driver_registry.samples IS NOT excluded.samples
			        OR driver_registry.brier_with IS NOT excluded.brier_with OR driver_registry.brier_without IS NOT excluded.brier_without
			        OR driver_registry.pairs IS NOT excluded.pairs OR driver_registry.correlation IS NOT excluded.correlation)`,
				)
				.bind(json(driver_registry), new Date().toISOString()),
		);
	}
	if (calibrators.length) {
		// O ARTEFATO é imutável (uma linha por versão); só o status evolui, e `retired` é terminal (uma versão aposentada nunca volta).
		stmts.push(
			db
				.prepare(
					`INSERT INTO calibrators (id,method,version,fit_start,fit_end,sample_count,artifact,status,created_at)
			 SELECT ${f("id")},${f("method")},${f("version")},${f("fit_start")},${f("fit_end")},${f("sample_count")},${f("artifact")},${f("status")},${f("created_at")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET status=excluded.status
			 WHERE calibrators.status != 'retired' AND calibrators.status IS NOT excluded.status`,
				)
				.bind(json(calibrators)),
		);
	}
	if (source_runtime.length) {
		// Só avança no tempo: um reenvio idêntico ou atrasado (mesmo updated_at ou mais velho) não grava nada.
		obsStmts.push(
			db
				.prepare(
					`INSERT INTO source_runtime (source_id,transport,freshness_state,newest_item_age_min,last_content_advance,records,new_records,duplicate_records,breaker_state,consecutive_failures,next_attempt_at,opened_count,breaker_reason,updated_at)
			 SELECT ${f("source_id")},${f("transport")},${f("freshness_state")},${f("newest_item_age_min")},${f("last_content_advance")},${f("records")},${f("new_records")},${f("duplicate_records")},${f("breaker_state")},${f("consecutive_failures")},${f("next_attempt_at")},${f("opened_count")},${f("breaker_reason")},${f("updated_at")} FROM json_each(?1) j WHERE true
			 ON CONFLICT(source_id) DO UPDATE SET transport=excluded.transport,freshness_state=excluded.freshness_state,newest_item_age_min=excluded.newest_item_age_min,
			   last_content_advance=excluded.last_content_advance,records=excluded.records,new_records=excluded.new_records,duplicate_records=excluded.duplicate_records,
			   breaker_state=excluded.breaker_state,consecutive_failures=excluded.consecutive_failures,next_attempt_at=excluded.next_attempt_at,
			   opened_count=excluded.opened_count,breaker_reason=excluded.breaker_reason,updated_at=excluded.updated_at
			 WHERE excluded.updated_at > source_runtime.updated_at`,
				)
				.bind(json(source_runtime)),
		);
	}
	if (engine_cycle) {
		obsStmts.push(
			db
				.prepare(
					`INSERT INTO engine_cycle (id,cycle_at,duration_s,summary) VALUES ('latest',?1,?2,?3)
			 ON CONFLICT(id) DO UPDATE SET cycle_at=excluded.cycle_at,duration_s=excluded.duration_s,summary=excluded.summary
			 WHERE excluded.cycle_at > engine_cycle.cycle_at`,
				)
				.bind(engine_cycle.cycle_at, engine_cycle.duration_s, json(engine_cycle)),
		);
	}
	// Investigação encerrada há mais de 30 dias sai (uma vez por dia, 03:10-03:20 UTC; o índice (status, last_update) cobre a busca).
	{
		const at = new Date();
		if (at.getUTCHours() === 3 && at.getUTCMinutes() >= 10 && at.getUTCMinutes() < 20) {
			stmts.push(
				db
					.prepare("DELETE FROM investigations WHERE status = 'CLOSED' AND last_update < ?1")
					.bind(new Date(Date.now() - INVESTIGATION_RETENTION_DAYS * 86400_000).toISOString()),
			);
			// auditoria e comparação V2: 180 dias (a janela de 03:10-03:20 UTC roda uma vez por dia)
			const cutoff = new Date(Date.now() - VALIDATION_RETENTION_DAYS * 86400_000).toISOString();
			stmts.push(db.prepare("DELETE FROM forecast_registry WHERE created_at < ?1").bind(cutoff));
			stmts.push(db.prepare("DELETE FROM shadow_results WHERE created_at < ?1").bind(cutoff));
		}
	}
	if (forecasts.length) {
		// IMUTABILIDADE: a previsão (probabilidade, pergunta, método, evidência) é gravada uma vez e nunca
		// reescrita; o reenvio só pode preencher a resolução, e apenas enquanto ainda estiver aberta.
		stmts.push(
			db
				.prepare(
					`INSERT INTO forecasts (id,kind,question,scope,metric,comparator,threshold,method,method_version,probability,interval_low,interval_high,horizon_minutes,created_at,resolves_at,evidence,status,outcome,observed_value,resolved_at,brier)
			 SELECT ${f("forecast_id")},${f("kind")},${f("question")},${f("scope")},${f("metric")},${f("comparator")},${f("threshold")},${f("method")},${f("method_version")},${f("probability")},${f("interval_low")},${f("interval_high")},${f("horizon_minutes")},${f("created_at")},${f("resolves_at")},${f("evidence")},${f("status")},${f("outcome")},${f("observed_value")},${f("resolved_at")},${f("brier")}
			 FROM json_each(?1) j WHERE true
			 ON CONFLICT(id) DO UPDATE SET status=excluded.status,outcome=excluded.outcome,observed_value=excluded.observed_value,resolved_at=excluded.resolved_at,brier=excluded.brier
			 WHERE forecasts.status = 'open' AND excluded.status != 'open'`, // aberta reenviada igual não grava; só a resolução/anulação grava
				)
				.bind(json(forecasts)),
		);
	}
	// CONTAGEM DO ORÇAMENTO sem subcontar (RT-005/A1b). Antes: contava DEPOIS do lote, em separado; se a resposta se perdia depois do
	// commit, o dado estava salvo e o orçamento não. Agora: uma RESERVA (estimativa por cima) entra na MESMA transação do lote; se a
	// resposta se perder, a reserva já está lá (erra para MAIS, a direção segura para um governador). No caminho normal a reserva é
	// trocada pelo valor real logo depois, então fica exata. O orçamento continua sendo uma cortesia do governador, não a garantia
	// forte: quem barra de verdade é o limite do próprio banco.
	const estimate =
		RESERVE_ROWS_PER_ITEM *
			(sources.length + events.length + 2 * signals.length + pulses.length + source_health.length + series.length + forecasts.length +
				observations.length + investigations.length + forecast_registry.length + shadow_results.length + driver_registry.length +
				calibrators.length + source_runtime.length + (engine_cycle ? 1 : 0)) +
		RESERVE_FIXED;
	const reserve = budgetTable && (stmts.length > 0 || obsStmts.length > 0);
	let written = 0;
	if (stmts.length) {
		if (reserve) {
			stmts.unshift(
				db
					.prepare("INSERT INTO write_budget (day,rows) VALUES (?1,?2) ON CONFLICT(day) DO UPDATE SET rows = rows + excluded.rows")
					.bind(day, estimate),
			);
		}
		const results = await db.batch(stmts);
		written = results.slice(reserve ? 1 : 0).reduce((a, r) => a + (r.meta?.rows_written ?? 0), 0);
	} else if (reserve) {
		// só observabilidade neste lote: a reserva vai sozinha (best-effort, não derruba nada)
		await db
			.prepare("INSERT INTO write_budget (day,rows) VALUES (?1,?2) ON CONFLICT(day) DO UPDATE SET rows = rows + excluded.rows")
			.bind(day, estimate)
			.run()
			.catch(() => {
				budgetTable = false;
			});
	}
	let observability: "ok" | "skipped" | "failed" = obsStmts.length ? "ok" : "skipped";
	if (obsStmts.length) {
		try {
			const results = await db.batch(obsStmts);
			written += results.reduce((a, r) => a + (r.meta?.rows_written ?? 0), 0);
		} catch (e) {
			observability = "failed";
			console.error("observability_write_failed", c.get("requestId"), e instanceof Error ? e.message.slice(0, 200) : "erro");
		}
	}
	// Troca a reserva pelo consumo REAL do dia. Falhar aqui nunca derruba a ingestão e só deixa o contador a MAIS (reserva mantida).
	if (reserve && budgetTable) {
		await db
			.prepare("UPDATE write_budget SET rows = MAX(0, rows - ?2 + ?3) WHERE day = ?1")
			.bind(day, estimate, written)
			.run()
			.catch(() => undefined);
	}
	return c.json({
		ok: true,
		sources: sources.length,
		signals: signals.length,
		events: events.length,
		pulses: pulses.length,
		source_health: source_health.length,
		series: series.length,
		forecasts: forecasts.length,
		observations: observations.length,
		investigations: investigations.length,
		forecast_registry: forecast_registry.length,
		shadow_results: shadow_results.length,
		driver_registry: driver_registry.length,
		calibrators: calibrators.length,
		source_runtime: source_runtime.length,
		engine_cycle: engine_cycle ? 1 : 0,
		observability,
		budget: { mode, used_before: used, written, shed },
	});
});
