import { describe, expect, it } from "vitest";
import { MIN_RESOLVED, methodKey, toForecast } from "../src/routes/forecasts";

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
