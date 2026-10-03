import { describe, expect, it } from "vitest";
import { CAMERAS } from "../src/data/cameras";

describe("catálogo de câmeras", () => {
	it("ids únicos, link https de origem e prévia https quando existe", () => {
		expect(new Set(CAMERAS.map((c) => c.id)).size).toBe(CAMERAS.length);
		for (const c of CAMERAS) {
			expect(c.page_url).toMatch(/^https:\/\//);
			expect(c.provider.length).toBeGreaterThan(0);
			if (c.preview) {
				expect(c.preview.url).toMatch(/^https:\/\//);
				expect(["iframe", "hls"]).toContain(c.preview.type);
			}
		}
	});

	it("lat/lon só existem como par (nunca coordenada inventada pela metade)", () => {
		for (const c of CAMERAS) expect(c.lat === null).toBe(c.lon === null);
	});
});
