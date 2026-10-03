import { describe, expect, it } from "vitest";
import type { Fault } from "./helpers/hrana";
import { BATCH, onlyWrite, setup, TABLES } from "./helpers/ingest";

/**
 * ENSAIO DE FALHA DO STORAGE (RT-005). O adaptador Turso, sob falha induzida, nunca pode: perder dado confirmado, duplicar ao
 * reenviar, nem deixar escrita parcial. Roda o `/api/ingest` REAL sobre SQLite real (via Hrana de mentira com injeção de falha).
 * Não prova o servidor remoto: prova a lógica do Worker e do adaptador diante de rede caída, resposta perdida e HTTP 5xx.
 */
describe("ensaio de falha: ingest sobre Turso", () => {
	it("referência: lote limpo grava tudo uma vez; no reenvio idêntico só o batimento de saúde das fontes muda", async () => {
		const s = setup();
		const r1 = await s.post(BATCH);
		expect(r1.status, JSON.stringify(await r1.clone().json())).toBe(200);
		const base = s.counts();
		expect(Object.values(base).every((n) => n >= 1)).toBe(true);
		const dump = () => JSON.stringify(TABLES.map((x) => s.sqlite.prepare(`SELECT * FROM ${x}`).all()).map((rows, i) => [TABLES[i], rows]));
		const before = JSON.parse(dump());
		const r2 = (await (await s.post(BATCH)).json()) as { budget: { written: number } };
		const after = JSON.parse(dump());
		const changed = before.filter((b: any, i: number) => JSON.stringify(b) !== JSON.stringify(after[i])).map((b: any) => b[0]);
		// `source_health` é ESTADO de batimento (last_check/last_success avançam a cada ciclo por desenho), não evento: é a única exceção, e é 1 linha por fonte.
		expect(changed).toEqual(["source_health"]);
		expect(r2.budget.written).toBe(1); // só a linha do batimento
		expect(s.counts()).toEqual(base);
	});

	it.each<[string, Fault]>([["rede cai antes do servidor agir", "before"], ["servidor responde HTTP 500", "http500"]])("%s: 5xx com request_id, NADA gravado, e o reenvio grava exatamente uma vez", async (_name, kind) => {
		const clean = setup();
		await clean.post(BATCH);
		const expected = clean.counts();

		let armed = true;
		const s = setup((n, body) => (armed ? onlyWrite(kind)(n, body) : undefined));
		const r = await s.post(BATCH);
		const body = (await r.json()) as { error: string; request_id: string };
		expect(r.status).toBe(500);
		expect(body.error).toBe("internal_error");
		expect(body.request_id).toBeTruthy();
		expect(Object.values(s.counts()).every((n) => n === 0)).toBe(true); // sem escrita parcial

		armed = false; // a rede volta: o Engine reenvia o MESMO lote
		expect((await s.post(BATCH)).status).toBe(200);
		expect(s.counts()).toEqual(expected);
	});

	it("resposta PERDIDA depois do commit: o dado está lá e o reenvio não duplica nada", async () => {
		const clean = setup();
		await clean.post(BATCH);
		const expected = clean.counts();

		let armed = true;
		const s = setup((n, body) => (armed ? onlyWrite("after")(n, body) : undefined));
		const lost = await s.post(BATCH);
		expect(lost.status).toBe(500); // o Engine não sabe se gravou: vai reenviar
		// o servidor JÁ gravou o dado de verdade (nada se perdeu); a observabilidade (lote à parte) ainda não rodou: só ela falta
		const core = (c: Record<string, number>) => ({ ...c, source_runtime: 0, engine_cycle: 0 });
		expect(core(s.counts())).toEqual(core(expected));

		armed = false;
		const retry = (await (await s.post(BATCH)).json()) as { budget: { written: number } };
		expect(retry.budget.written).toBe(3); // batimento de saúde (1) + as 2 linhas de observabilidade que o 500 impediu; nenhuma linha de dado duplicada
		expect(s.counts()).toEqual(expected);
	});

	describe("contador do orçamento de escrita (write_budget): nunca subconta", () => {
		const spent = (s: ReturnType<typeof setup>) => (s.sqlite.prepare("SELECT COALESCE(SUM(rows),0) AS r FROM write_budget").get() as { r: number }).r;

		it("caminho normal: a reserva é trocada pelo valor REAL e o contador fica exato", async () => {
			const s = setup();
			const body = (await (await s.post(BATCH)).json()) as { budget: { written: number } };
			expect(body.budget.written).toBeGreaterThan(0);
			expect(spent(s)).toBe(body.budget.written);
		});

		it("resposta PERDIDA depois do commit: o contador NÃO fica abaixo do que foi gravado (a reserva está na mesma transação)", async () => {
			const clean = setup();
			const real = ((await (await clean.post(BATCH)).json()) as { budget: { written: number } }).budget.written;
			let armed = true;
			const s = setup((n, body) => (armed ? onlyWrite("after")(n, body) : undefined));
			await s.post(BATCH); // 500: o servidor gravou, a resposta se perdeu, ninguém acertou o contador
			expect(spent(s)).toBeGreaterThanOrEqual(real); // erra para MAIS, nunca para menos
			armed = false;
			await s.post(BATCH); // o Engine reenvia: o contador volta a ser trocado pelo valor real do reenvio
			expect(spent(s)).toBeGreaterThanOrEqual(real);
		});

		it("rede cai ANTES do commit: a reserva some junto com o lote (atômica), nada fica contado", async () => {
			const s = setup(onlyWrite("before"));
			await s.post(BATCH);
			expect(spent(s)).toBe(0);
		});

		it("sem a tabela write_budget (D1 sem a migration 0005) o ingest segue: 200, dado gravado, sem contagem", async () => {
			const s = setup();
			s.sqlite.exec("DROP TABLE write_budget;");
			const r = await s.post(BATCH);
			expect(r.status).toBe(200);
			expect((s.sqlite.prepare("SELECT COUNT(*) AS n FROM events").get() as { n: number }).n).toBe(1);
		});
	});

	it("lote que falha NO MEIO desfaz tudo (transação do adaptador)", async () => {
		const s = setup();
		await s.db.exec("CREATE TABLE IF NOT EXISTS parcial (id TEXT PRIMARY KEY)");
		const stmts = [s.db.prepare("INSERT INTO parcial VALUES (?1)").bind("a"), s.db.prepare("INSERT INTO parcial VALUES (?1)").bind("b"), s.db.prepare("INSERT INTO parcial VALUES (?1)").bind("a")];
		await expect(s.db.batch(stmts)).rejects.toThrow(/turso_batch_failed/);
		expect((s.sqlite.prepare("SELECT COUNT(*) AS c FROM parcial").get() as { c: number }).c).toBe(0);
	});
});
