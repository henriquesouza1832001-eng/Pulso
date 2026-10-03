import { describe, expect, it } from "vitest";
import { toEpisodes } from "../src/routes/history";

const p = (t: string, score: number, alert_level: number) => ({ timestamp: t, score, alert_level });

describe("toEpisodes", () => {
	it("agrupa pontos consecutivos em um episódio e guarda o pico", () => {
		const eps = toEpisodes([
			p("2026-10-03T10:00:00Z", 62, 3),
			p("2026-10-03T10:05:00Z", 78, 4),
			p("2026-10-03T10:10:00Z", 66, 3),
		]);
		expect(eps).toHaveLength(1);
		expect(eps[0]).toMatchObject({ start: "2026-10-03T10:00:00Z", end: "2026-10-03T10:10:00Z", peak_score: 78, peak_level: 4, peak_at: "2026-10-03T10:05:00Z" });
	});

	it("separa episódios quando há lacuna maior que 30 min", () => {
		const eps = toEpisodes([p("2026-10-03T10:00:00Z", 60, 3), p("2026-10-03T10:40:00Z", 61, 3)]);
		expect(eps).toHaveLength(2);
	});

	it("lista vazia não gera episódio", () => {
		expect(toEpisodes([])).toEqual([]);
	});
});
