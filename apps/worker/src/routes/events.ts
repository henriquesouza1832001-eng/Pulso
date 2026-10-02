import { Hono } from "hono";
import { z } from "zod";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";
import { EVENT_COLUMNS, toEvent, type EventRow } from "../lib/rows";

export const events = new Hono<AppEnv>();

const listQuery = z.object({
	category: z.string().regex(/^[A-Z_]{2,20}$/).optional(),
	state: z.string().regex(/^[A-Za-z]{2}$/).optional(),
	limit: z.coerce.number().int().min(1).max(100).default(30),
});

events.get("/", async (c) => {
	const q = listQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { category, state, limit } = q.data;
	const { results } = await c.env.DB.prepare(
		`SELECT ${EVENT_COLUMNS} FROM events
		 WHERE resolved_at IS NULL
		   AND (?1 IS NULL OR category = ?1)
		   AND (?2 IS NULL OR state = ?2)
		 ORDER BY pulse DESC, updated_at DESC LIMIT ?3`,
	)
		.bind(category ?? null, state?.toUpperCase() ?? null, limit)
		.all<EventRow>();
	c.header("Cache-Control", cacheControl(5));
	return c.json({ events: results.map(toEvent) });
});

events.get("/:id", async (c) => {
	const id = c.req.param("id");
	const row = await c.env.DB.prepare(`SELECT ${EVENT_COLUMNS} FROM events WHERE id = ?1`)
		.bind(id)
		.first<EventRow>();
	if (!row) return c.json({ error: "not_found" }, 404);
	// Transparência: toda fonte e sinal que sustenta o evento.
	const { results: signals } = await c.env.DB.prepare(
		`SELECT s.id AS signal_id, s.source_id, src.name AS source_name, s.source_class, s.timestamp,
		        s.collected_at, s.title, s.url, s.category
		 FROM signals s JOIN sources src ON src.id = s.source_id
		 WHERE s.event_id = ?1 ORDER BY s.timestamp ASC LIMIT 200`,
	)
		.bind(id)
		.all();
	c.header("Cache-Control", cacheControl(5));
	return c.json({ event: toEvent(row), signals });
});
