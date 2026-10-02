import type { PulsoEvent } from "@pulso/shared";

export interface EventRow {
	id: string;
	title: string;
	summary: string | null;
	category: string;
	status: string;
	latitude: number | null;
	longitude: number | null;
	geo_precision: string | null;
	geo_confidence: number | null;
	state: string | null;
	city: string | null;
	severity: number;
	confidence: number;
	pulse: number;
	alert_level: number;
	score_breakdown: string;
	signal_count: number;
	source_count: number;
	detected_at: string;
	updated_at: string;
}

export const EVENT_COLUMNS =
	"id,title,summary,category,status,latitude,longitude,geo_precision,geo_confidence,state,city,severity,confidence,pulse,alert_level,score_breakdown,signal_count,source_count,detected_at,updated_at";

export function toEvent(r: EventRow): PulsoEvent {
	let breakdown: PulsoEvent["score_breakdown"] = [];
	try {
		breakdown = JSON.parse(r.score_breakdown);
	} catch {
		// breakdown corrompido não derruba a API
	}
	const { id, score_breakdown: _b, ...rest } = r;
	return { event_id: id, ...rest, score_breakdown: breakdown } as PulsoEvent;
}
