import { Hono } from "hono";
import { cors } from "hono/cors";
import { health } from "./routes/health";
import { pulse } from "./routes/pulse";
import { events } from "./routes/events";
import { map } from "./routes/map";
import { ingest } from "./routes/ingest";
import { admin } from "./routes/admin";
import type { AppEnv } from "./env";

const app = new Hono<AppEnv>();

app.use("/api/*", async (c, next) => {
	const origins = c.env.ALLOWED_ORIGINS.split(",").map((o) => o.trim());
	return cors({ origin: origins, allowMethods: ["GET", "POST"], maxAge: 600 })(c, next);
});

app.route("/api/health", health);
app.route("/api/pulse", pulse);
app.route("/api/events", events);
app.route("/api/map", map);
app.route("/api/ingest", ingest);
app.route("/api/admin", admin);

app.notFound((c) => c.json({ error: "not_found" }, 404));
app.onError((err, c) => {
	console.error("unhandled", err);
	return c.json({ error: "internal_error" }, 500);
});

export default app;
