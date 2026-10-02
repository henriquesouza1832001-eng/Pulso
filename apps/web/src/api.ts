import type { PulsoEvent, PulseSnapshot } from "@pulso/shared";

/** Em produção defina VITE_API_BASE (URL pública do Worker). Nunca coloque segredos aqui. */
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function get<T>(path: string): Promise<T> {
	const res = await fetch(`${BASE}${path}`);
	if (!res.ok) throw new Error(`${path} → ${res.status}`);
	return res.json() as Promise<T>;
}

export const api = {
	pulseBR: () => get<PulseSnapshot>("/api/pulse/br"),
	events: () => get<{ events: PulsoEvent[] }>("/api/events?limit=20"),
};
