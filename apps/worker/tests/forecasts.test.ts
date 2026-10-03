import { describe, expect, it } from "vitest";
import { MIN_RESOLVED, calibrationError, classificationMetrics, methodKey, toForecast } from "../src/routes/forecasts";

const row = (method_version: string) => ({
	id: "fc-x", kind: "NOWCAST", question: "O Pulso será >= 50?", scope: "BR", metric: "pulse", comparator: "gte",
	threshold: 50, method: "pulse_empirical_delta", method_version, probability: 0.3, interval_low: 0.2, interval_high: 0.4,
	horizon_minutes: 60, created_at: "2026-10-03T00:00:00Z", resolves_at: "2026-10-03T01:00:00Z", evidence: "{}",
	status: "open", outcome: null, observed_value: null, resolved_at: null, brier: null,
});

describe("selo EXPERIMENTAL por método e versão", () => {
	const resolved = new Map([[methodKey("pulse_empirical_delta", "1"), MIN_RESOLVED]]);

	it("a versão com resolvidas suficientes deixa de ser experimental", () => {
		expect(toForecast(row("1"), resolved).experimental).toBe(false);
	});

	it("uma versão nova do mesmo método recomeça experimental (não herda a contagem das antigas)", () => {
		expect(toForecast(row("2"), resolved).experimental).toBe(true);
	});

	it("método sem nenhuma previsão resolvida é experimental e a evidência corrompida não derruba a API", () => {
		const f = toForecast({ ...row("1"), evidence: "{não é json" }, new Map());
		expect(f.experimental).toBe(true);
		expect(f.evidence).toEqual({});
	});
});

describe("métricas de calibração do track-record", () => {
	it("precision, recall e FPR no corte de 0,5; denominador zero devolve null (nunca 0 fingindo acerto)", () => {
		expect(classificationMetrics({ tp: 2, fp: 1, fn: 1, tn: 6 })).toEqual({ cutoff: 0.5, precision: 0.6667, recall: 0.6667, false_positive_rate: 0.1429 });
		expect(classificationMetrics({ tp: 0, fp: 0, fn: 0, tn: 20 })).toEqual({ cutoff: 0.5, precision: null, recall: null, false_positive_rate: 0 });
		expect(classificationMetrics({ tp: 0, fp: 0, fn: 0, tn: 0 }).false_positive_rate).toBeNull();
	});

	it("ECE pondera cada faixa pelo seu tamanho e é null sem amostras", () => {
		expect(calibrationError([])).toBeNull();
		const bins = [
			{ n: 17, mean_probability: 0.067, observed_rate: 0 },
			{ n: 3, mean_probability: 0.2822, observed_rate: 0 },
		];
		expect(calibrationError(bins)).toBeCloseTo((17 * 0.067 + 3 * 0.2822) / 20, 3);
		expect(calibrationError([{ n: 10, mean_probability: 0.8, observed_rate: 0.8 }])).toBe(0);
	});
});
