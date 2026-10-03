/**
 * Turso (libSQL) com a MESMA superfície do D1 que o Worker usa: `prepare(sql).bind(...).first()/all()/run()` e `batch()`.
 * Assim as rotas não mudam: o middleware do `index.ts` troca `c.env.DB` por esta classe quando `DB_BACKEND = "turso"`.
 *
 * Protocolo: Hrana sobre HTTP (`POST {url}/v2/pipeline`, `Authorization: Bearer`). O `batch()` roda numa transação
 * (BEGIN ... COMMIT; ROLLBACK se algum passo falhar), como no D1. Parâmetros numerados (`?1`, `?2`) funcionam porque
 * o SQLite associa `?N` à posição N da lista de argumentos.
 * Ver docs/decisions/0008-orcamento-de-escrita-do-d1.md.
 */

type HranaValue =
	| { type: "null" }
	| { type: "integer"; value: string }
	| { type: "float"; value: number }
	| { type: "text"; value: string }
	| { type: "blob"; base64: string };

export function toHrana(v: unknown): HranaValue {
	if (v === null || v === undefined) return { type: "null" };
	if (typeof v === "boolean") return { type: "integer", value: v ? "1" : "0" };
	if (typeof v === "number") return Number.isInteger(v) ? { type: "integer", value: String(v) } : { type: "float", value: v };
	if (typeof v === "bigint") return { type: "integer", value: v.toString() };
	return { type: "text", value: String(v) };
}

export function fromHrana(v: HranaValue): unknown {
	switch (v.type) {
		case "null":
			return null;
		case "integer":
			return Number(v.value);
		case "float":
			return v.value;
		case "text":
			return v.value;
		default:
			return v.base64;
	}
}

interface Cell {
	name: string | null;
}
interface ExecResult {
	cols: Cell[];
	rows: HranaValue[][];
	affected_row_count: number;
	last_insert_rowid: string | null;
}

export interface TursoConfig {
	url: string;
	token: string;
	fetchImpl?: typeof fetch;
}

const stmtBody = (sql: string, args: unknown[]) => ({ sql, args: args.map(toHrana) });

async function pipeline(cfg: TursoConfig, requests: unknown[]): Promise<{ results: any[] }> {
	const base = cfg.url.replace(/^libsql:\/\//, "https://").replace(/\/+$/, "");
	const res = await (cfg.fetchImpl ?? fetch)(`${base}/v2/pipeline`, {
		method: "POST",
		headers: { Authorization: `Bearer ${cfg.token}`, "Content-Type": "application/json" },
		body: JSON.stringify({ requests: [...requests, { type: "close" }] }),
		signal: AbortSignal.timeout(25_000),
	});
	if (!res.ok) throw new Error(`turso_http_${res.status}: ${(await res.text()).slice(0, 200)}`);
	return (await res.json()) as { results: any[] };
}

function unwrap(r: any): ExecResult {
	if (r.type !== "ok") throw new Error(`turso_error: ${r.error?.message ?? JSON.stringify(r).slice(0, 200)}`);
	return r.response.result as ExecResult;
}

function shape(r: ExecResult) {
	const names = r.cols.map((c) => c.name ?? "");
	const results = r.rows.map((row) => Object.fromEntries(row.map((cell, i) => [names[i], fromHrana(cell)])));
	// `rows_written` aproxima as linhas alteradas (o Turso não conta as de índice como o D1); serve ao governador de orçamento.
	return { results, success: true, meta: { rows_read: r.rows.length, rows_written: r.affected_row_count, changes: r.affected_row_count } };
}

export class TursoStatement {
	private args: unknown[] = [];
	constructor(
		private readonly cfg: TursoConfig,
		readonly sql: string,
	) {}
	bind(...values: unknown[]): this {
		this.args = values;
		return this;
	}
	/** @internal usado pelo batch */
	body() {
		return stmtBody(this.sql, this.args);
	}
	async all<T = Record<string, unknown>>() {
		const { results } = await pipeline(this.cfg, [{ type: "execute", stmt: this.body() }]);
		const s = shape(unwrap(results[0]));
		return { ...s, results: s.results as T[] };
	}
	async run() {
		return this.all();
	}
	async first<T = Record<string, unknown>>(column?: string): Promise<T | null> {
		const { results } = await this.all<Record<string, unknown>>();
		const row = results[0];
		if (!row) return null;
		return (column ? (row[column] ?? null) : row) as T | null;
	}
	async raw<T = unknown[]>() {
		const { results } = await this.all<Record<string, unknown>>();
		return results.map((r) => Object.values(r)) as T[];
	}
}

export class TursoDatabase {
	constructor(private readonly cfg: TursoConfig) {}
	prepare(sql: string): TursoStatement {
		return new TursoStatement(this.cfg, sql);
	}
	/** Transação: tudo ou nada, na ordem dada (igual ao `batch` do D1). */
	async batch(stmts: TursoStatement[]) {
		if (!stmts.length) return [];
		const n = stmts.length;
		const steps: unknown[] = [{ stmt: { sql: "BEGIN" } }];
		stmts.forEach((s, i) => steps.push({ condition: { type: "ok", step: i }, stmt: s.body() }));
		steps.push({ condition: { type: "ok", step: n }, stmt: { sql: "COMMIT" } });
		steps.push({ condition: { type: "not", cond: { type: "ok", step: n + 1 } }, stmt: { sql: "ROLLBACK" } });
		const { results } = await pipeline(this.cfg, [{ type: "batch", batch: { steps } }]);
		const r = results[0];
		if (r.type !== "ok") throw new Error(`turso_error: ${r.error?.message ?? "batch"}`);
		const { step_results, step_errors } = r.response.result as { step_results: (ExecResult | null)[]; step_errors: ({ message: string } | null)[] };
		// índices dos passos: 0 = BEGIN, 1..n = instruções, n+1 = COMMIT, n+2 = ROLLBACK (só roda se algo falhou)
		const failed = step_errors.findIndex((e, i) => e && i >= 1 && i <= n + 1);
		if (failed >= 0) throw new Error(`turso_batch_failed_at_${failed <= n ? failed - 1 : "commit"}: ${step_errors[failed]?.message}`);
		return stmts.map((_, i) => shape(step_results[i + 1] as ExecResult));
	}
	async exec(sql: string) {
		const { results } = await pipeline(this.cfg, [{ type: "sequence", sql }]);
		if (results[0].type !== "ok") throw new Error(`turso_error: ${results[0].error?.message}`);
	}
}
