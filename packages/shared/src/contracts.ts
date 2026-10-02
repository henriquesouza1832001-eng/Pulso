/**
 * CONTRATOS DO PULSO — fonte única da verdade entre Engine (Python), Worker e Web.
 * Os espelhos em Python vivem em engine/pulso_engine/models.py.
 * Mudança aqui é mudança de contrato: abra PR com label `contract` e atualize docs/api/API.md.
 */

export const CATEGORIES = [
	"SECURITY", "TRAFFIC", "WEATHER", "INFRASTRUCTURE", "PROTEST", "POLITICS",
	"ECONOMY", "HEALTH", "INTERNATIONAL", "TECH", "EVENT", "EMERGENCY", "OTHER",
] as const;
export type Category = (typeof CATEGORIES)[number];

/** Confiabilidade da FONTE (apenas um componente da confiança do evento). */
export const SOURCE_CLASSES = [
	"OFFICIAL", "NEWS_HIGH", "NEWS_REGIONAL", "TRAFFIC_PROVIDER",
	"SOCIAL_VERIFIED", "SOCIAL", "UNKNOWN",
] as const;
export type SourceClass = (typeof SOURCE_CLASSES)[number];

export const EVENT_STATUSES = [
	"DETECTED", "DEVELOPING", "CONFIRMED", "STABLE", "RESOLVING", "RESOLVED", "DISPUTED",
] as const;
export type EventStatus = (typeof EVENT_STATUSES)[number];

export const GEO_PRECISIONS = [
	"COUNTRY", "STATE", "CITY", "NEIGHBORHOOD", "STREET", "POINT",
] as const;
export type GeoPrecision = (typeof GEO_PRECISIONS)[number];

export const SOURCE_HEALTH = [
	"ONLINE", "DEGRADED", "RATE_LIMITED", "OFFLINE", "AUTH_ERROR", "UNKNOWN",
] as const;
export type SourceHealthStatus = (typeof SOURCE_HEALTH)[number];

/** PULSO 1–5. O nível 5 exige fonte oficial + múltiplas fontes independentes. */
export type AlertLevel = 1 | 2 | 3 | 4 | 5;

/** Um item do score explicável ("POR QUE 87?"). `points` somados = `pulso`. */
export interface ScoreContribution {
	key: string;
	label: string;
	points: number;
}

/** Sinal bruto normalizado: o "asteroide". */
export interface Signal {
	signal_id: string;
	source_id: string;
	source_class: SourceClass;
	timestamp: string; // ISO-8601 UTC
	collected_at: string;
	title: string;
	text: string | null;
	url: string | null;
	category: Category;
	latitude: number | null;
	longitude: number | null;
	geo_precision: GeoPrecision | null;
	geo_confidence: number | null; // 0–100
	reliability: number; // 0–100, só da fonte
	event_id: string | null;
	hash: string; // deduplicação (canonical_url ou título normalizado)
	canonical_url: string | null;
	author: string | null;
	state: string | null; // UF
	city: string | null;
}

/** Cadastro de uma fonte (espelha a tabela sources). */
export interface SourceDef {
	id: string;
	name: string;
	domain: string | null;
	adapter: string; // rss | api | feed | sitemap | social
	source_class: SourceClass;
	url: string;
	state: string | null;
}

/** Evento normalizado (cluster de sinais). Severidade e confiança são independentes. */
export interface PulsoEvent {
	event_id: string;
	title: string;
	summary: string | null;
	category: Category;
	status: EventStatus;
	latitude: number | null;
	longitude: number | null;
	geo_precision: GeoPrecision | null;
	geo_confidence: number | null;
	state: string | null; // UF
	city: string | null;
	severity: number; // 0–100
	confidence: number; // 0–100
	pulse: number; // 0–100
	alert_level: AlertLevel;
	score_breakdown: ScoreContribution[];
	signal_count: number;
	source_count: number;
	detected_at: string;
	updated_at: string;
}

export interface PulseSnapshot {
	scope: string; // "BR" | "UF:MG" | "CITY:belo-horizonte"
	timestamp: string;
	score: number;
	alert_level: AlertLevel;
	label: string;
	/** Maiores responsáveis pela variação (ex.: "DF" +18). */
	contributors: { scope: string; delta: number }[];
	delta_2h: number | null;
}

export interface SourceHealth {
	source_id: string;
	name: string;
	status: SourceHealthStatus;
	last_success: string | null;
	detail: string | null;
}

/** Payload que o Python Engine envia ao Worker (POST /api/ingest). Idempotente por event_id/scope+timestamp. */
export interface IngestBatch {
	batch_id: string;
	sources: SourceDef[];
	events: PulsoEvent[];
	signals: Signal[];
	pulses: PulseSnapshot[];
	source_health: SourceHealth[];
}

export interface ApiError {
	error: string;
	detail?: string;
}
