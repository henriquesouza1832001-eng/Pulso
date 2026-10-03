import { afterEach, describe, expect, it, vi } from "vitest";
import worker from "../src/index";

const ctx = { waitUntil() {}, passThroughOnException() {} } as unknown as ExecutionContext;
const app = { request: (path: string, init: RequestInit, e: unknown) => worker.fetch!(new Request(`http://localhost${path}`, init) as never, e as never, ctx) };

const hranaOk = (rows: unknown[][] = [[{ type: "integer", value: "7" }]], names = ["n"]) =>
	new Response(
		JSON.stringify({
			results: [{ type: "ok", response: { type: "execute", result: { cols: names.map((name) => ({ name })), rows, affected_row_count: 0, last_insert_rowid: null } } }, { type: "ok", response: { type: "close" } }],
		}),
	);

function d1Stub() {
	const calls: string[] = [];
	const stmt = { bind: () => stmt, first: async () => (calls.push("first"), null), all: async () => (calls.push("all"), { results: [] }), run: async () => (calls.push("run"), {}) };
	return { calls, db: { prepare: () => stmt, batch: async () => [] } as unknown as D1Database };
}
const env = (db: D1Database, extra: Record<string, string> = {}) => ({ DB: db, ALLOWED_ORIGINS: "http://localhost:5173", GITHUB_REPO: "a/b", INGEST_TOKEN: "tok", ...extra });

afterEach(() => vi.unstubAllGlobals());

describe("troca de banco por DB_BACKEND", () => {
	it("com turso, a rota consulta o Turso e não toca o D1", async () => {
		const d1 = d1Stub();
		const fetchMock = vi.fn(async () => hranaOk());
		vi.stubGlobal("fetch", fetchMock);
		const res = await app.request("/api/stats", {}, env(d1.db, { DB_BACKEND: "turso", TURSO_URL: "libsql://x.turso.io", TURSO_TOKEN: "t" }));
		expect(res.status).toBe(200);
		expect(fetchMock).toHaveBeenCalled();
		expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe("https://x.turso.io/v2/pipeline");
		expect(d1.calls).toEqual([]); // o D1 não foi usado
	});

	it("sem DB_BACKEND (ou sem segredos), segue no D1", async () => {
		for (const extra of [{}, { DB_BACKEND: "turso" }]) {
			const d1 = d1Stub();
			const fetchMock = vi.fn(async () => hranaOk());
			vi.stubGlobal("fetch", fetchMock);
			const res = await app.request("/api/stats", {}, env(d1.db, extra));
			expect(res.status).toBe(200);
			expect(fetchMock).not.toHaveBeenCalled();
			expect(d1.calls.length).toBeGreaterThan(0);
		}
	});

	it("a rota turso-ping exige o token e não devolve segredos", async () => {
		const d1 = d1Stub();
		expect((await app.request("/api/admin/turso-ping", {}, env(d1.db))).status).toBe(401);
		const semSegredos = await app.request("/api/admin/turso-ping", { headers: { Authorization: "Bearer tok" } }, env(d1.db));
		expect(semSegredos.status).toBe(503);
		const okRes = (rows: unknown[][], names: string[]) => ({ cols: names.map((name) => ({ name })), rows, affected_row_count: 0, last_insert_rowid: null });
		vi.stubGlobal(
			"fetch",
			vi.fn(async (_u: string, init: { body: string }) => {
				const rq = JSON.parse(init.body).requests[0];
				const result =
					rq.type === "batch"
						? { response: { type: "batch", result: { step_results: [okRes([], []), okRes([], []), okRes([], []), okRes([], []), null], step_errors: [null, null, null, null, null] } } }
						: { response: { type: "execute", result: okRes([[{ type: "text", value: "3.47.0" }]], ["v"]) } };
				return new Response(JSON.stringify({ results: [{ type: "ok", ...result }, { type: "ok", response: { type: "close" } }] }));
			}),
		);
		const r = await app.request("/api/admin/turso-ping", { headers: { Authorization: "Bearer tok" } }, env(d1.db, { TURSO_URL: "libsql://x.turso.io", TURSO_TOKEN: "segredo-turso" }));
		const text = await r.text();
		expect(text).not.toContain("segredo-turso");
		expect(text).toContain("backend_ativo");
	});
});
