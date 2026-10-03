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
	alerts: number;
	signals_2h: number;
	signals_24h: number;
	sources_online: number;
	sources_total: number;
	last_pulse_at: string | null;
}

export interface PulsePoint {
	timestamp: string;
	score: number;
	alert_level: number;
}

export interface TrackRecord {
	methods: { method: string; n_resolved: number; mean_brier: number | null; experimental: boolean }[];
}

export const api = {
	pulseBR: () => get<PulseSnapshot>("/api/pulse/br"),
	events: (limit = 50) => get<{ events: PulsoEvent[] }>(`/api/events?limit=${limit}`),
	event: (id: string) => get<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
	health: () => get<HealthSnapshot>("/api/health"),
	cameras: () => get<{ cameras: CameraFeed[] }>("/api/cameras"),
	stats: () => get<StatsSnapshot>("/api/stats"),
	pulseHistoryBR: () => get<{ points: PulsePoint[] }>("/api/pulse/history?scope=BR&hours=6"),
	forecasts: () => get<{ notice: string; forecasts: Forecast[] }>("/api/forecasts?limit=30"),
	trackRecord: () => get<TrackRecord>("/api/forecasts/track-record"),
	/** Até 100 eventos (limite da API): mais base para os agregados do painel. */
	events100: () => get<{ events: PulsoEvent[] }>("/api/events?limit=100"),
};
