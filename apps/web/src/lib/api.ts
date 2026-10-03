import type { Forecast, PulsoEvent, PulseSnapshot, SourceHealth } from "@pulso/shared";

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

export interface StatsSnapshot {
	active_events: number;
	states_active: number;
	alerts: number;
	signals_2h: number;
	signals_24h: number;
	sources_online: number;
	sources_total: number;
	last_pulse_at: string | null;
	generated_at: string;
}

export interface HistoryEntry {
	kind: "event" | "national";
	event_id?: string;
	date: string;
	level: 2 | 3 | 4 | 5;
	peak_pulse: number;
	title: string;
	category?: string;
	state?: string | null;
	city?: string | null;
	confidence?: number;
	signal_count?: number;
	source_count?: number;
	started_at?: string;
	ended_at?: string;
	duration_minutes?: number;
}

export interface PulseHistoryPoint {
	timestamp: string;
	score: number;
	alert_level: number;
}

export const api = {
	pulseBR: () => get<PulseSnapshot>("/api/pulse/br"),
	events: (limit = 50) => get<{ events: PulsoEvent[] }>(`/api/events?limit=${limit}`),
	event: (id: string) => get<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
	health: () => get<HealthSnapshot>("/api/health"),
	stats: () => get<StatsSnapshot>("/api/stats"),
	forecasts: () => get<{ notice: string; forecasts: Forecast[] }>("/api/forecasts?status=open&limit=10"),
	history: () => get<{ min_level: number; days: number; entries: HistoryEntry[] }>("/api/history?days=30&limit=50"),
	pulseHistory: () => get<{ scope: string; hours: number; points: PulseHistoryPoint[] }>("/api/pulse/history?scope=BR&hours=24"),
};
