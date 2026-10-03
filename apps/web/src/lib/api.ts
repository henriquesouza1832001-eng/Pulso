import type { CameraFeed, PulsoEvent, PulseSnapshot, SourceHealth } from "@pulso/shared";

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

export const api = {
	pulseBR: () => get<PulseSnapshot>("/api/pulse/br"),
	events: (limit = 50) => get<{ events: PulsoEvent[] }>(`/api/events?limit=${limit}`),
	event: (id: string) => get<EventDetail>(`/api/events/${encodeURIComponent(id)}`),
	health: () => get<HealthSnapshot>("/api/health"),
	cameras: () => get<{ cameras: CameraFeed[] }>("/api/cameras"),
};
