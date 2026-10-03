import { Hono } from "hono";
import { z } from "zod";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";

/** Histórico de inteligência: momentos de nível alto, de eventos e do Pulso nacional. */
export const history = new Hono<AppEnv>();

const query = z.object({
	min_level: z.coerce.number().int().min(2).max(5).default(3),
	days: z.coerce.number().int().min(1).max(90).default(30),
	limit: z.coerce.number().int().min(1).max(50).default(20),
});

interface Point {
	timestamp: string;
	score: number;
	alert_level: number;
}

const GAP_MS = 30 * 60_000; // pontos separados por mais de 30 min pertencem a episódios diferentes

/** Agrupa pontos consecutivos de nível alto em episódios (início, fim, pico). */
export function toEpisodes(points: Point[]) {
	const episodes: { start: string; end: string; peak_score: number; peak_level: number; peak_at: string }[] = [];
	for (const p of points) {
		const last = episodes[episodes.length - 1];
		if (last && Date.parse(p.timestamp) - Date.parse(last.end) <= GAP_MS) {
			last.end = p.timestamp;
			if (p.score > last.peak_score) {
				last.peak_score = p.score;
				last.peak_at = p.timestamp;
			}
			last.peak_level = Math.max(last.peak_level, p.alert_level);
		} else {
			episodes.push({ start: p.timestamp, end: p.timestamp, peak_score: p.score, peak_level: p.alert_level, peak_at: p.timestamp });
		}
	}
	return episodes;
}

history.get("/", async (c) => {
	const q = query.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { min_level, days, limit } = q.data;
	const since = new Date(Date.now() - days * 86400_000).toISOString();

	const [events, national] = await Promise.all([
		c.env.DB.prepare(
			`SELECT id, title, category, state, city, peak_alert_level, peak_pulse, peak_at, detected_at,
			        confidence, signal_count, source_count
			 FROM events WHERE peak_alert_level >= ?1 AND detected_at >= ?2
			 ORDER BY peak_at DESC LIMIT ?3`,
		)
			.bind(min_level, since, limit)
			.all<Record<string, string | number | null>>(),
		c.env.DB.prepare(
			`SELECT timestamp, score, alert_level FROM pulse_history
			 WHERE scope = 'BR' AND alert_level >= ?1 AND timestamp >= ?2 ORDER BY timestamp DESC LIMIT 5000`,
		)
			.bind(min_level, since)
			.all<Point>(),
	]);

	const entries = [
		...events.results.map((e) => ({
			kind: "event" as const,
			event_id: e.id,
			date: e.peak_at,
			level: e.peak_alert_level,
			peak_pulse: e.peak_pulse,
			title: e.title,
			category: e.category,
			state: e.state,
			city: e.city,
			confidence: e.confidence,
			signal_count: e.signal_count,
			source_count: e.source_count,
			detected_at: e.detected_at,
		})),
		...toEpisodes([...national.results].reverse()).map((ep) => ({
			kind: "national" as const,
			date: ep.peak_at,
			level: ep.peak_level,
			peak_pulse: ep.peak_score,
			title: `Pulso nacional em nível ${ep.peak_level}`,
			started_at: ep.start,
			ended_at: ep.end,
			duration_minutes: Math.round((Date.parse(ep.end) - Date.parse(ep.start)) / 60_000),
		})),
	]
		.sort((a, b) => String(b.date).localeCompare(String(a.date)))
		.slice(0, limit);

	c.header("Cache-Control", cacheControl(60));
	return c.json({ min_level, days, entries });
});
