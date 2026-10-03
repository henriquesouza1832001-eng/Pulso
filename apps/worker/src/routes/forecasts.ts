import { Hono } from "hono";
import { z } from "zod";
import type { Forecast } from "@pulso/shared";
import type { AppEnv } from "../env";
import { cacheControl } from "../lib/cache";

/**
 * Previsões (públicas). Toda resposta carrega o aviso de que são PROBABILIDADES, não fatos.
 * Método com menos de MIN_RESOLVED previsões resolvidas é EXPERIMENTAL.
 */
export const forecasts = new Hono<AppEnv>();

export const MIN_RESOLVED = 100;
const NOTICE = "PREVISÃO (probabilidade), não fato. Veja o histórico de acertos em /api/forecasts/track-record.";

interface Row {
	id: string; kind: string; question: string; scope: string; metric: string; comparator: string;
	threshold: number; method: string; method_version: string; probability: number;
	interval_low: number; interval_high: number; horizon_minutes: number; created_at: string;
	resolves_at: string; evidence: string; status: string; outcome: number | null;
	observed_value: number | null; resolved_at: string | null; brier: number | null;
}

const COLS =
	"id,kind,question,scope,metric,comparator,threshold,method,method_version,probability,interval_low,interval_high,horizon_minutes,created_at,resolves_at,evidence,status,outcome,observed_value,resolved_at,brier";

async function resolvedByMethod(db: D1Database): Promise<Map<string, number>> {
	const { results } = await db
		.prepare("SELECT method, COUNT(*) AS n FROM forecasts WHERE status = 'resolved' GROUP BY method")
		.all<{ method: string; n: number }>();
	return new Map(results.map((r) => [r.method, r.n]));
}

function toForecast(r: Row, resolved: Map<string, number>): Forecast {
	let evidence: Record<string, unknown> = {};
	try {
		evidence = JSON.parse(r.evidence);
	} catch {
		// evidência corrompida não derruba a API
	}
	const { id, ...rest } = r;
	return {
		forecast_id: id,
		...rest,
		evidence,
		experimental: (resolved.get(r.method) ?? 0) < MIN_RESOLVED,
	} as Forecast;
}

const listQuery = z.object({
	status: z.enum(["open", "resolved", "void"]).optional(),
	scope: z.string().regex(/^(BR|UF:[A-Z]{2})$/).optional(),
	limit: z.coerce.number().int().min(1).max(100).default(30),
});

forecasts.get("/", async (c) => {
	const q = listQuery.safeParse(c.req.query());
	if (!q.success) return c.json({ error: "invalid_query" }, 400);
	const { status, scope, limit } = q.data;
	const { results } = await c.env.DB.prepare(
		`SELECT ${COLS} FROM forecasts
		 WHERE (?1 IS NULL OR status = ?1) AND (?2 IS NULL OR scope = ?2)
		 ORDER BY created_at DESC LIMIT ?3`,
	)
		.bind(status ?? null, scope ?? null, limit)
		.all<Row>();
	const resolved = await resolvedByMethod(c.env.DB);
	c.header("Cache-Control", cacheControl(15));
	return c.json({ notice: NOTICE, forecasts: results.map((r) => toForecast(r, resolved)) });
});

/** Histórico de acertos: o que dá credibilidade (ou não) a cada método. */
forecasts.get("/track-record", async (c) => {
	const [methods, bins] = await Promise.all([
		c.env.DB.prepare(
			`SELECT method, method_version,
			        SUM(status='resolved') AS n_resolved, SUM(status='open') AS n_open, SUM(status='void') AS n_void,
			        AVG(CASE WHEN status='resolved' THEN brier END) AS mean_brier,
			        AVG(CASE WHEN status='resolved' THEN probability END) AS mean_probability,
			        AVG(CASE WHEN status='resolved' THEN outcome END) AS observed_rate
			 FROM forecasts GROUP BY method, method_version ORDER BY method`,
		).all<Record<string, number | string | null>>(),
		c.env.DB.prepare(
			`SELECT method, MIN(CAST(probability * 5 AS INTEGER), 4) AS bin, COUNT(*) AS n,
			        AVG(probability) AS mean_probability, AVG(outcome) AS observed_rate
			 FROM forecasts WHERE status='resolved' GROUP BY method, bin ORDER BY method, bin`,
		).all<Record<string, number | string | null>>(),
	]);
	c.header("Cache-Control", cacheControl(60));
	return c.json({
		notice: NOTICE,
		min_resolved_for_non_experimental: MIN_RESOLVED,
		methods: methods.results.map((m) => {
			const n = Number(m.n_resolved ?? 0);
			const rate = m.observed_rate === null ? null : Number(m.observed_rate);
			const brier = m.mean_brier === null ? null : Number(m.mean_brier);
			// Referência ingênua: sempre prever a taxa média observada. Skill > 0 = melhor que a referência.
			const reference = rate === null ? null : rate * (1 - rate);
			return {
				...m,
				experimental: n < MIN_RESOLVED,
				brier_reference: reference,
				skill: brier !== null && reference ? 1 - brier / reference : null,
			};
		}),
		calibration: bins.results, // faixas de 20%: probabilidade média prevista x frequência observada
	});
});

forecasts.get("/:id", async (c) => {
	const row = await c.env.DB.prepare(`SELECT ${COLS} FROM forecasts WHERE id = ?1`)
		.bind(c.req.param("id"))
		.first<Row>();
	if (!row) return c.json({ error: "not_found" }, 404);
	const resolved = await resolvedByMethod(c.env.DB);
	c.header("Cache-Control", cacheControl(15));
	return c.json({ notice: NOTICE, forecast: toForecast(row, resolved) });
});
