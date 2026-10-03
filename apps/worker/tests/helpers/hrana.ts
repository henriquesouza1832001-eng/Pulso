import { DatabaseSync } from "node:sqlite";
import { TursoDatabase } from "../../src/lib/turso";

/** Servidor Hrana (/v2/pipeline) de mentira, com SQLite de verdade por baixo. Valida a lógica da camada, não o servidor real. */
export type Fault = "before" | "after" | "http500" | "http429" | "dns" | "reset" | "slow" | "hang";

/** `fault(n, body)` decide a falha da n-ésima chamada: `before` = a rede cai ANTES do servidor agir (nada gravado); `after` = o servidor GRAVA e a resposta se perde; `http500` = o servidor recusa; `http429` = limite de taxa do banco; `dns` = o nome do banco não resolve; `reset` = conexão derrubada no meio (ECONNRESET); `slow` = responde, mas só depois de `slowMs`; `hang` = nunca responde (só o timeout do adaptador encerra). */
export function mockHrana(fault?: (n: number, body: any) => Fault | undefined, opts: { timeoutMs?: number; slowMs?: number } = {}) {
	const sqlite = new DatabaseSync(":memory:");
	const val = (v: any): any => (v.type === "null" ? null : v.type === "integer" ? Number(v.value) : v.value);
	const out = (v: unknown) =>
		v === null ? { type: "null" } : typeof v === "number" ? (Number.isInteger(v) ? { type: "integer", value: String(v) } : { type: "float", value: v }) : { type: "text", value: String(v) };
	const exec = (stmt: { sql: string; args?: any[] }) => {
		const s = sqlite.prepare(stmt.sql);
		const args = (stmt.args ?? []).map(val);
		if (/^\s*(select|with|pragma)/i.test(stmt.sql)) {
			const rows = s.all(...args) as Record<string, unknown>[];
			const cols = rows[0] ? Object.keys(rows[0]).map((name) => ({ name })) : [];
			return { cols, rows: rows.map((r) => Object.values(r).map(out)), affected_row_count: 0, last_insert_rowid: null };
		}
		const r = s.run(...args);
		return { cols: [], rows: [], affected_row_count: Number(r.changes), last_insert_rowid: String(r.lastInsertRowid) };
	};
	const calls: any[] = [];
	const fetchImpl = (async (_url: string, init: any) => {
		const body = JSON.parse(init.body);
		calls.push(body);
		const f = fault?.(calls.length, body);
		if (f === "before") throw new TypeError("network_down");
		if (f === "http500") return new Response("boom", { status: 500 });
		if (f === "http429") return new Response("rate limited", { status: 429, headers: { "retry-after": "30" } });
		if (f === "dns") throw new TypeError("fetch failed: getaddrinfo ENOTFOUND x.turso.io");
		if (f === "reset") throw new TypeError("fetch failed: ECONNRESET");
		if (f === "hang") return new Promise<Response>((_, reject) => init.signal?.addEventListener("abort", () => reject(init.signal.reason)));
		if (f === "slow") await new Promise((r) => setTimeout(r, opts.slowMs ?? 2100));
		const results = body.requests.map((rq: any) => {
			try {
				if (rq.type === "close") return { type: "ok", response: { type: "close" } };
				if (rq.type === "sequence") {
					sqlite.exec(rq.sql);
					return { type: "ok", response: { type: "sequence" } };
				}
				if (rq.type === "execute") return { type: "ok", response: { type: "execute", result: exec(rq.stmt) } };
				// batch com condições (ok / not)
				const step_results: any[] = [];
				const step_errors: any[] = [];
				const okAt = (c: any): boolean => (c.type === "ok" ? step_results[c.step] != null : c.type === "not" ? !okAt(c.cond) : true);
				rq.batch.steps.forEach((st: any, i: number) => {
					if (st.condition && !okAt(st.condition)) {
						step_results[i] = null;
						step_errors[i] = null;
						return;
					}
					try {
						step_results[i] = exec(st.stmt);
						step_errors[i] = null;
					} catch (e: any) {
						step_results[i] = null;
						step_errors[i] = { message: String(e.message) };
					}
				});
				return { type: "ok", response: { type: "batch", result: { step_results, step_errors } } };
			} catch (e: any) {
				return { type: "error", error: { message: String(e.message) } };
			}
		});
		if (f === "after") throw new TypeError("response_lost");
		return new Response(JSON.stringify({ results }), { status: 200 });
	}) as unknown as typeof fetch;
	return { db: new TursoDatabase({ url: "libsql://x.turso.io", token: "t", fetchImpl, timeoutMs: opts.timeoutMs }), sqlite, calls };
}
