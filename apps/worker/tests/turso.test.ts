import { describe, expect, it } from "vitest";
import { fromHrana, toHrana, TursoDatabase } from "../src/lib/turso";
import { mockHrana } from "./helpers/hrana";

describe("valores Hrana", () => {
	it("converte nos dois sentidos", () => {
		expect(toHrana(null)).toEqual({ type: "null" });
		expect(toHrana(7)).toEqual({ type: "integer", value: "7" });
		expect(toHrana(1.5)).toEqual({ type: "float", value: 1.5 });
		expect(toHrana(true)).toEqual({ type: "integer", value: "1" });
		expect(toHrana("a")).toEqual({ type: "text", value: "a" });
		expect(fromHrana({ type: "integer", value: "42" })).toBe(42);
	});
});

describe("TursoDatabase (mesma superfície do D1)", () => {
	it("prepare/bind/first/all/run com parâmetros numerados", async () => {
		const { db } = mockHrana();
		await db.prepare("CREATE TABLE t (id TEXT PRIMARY KEY, n INTEGER, x REAL)").run();
		const w = await db.prepare("INSERT INTO t (id,n,x) VALUES (?1,?2,?3)").bind("a", 5, 1.5).run();
		expect(w.meta.rows_written).toBe(1);
		await db.prepare("INSERT INTO t (id,n,x) VALUES (?1,?2,?3)").bind("b", 9, null).run();
		const row = await db.prepare("SELECT id, n, x FROM t WHERE n > ?1 ORDER BY n").bind(6).first<{ id: string; n: number; x: number | null }>();
		expect(row).toEqual({ id: "b", n: 9, x: null });
		expect((await db.prepare("SELECT COUNT(*) AS c FROM t").first<{ c: number }>("c" as never)) as unknown).toBe(2);
		expect(await db.prepare("SELECT * FROM t WHERE id = ?1").bind("nada").first()).toBeNull();
		const all = await db.prepare("SELECT id FROM t ORDER BY id").all<{ id: string }>();
		expect(all.results.map((r) => r.id)).toEqual(["a", "b"]);
	});

	it("o upsert em lote com json_each (formato do ingest) e a regravação condicional", async () => {
		const { db } = mockHrana();
		await db.exec("CREATE TABLE s (id TEXT PRIMARY KEY, name TEXT, state TEXT)");
		const sql = `INSERT INTO s (id,name,state)
			SELECT json_extract(j.value,'$.id'),json_extract(j.value,'$.name'),json_extract(j.value,'$.state') FROM json_each(?1) j WHERE true
			ON CONFLICT(id) DO UPDATE SET name=excluded.name,state=excluded.state
			WHERE s.name IS NOT excluded.name OR s.state IS NOT excluded.state`;
		const rows = JSON.stringify([{ id: "1", name: "A", state: null }, { id: "2", name: "B", state: "SP" }]);
		const [first] = await db.batch([db.prepare(sql).bind(rows)]);
		expect(first.meta.rows_written).toBe(2);
		const [again] = await db.batch([db.prepare(sql).bind(rows)]);
		expect(again.meta.rows_written).toBe(0); // idêntico: nada regravado
		const changed = JSON.stringify([{ id: "1", name: "A2", state: null }]);
		const [third] = await db.batch([db.prepare(sql).bind(changed)]);
		expect(third.meta.rows_written).toBe(1);
	});

	it("o batch é uma transação: se um passo falha, nada é gravado", async () => {
		const { db, sqlite } = mockHrana();
		await db.exec("CREATE TABLE u (k TEXT PRIMARY KEY)");
		await expect(
			db.batch([db.prepare("INSERT INTO u VALUES (?1)").bind("a"), db.prepare("INSERT INTO u VALUES (?1)").bind("a")]),
		).rejects.toThrow(/turso_batch_failed_at_1/);
		expect((sqlite.prepare("SELECT COUNT(*) c FROM u").get() as { c: number }).c).toBe(0);
		await db.batch([db.prepare("INSERT INTO u VALUES (?1)").bind("a"), db.prepare("INSERT INTO u VALUES (?1)").bind("b")]);
		expect((sqlite.prepare("SELECT COUNT(*) c FROM u").get() as { c: number }).c).toBe(2);
	});

	it("erro de SQL vira exceção legível e HTTP não-200 também", async () => {
		const { db } = mockHrana();
		await expect(db.prepare("SELECT * FROM nao_existe").all()).rejects.toThrow(/turso_error/);
		const bad = new TursoDatabase({ url: "https://x", token: "t", fetchImpl: (async () => new Response("no", { status: 401 })) as unknown as typeof fetch });
		await expect(bad.prepare("SELECT 1").first()).rejects.toThrow(/turso_http_401/);
	});

	it("o token vai só no cabeçalho e libsql:// vira https://", async () => {
		const seen: { url?: string; auth?: string; body?: string } = {};
		const db = new TursoDatabase({
			url: "libsql://meu-banco.turso.io/",
			token: "segredo",
			fetchImpl: (async (url: string, init: any) => {
				seen.url = url;
				seen.auth = init.headers.Authorization;
				seen.body = init.body;
				return new Response(JSON.stringify({ results: [{ type: "ok", response: { type: "execute", result: { cols: [], rows: [], affected_row_count: 0, last_insert_rowid: null } } }] }));
			}) as unknown as typeof fetch,
		});
		await db.prepare("SELECT 1").first();
		expect(seen.url).toBe("https://meu-banco.turso.io/v2/pipeline");
		expect(seen.auth).toBe("Bearer segredo");
		expect(seen.body).not.toContain("segredo");
	});
});
