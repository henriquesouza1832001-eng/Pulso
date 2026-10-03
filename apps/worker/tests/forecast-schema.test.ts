import { describe, expect, it } from "vitest";
import { forecastSchema } from "../src/routes/ingest";

const base = {
	forecast_id: "fc-pulse-br-gte-50-h60-2026100312", kind: "NOWCAST", question: "O Pulso do Brasil será >= 50?", scope: "BR", metric: "pulse",
	comparator: "gte", threshold: 50, method: "pulse_empirical_delta", method_version: "1", probability: 0.3, interval_low: 0.2,
	interval_high: 0.4, horizon_minutes: 60, created_at: "2026-10-03T12:00:00Z", resolves_at: "2026-10-03T13:00:00Z", evidence: {},
	status: "open", outcome: null, observed_value: null, resolved_at: null, brier: null,
};
const ok = (f: object) => forecastSchema.safeParse(f).success;

describe("coerência entre o status da previsão e os campos de resolução", () => {
	it("aberta: nenhum campo de resolução", () => {
		expect(ok(base)).toBe(true);
		expect(ok({ ...base, brier: 0.1 })).toBe(false);
		expect(ok({ ...base, outcome: 1 })).toBe(false);
		expect(ok({ ...base, observed_value: 3 })).toBe(false);
	});

	it("resolvida: resultado, Brier, valor observado e data, tudo junto", () => {
		const resolved = { ...base, status: "resolved", outcome: 1, brier: 0.49, observed_value: 62, resolved_at: "2026-10-03T13:05:00Z" };
		expect(ok(resolved)).toBe(true);
		expect(ok({ ...resolved, brier: null })).toBe(false);
		expect(ok({ ...resolved, observed_value: null })).toBe(false);
		expect(ok({ ...resolved, resolved_at: null })).toBe(false);
	});

	it("anulada: sem resultado nem Brier, mesmo com a data de anulação", () => {
		const voided = { ...base, status: "void", resolved_at: "2026-10-03T13:40:00Z" };
		expect(ok(voided)).toBe(true);
		expect(ok({ ...voided, outcome: 1, brier: 0.2 })).toBe(false);
		expect(ok({ ...voided, brier: 0.2 })).toBe(false);
	});

	it("continua recusando probabilidade 0 ou 1 e fora do intervalo", () => {
		expect(ok({ ...base, probability: 1 })).toBe(false);
		expect(ok({ ...base, probability: 0 })).toBe(false);
		expect(ok({ ...base, probability: 0.9 })).toBe(false); // fora de [0.2, 0.4]
	});
});
