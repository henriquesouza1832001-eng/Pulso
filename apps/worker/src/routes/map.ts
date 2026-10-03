import { Hono } from "hono";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";

export const map = new Hono<AppEnv>();

interface MapRow {
	id: string;
	title: string;
	category: string;
	status: string;
	latitude: number;
	longitude: number;
	severity: number;
	confidence: number;
	pulse: number;
	alert_level: number;
	updated_at: string;
}

/** GeoJSON FeatureCollection de eventos com coordenadas: alimenta o MapLibre. */
map.get("/", async (c) => {
	const { results } = await c.env.DB.prepare(
		`SELECT id, title, category, status, latitude, longitude, severity, confidence, pulse, alert_level, updated_at
		 FROM events WHERE resolved_at IS NULL AND updated_at >= ?1 AND latitude IS NOT NULL AND longitude IS NOT NULL
		 ORDER BY pulse DESC LIMIT 1000`,
	)
		.bind(new Date(Date.now() - 24 * 3600_000).toISOString())
		.all<MapRow>();
	c.header("Cache-Control", cacheControl(10));
	return c.json({
		type: "FeatureCollection",
		features: results.map((r) => ({
			type: "Feature",
			geometry: { type: "Point", coordinates: [r.longitude, r.latitude] },
			properties: {
				event_id: r.id,
				title: r.title,
				category: r.category,
				status: r.status,
				severity: r.severity,
				confidence: r.confidence,
				pulse: r.pulse,
				alert_level: r.alert_level,
				updated_at: r.updated_at,
			},
		})),
	});
});
