import { describe, expect, it } from "vitest";
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { INGEST_MAX_BYTES, requestContext } from "../src/lib/http";
import { assess, INVESTIGATION_FLOOD, STALE_AFTER_SECONDS } from "../src/lib/status";
import type { AppEnv } from "../src/env";

const base = { dbOk: true, dbLatencyMs: 20, collectionAgeSeconds: 60, budgetMode: "normal" as const, investigationsActive: 0 };

function app() {
	const a = new Hono<AppEnv>();
	a.use("*", requestContext);
	a.use("/in", bodyLimit({ maxSize: 100, onError: (c) => c.json({ error: "payload_too_large" }, 413) }));
	a.get("/ok", (c) => c.json({ fine: true }));
	a.get("/bad", (c) => c.json({ error: "invalid_query" }, 400));
	a.get("/arr", (c) => c.json([1], 400));
	a.get("/text", (c) => c.text("nope", 400));
	a.post("/in", async (c) => c.json({ n: (await c.req.text()).length }));
	a.onError((err, c) => c.json({ error: "internal_error" }, 500));
	a.get("/boom", () => {
		throw new Error("segredo interno com stack");
	});
	return a;
}

describe("envelope de erro e request_id", () => {
	it("erro JSON ganha request_id igual ao cabeçalho, mantendo o campo error", async () => {
		const r = await app().request("/bad");
		const body = (await r.json()) as Record<string, string>;
		expect(r.status).toBe(400);
		expect(body.error).toBe("invalid_query");
		expect(body.request_id).toBe(r.headers.get("x-request-id"));
	});
	it("sucesso não é alterado, mas leva o cabeçalho", async () => {
		const r = await app().request("/ok");
		expect(await r.json()).toEqual({ fine: true });
		expect(r.headers.get("x-request-id")).toBeTruthy();
	});
	it("id do chamador é aceito só se for inofensivo", async () => {
		const good = await app().request("/ok", { headers: { "x-request-id": "abc-12345678" } });
		expect(good.headers.get("x-request-id")).toBe("abc-12345678");
		const evil = await app().request("/ok", { headers: { "x-request-id": "a b;<script>" } });
		expect(evil.headers.get("x-request-id")).not.toContain(" ");
	});
	it("corpo que não é objeto JSON (lista, texto) passa intacto", async () => {
		expect(await (await app().request("/arr")).json()).toEqual([1]);
		expect(await (await app().request("/text")).text()).toBe("nope");
	});
	it("erro interno não vaza stack nem mensagem", async () => {
		const r = await app().request("/boom");
		const txt = await r.text();
		expect(r.status).toBe(500);
		expect(txt).not.toContain("segredo");
		expect(txt).toContain("request_id");
	});
});

describe("limite de corpo", () => {
	it("aceita dentro do teto e recusa acima com 413", async () => {
		expect((await app().request("/in", { method: "POST", body: "x".repeat(50) })).status).toBe(200);
		const big = await app().request("/in", { method: "POST", body: "x".repeat(500) });
		expect(big.status).toBe(413);
	});
	it("o teto do ingest é finito", () => {
		expect(INGEST_MAX_BYTES).toBeGreaterThan(0);
		expect(INGEST_MAX_BYTES).toBeLessThanOrEqual(16 * 1024 * 1024);
	});
});

describe("veredito de saúde", () => {
	it("tudo normal = ok", () => expect(assess(base)).toEqual({ status: "ok", reasons: [] }));
	it("banco fora = not_ready, mesmo com o resto bom", () => {
		const a = assess({ ...base, dbOk: false, dbLatencyMs: null });
		expect(a.status).toBe("not_ready");
		expect(a.reasons[0]).toMatch(/banco/);
	});
	it("coleta atrasada = degraded; nunca coletou = degraded (não 'ok')", () => {
		expect(assess({ ...base, collectionAgeSeconds: STALE_AFTER_SECONDS + 1 }).status).toBe("degraded");
		expect(assess({ ...base, collectionAgeSeconds: null }).status).toBe("degraded");
		expect(assess({ ...base, collectionAgeSeconds: STALE_AFTER_SECONDS }).status).toBe("ok");
	});
	it("economia e crítico degradam; degradação não rebaixa um not_ready", () => {
		expect(assess({ ...base, budgetMode: "economy" }).status).toBe("degraded");
		expect(assess({ ...base, budgetMode: "critical" }).status).toBe("degraded");
		expect(assess({ ...base, dbOk: false, dbLatencyMs: null, budgetMode: "critical" }).status).toBe("not_ready");
	});
	it("enxurrada de investigações aparece como motivo", () => {
		const a = assess({ ...base, investigationsActive: INVESTIGATION_FLOOD });
		expect(a.status).toBe("degraded");
		expect(a.reasons.join()).toMatch(/investiga/);
	});
});
