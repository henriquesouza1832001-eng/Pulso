import type { CameraFeed, Forecast, PulsoEvent, PulseSnapshot, SourceHealth } from "@pulso/shared";

/** Em produção defina VITE_API_BASE (URL pública do Worker). Nunca coloque segredos aqui. */
const BASE: string =
	import.meta.env.VITE_API_BASE ??
	(import.meta.env.PROD ? "https://pulso-api.henriquesouza.workers.dev" : "");

async function get<T>(path: string): Promise<T> {
	const res = await fetch(`${BASE}${path}`);
	if (!res.ok) throw new Error(`${path} → ${res.status}`);
	return res.json() as Promise<T>;
}

/** Sinais que sustentam um evento (transparência editorial). */
export interface SignalRow {
	signal_id: string;
	source_id: string;
	source_name: string;
	source_class: string;
	timestamp: string;
	collected_at: string;
	title: string;
	url: string | null;
	category: string;
}

export interface EventDetail {
	event: PulsoEvent;
	signals: SignalRow[];
}

export interface HealthSnapshot {
	api: string;
	db: string;
	sources: SourceHealth[];
}

/** Contadores do indicador nacional (GET /api/stats), janelas calculadas no servidor. */
export interface StatsSnapshot {
	active_events: number;
	states_active: number;
	sources_online: number;
	sources_total: number;
	alerts: number | null;
	signals_2h: number | null;
	last_pulse_at: string | null;
	generated_at: string;
}
export interface StatsSnapshot {
	active_events: number;
	states_active: number;
	alerts: number;
	signals_2h: number;
	signals_24h: number;
	sources_online: number;
	sources_total: number;
	last_pulse_at: string | null;
export interface PulseHistoryPoint {
	timestamp: string;
	score: number;
	alert_level: number;
}

export interface PulsePoint {
	timestamp: string;
	score: number;
	alert_level: number;
}

export interface TrackRecord {
	methods: { method: string; n_resolved: number; mean_brier: number | null; experimental: boolean }[];
}
	timestamp: string;
	score: number;
	alert_level: number;
}

export const api = {
	pulseBR: () => get<PulseSnapshot>("/api/pulse/br"),
	pulseHistoryBR: () => get<{ points: PulsePoint[] }> ("/api/pulse/history?scope=BR&hours=6"),
	pulseHistory: () => get<{ scope: string; hours: number; points: PulseHistoryPoint[] }> ("/api/pulse/history?scope=BR&hours=24"),
	events: (limit = 50) => get<{ events: PulsoEvent[] }>(`/api/events?limit=${limit}`),
	event: (id: string) => get<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
	health: () => get<HealthSnapshot>("/api/health"),
	stats: () => get<StatsSnapshot>("/api/stats"),
	cameras: () => get<{ cameras: CameraFeed[] }>("/api/cameras"),
	forecasts: () => get<{ notice: string; forecasts: Forecast[] }>("/api/forecasts?status=open&limit=10"),
	trackRecord: () => get<TrackRecord>("/api/forecasts/track-record"),
	history: () => get<{ min_level: number; days: number; entries: HistoryEntry[] }>("/api/history?days=30&limit=50"),
	events100: () => get<{ events: PulsoEvent[] }>("/api/events?limit=100"),
};
export const api = {
	pulseBR: () => get<PulseSnapshot>("/api/pulse/br"),
	events: (limit = 50) => get<{ events: PulsoEvent[] }>(`/api/events?limit=${limit}`),
	event: (id: string) => get<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
	health: () => get<HealthSnapshot>("/api/health"),
	stats: () => get<StatsSnapshot>("/api/stats"),
	forecasts: () => get<{ notice: string; forecasts: Forecast[] }>("/api/forecasts?status=open&limit=10"),
	history: () => get<{ min_level: number; days: number; entries: HistoryEntry[] }>("/api/history?days=30&limit=50"),
	pulseHistory: () => get<{ scope: string; hours: number; points: PulseHistoryPoint[] }>("/api/pulse/history?scope=BR&hours=24"),
	cameras: () => get<{ cameras: CameraFeed[] }>("/api/cameras"),
	pulseHistoryBR: () => get<{ points: PulsePoint[] }>("/api/pulse/history?scope=BR&hours=6"),
	trackRecord: () => get<TrackRecord>("/api/forecasts/track-record"),
	events100: () => get<{ events: PulsoEvent[] }>("/api/events?limit=100"),
	event: (id: string) => get<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
	health: () => get<HealthSnapshot>("/api/health"),
};
