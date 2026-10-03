import { describe, expect, it } from "vitest";
import { budgetMode, CRITICAL_FROM, ECONOMY_FROM, shedBatch, utcDay, type BatchLike } from "../src/lib/budget";

const batch = (): BatchLike => ({
	sources: [{ id: "s1" }],
	catalog_complete: true,
	events: [
		{ event_id: "ev-1", alert_level: 1 },
		{ event_id: "ev-2", alert_level: 2 },
		{ event_id: "ev-3", alert_level: 4 },
	],
	signals: [{ event_id: "ev-1" }, { event_id: "ev-2" }, { event_id: "ev-3" }, { event_id: null }],
	pulses: [{ scope: "BR" }, { scope: "UF:SP" }],
	source_health: [{ status: "ONLINE" }, { status: "OFFLINE" }],
	series: [{ scope: "BR" }, { scope: "UF:RJ" }],
	forecasts: [{ status: "open" }, { status: "resolved" }],
	observations: [{ scope: "BR" }, { scope: "UF:MG" }],
	investigations: [{ status: "NEW" }, { status: "INVESTIGATING" }, { status: "CLOSED" }],
	forecast_registry: [{ id: "f1" }],
	shadow_results: [{ id: "s1" }],
	driver_registry: [{ id: "d1" }],
	calibrators: [{ id: "c1" }],
	source_runtime: [{ source_id: "a" }],
	engine_cycle: { cycle_at: "2026-10-03T12:00:00Z" },
});

describe("governador do orçamento de escrita", () => {
	it("o modo muda nos limiares e o dia é UTC", () => {
		expect(budgetMode(0)).toBe("normal");
		expect(budgetMode(ECONOMY_FROM - 1)).toBe("normal");
		expect(budgetMode(ECONOMY_FROM)).toBe("economy");
		expect(budgetMode(CRITICAL_FROM)).toBe("critical");
		expect(utcDay(new Date("2026-10-04T02:30:00-03:00"))).toBe("2026-10-04");
		expect(utcDay(new Date("2026-10-03T22:00:00-03:00"))).toBe("2026-10-04"); // 22h em Brasília já é o dia seguinte em UTC
	});

	it("normal não corta nada", () => {
		const b = batch();
		const r = shedBatch(b, "normal");
		expect(r.batch).toBe(b);
		expect(r.shed).toEqual({});
	});

	it("economia: corta nível 1, só série nacional, só saúde com problema, catálogo não é enviado", () => {
		const { batch: out, shed } = shedBatch(batch(), "economy");
		expect(out.events.map((e) => e.event_id)).toEqual(["ev-2", "ev-3"]);
		expect(out.signals).toEqual([{ event_id: "ev-2" }, { event_id: "ev-3" }]); // sinal sem evento mantido não entra (chave estrangeira)
		expect(out.series).toEqual([{ scope: "BR" }]);
		expect(out.source_health).toEqual([{ status: "OFFLINE" }]);
		expect(out.sources).toEqual([]);
		expect(out.catalog_complete).toBe(false); // senão as fontes ausentes seriam desativadas
		expect(out.pulses).toHaveLength(2);
		expect(out.observations).toEqual([{ scope: "BR" }]); // histórico agregado: só o nacional em economia
		expect(out.investigations).toEqual([{ status: "NEW" }, { status: "CLOSED" }]); // economia: só abertura e encerramento
		expect(out.forecast_registry).toHaveLength(1); // auditoria de previsão continua em economia
		expect(out.shadow_results).toEqual([]); // comparação e drivers esperam a cota folgar
		expect(out.driver_registry).toEqual([]);
		expect(out.calibrators).toHaveLength(1); // versões de calibrador são raras e minúsculas: continuam em economia
		expect(out.source_runtime).toHaveLength(1); // estado por fonte e resumo do ciclo são operacionais e minúsculos: continuam em economia
		expect(out.engine_cycle).not.toBeNull();
		expect(shed.events).toBe(1);
	});

	it("crítico: só alerta alto, pulso nacional, previsões já resolvidas e nenhuma série", () => {
		const { batch: out } = shedBatch(batch(), "critical");
		expect(out.events.map((e) => e.event_id)).toEqual(["ev-3"]);
		expect(out.signals).toEqual([{ event_id: "ev-3" }]);
		expect(out.pulses).toEqual([{ scope: "BR" }]);
		expect(out.series).toEqual([]);
		expect(out.forecasts).toEqual([{ status: "resolved" }]); // a resolução de uma previsão nunca se perde
		expect(out.observations).toEqual([]);
		expect(out.investigations).toEqual([]);
		expect(out.forecast_registry).toEqual([]);
		expect(out.calibrators).toEqual([]);
		expect(out.source_runtime).toEqual([]);
		expect(out.engine_cycle).toBeNull();
	});
});
