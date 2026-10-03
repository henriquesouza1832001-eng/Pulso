import { describe, expect, it } from "vitest";
import { Hono } from "hono";
import { adminAuthorized, ENGINE_READ_ROUTES, engineAuthorized, safeEqual } from "../src/lib/auth";
import { admin } from "../src/routes/admin";
import type { AppEnv } from "../src/env";

describe("engineAuthorized", () => {
	it("aceita só 'Bearer <token>' com o token certo", () => {
		expect(engineAuthorized("Bearer segredo-123", "segredo-123")).toBe(true);
		expect(engineAuthorized("Bearer errado", "segredo-123")).toBe(false);
	});

	it("recusa o token cru, sem o esquema Bearer, e cabeçalhos vazios ou malformados", () => {
		expect(engineAuthorized("segredo-123", "segredo-123")).toBe(false); // antes: aceito
		expect(engineAuthorized("bearer segredo-123", "segredo-123")).toBe(false);
		expect(engineAuthorized("Bearer ", "segredo-123")).toBe(false);
		expect(engineAuthorized(undefined, "segredo-123")).toBe(false);
	});

	it("sem segredo configurado fecha tudo (fail-closed)", () => {
		expect(engineAuthorized("Bearer x", undefined)).toBe(false);
		expect(engineAuthorized("Bearer ", "")).toBe(false);
	});
});

describe("safeEqual", () => {
	it("compara certo e rejeita prefixos, sufixos e comprimentos diferentes", () => {
		expect(safeEqual("abc", "abc")).toBe(true);
		expect(safeEqual("abc", "abd")).toBe(false);
		expect(safeEqual("ab", "abc")).toBe(false);
		expect(safeEqual("abcd", "abc")).toBe(false);
		expect(safeEqual("", "abc")).toBe(false);
	});
});

describe("adminAuthorized (menor privilégio, RT-007)", () => {
	const both = { INGEST_TOKEN: "ingest-tok", ADMIN_TOKEN: "admin-tok" };
	const onlyIngest = { INGEST_TOKEN: "ingest-tok" };
	it("sem ADMIN_TOKEN: o token do ingest vale em tudo (compatibilidade)", () => {
		expect(adminAuthorized("Bearer ingest-tok", onlyIngest, "/engine-status")).toBe(true);
		expect(adminAuthorized("Bearer ingest-tok", onlyIngest, "/observations")).toBe(true);
		expect(adminAuthorized("Bearer outro", onlyIngest, "/observations")).toBe(false);
	});
	it("com ADMIN_TOKEN: rota de operador só aceita o ADMIN_TOKEN", () => {
		for (const p of ["/engine-status", "/overview", "/turso-ping", "/calibrators", "/forecast-registry", "/drivers", "/shadow-results", "/forecast-trajectory"]) {
			expect(adminAuthorized("Bearer admin-tok", both, p)).toBe(true);
			expect(adminAuthorized("Bearer ingest-tok", both, p)).toBe(false); // quem escreve o lote não lê o painel
		}
	});
	it("com ADMIN_TOKEN: rota que o Engine lê aceita os dois", () => {
		for (const p of ENGINE_READ_ROUTES) {
			expect(adminAuthorized("Bearer ingest-tok", both, p)).toBe(true);
			expect(adminAuthorized("Bearer admin-tok", both, p)).toBe(true);
		}
	});
	it("token errado, ausente ou cru nunca passa; sem nenhum segredo fecha tudo", () => {
		expect(adminAuthorized("Bearer x", both, "/series")).toBe(false);
		expect(adminAuthorized(undefined, both, "/series")).toBe(false);
		expect(adminAuthorized("admin-tok", both, "/engine-status")).toBe(false);
		expect(adminAuthorized("Bearer x", {}, "/series")).toBe(false);
	});
	it("o conjunto de rotas do Engine cobre exatamente o que o client.py chama", () => {
		expect([...ENGINE_READ_ROUTES].sort()).toEqual(["/events-digest", "/forecasts/open", "/investigations", "/observations", "/pulse-history", "/series", "/signals"]);
	});
});

describe("rotas admin pelo app real", () => {
	const mk = (env: Record<string, string>) => {
		const a = new Hono<AppEnv>();
		a.route("/api/admin", admin);
		a.onError((_e, c) => c.json({ error: "internal_error" }, 500));
		return (path: string, token: string) => a.request(path, { headers: { Authorization: `Bearer ${token}` } }, { DB: { prepare: () => { throw new Error("db"); } }, ...env } as never).then((r) => r.status);
	};
	it("com ADMIN_TOKEN: ingest-token é 401 em /engine-status e passa a auth em /observations; admin-token passa nos dois", async () => {
		const get = mk({ INGEST_TOKEN: "ingest-tok", ADMIN_TOKEN: "admin-tok", ALLOWED_ORIGINS: "", GITHUB_REPO: "x/y" });
		expect(await get("/api/admin/engine-status", "ingest-tok")).toBe(401);
		expect(await get("/api/admin/engine-status", "admin-tok")).not.toBe(401);
		expect(await get("/api/admin/observations", "ingest-tok")).not.toBe(401);
		expect(await get("/api/admin/observations", "admin-tok")).not.toBe(401);
	});
});
