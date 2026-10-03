import { Hono } from "hono";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";
import { CAMERAS } from "../data/cameras";

export const cameras = new Hono<AppEnv>();

/** Catálogo de câmeras: prévia do provedor (quando existe) + link para a origem. Estático, sem banco. */
cameras.get("/", (c) => {
	c.header("Cache-Control", cacheControl(300));
	return c.json({ cameras: CAMERAS, generated_at: new Date().toISOString() });
});
