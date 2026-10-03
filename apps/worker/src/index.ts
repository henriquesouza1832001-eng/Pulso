import { Hono } from "hono";
import { cors } from "hono/cors";
import { bodyLimit } from "hono/body-limit";
import { errorHandler, INGEST_MAX_BYTES, requestContext } from "./lib/http";
import { health } from "./routes/health";
import { pulse } from "./routes/pulse";
import { events } from "./routes/events";
import { map } from "./routes/map";
import { ingest } from "./routes/ingest";
import { admin } from "./routes/admin";
import { forecasts } from "./routes/forecasts";
import { stats } from "./routes/stats";
import { history } from "./routes/history";
import { cameras } from "./routes/cameras";
import type { AppEnv, Bindings } from "./env";
import { TursoDatabase } from "./lib/turso";
import { dispatchCollection, dispatchHealthcheck, isHealthcheckSlot } from "./lib/dispatch";

const app = new Hono<AppEnv>();

app.use("*", requestContext);

// Corpo do ingest limitado ANTES de ler: lote legítimo do Engine tem poucos MB; acima disso é erro ou abuso (413, nunca OOM).
app.use(
	"/api/ingest",
	bodyLimit({ maxSize: INGEST_MAX_BYTES, onError: (c) => c.json({ error: "payload_too_large", max_bytes: INGEST_MAX_BYTES }, 413) }),
);

// Troca o banco por requisição: com DB_BACKEND="turso" as rotas continuam usando `c.env.DB`, agora sobre o Turso.
app.use("*", async (c, next) => {
	if (c.env.DB_BACKEND === "turso" && c.env.TURSO_URL && c.env.TURSO_TOKEN) {
		c.env = { ...c.env, DB: new TursoDatabase({ url: c.env.TURSO_URL, token: c.env.TURSO_TOKEN }) as unknown as D1Database };
	}
	await next();
});

app.use("/api/*", async (c, next) => {
	const origins = c.env.ALLOWED_ORIGINS.split(",").map((o) => o.trim());
	return cors({ origin: origins, allowMethods: ["GET", "POST"], maxAge: 600 })(c, next);
});

app.route("/api/health", health);
app.route("/api/pulse", pulse);
app.route("/api/events", events);
app.route("/api/map", map);
app.route("/api/forecasts", forecasts);
app.route("/api/stats", stats);
app.route("/api/history", history);
app.route("/api/cameras", cameras);
app.route("/api/ingest", ingest);
app.route("/api/admin", admin);

app.notFound((c) => c.json({ error: "not_found" }, 404));
app.onError(errorHandler);

export default {
	fetch: app.fetch,
	// Cron Trigger (wrangler.jsonc > triggers.crons): aciona a coleta no minuto certo.
	async scheduled(event: ScheduledController, env: Bindings, ctx: ExecutionContext) {
		ctx.waitUntil(
			dispatchCollection(env).then((r) =>
				r.ok ? console.log("coleta acionada") : console.error("falha ao acionar coleta:", r.reason ?? r.status),
			),
		);
		if (isHealthcheckSlot(new Date(event.scheduledTime))) {
			ctx.waitUntil(
				dispatchHealthcheck(env).then((r) =>
					r.ok ? console.log("verificação de saúde acionada") : console.error("falha ao acionar a saúde:", r.reason ?? r.status),
				),
			);
		}
	},
} satisfies ExportedHandler<Bindings>;
