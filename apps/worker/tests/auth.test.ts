import { describe, expect, it } from "vitest";
import { engineAuthorized, safeEqual } from "../src/lib/auth";

describe("engineAuthorized", () => {
	it("aceita só 'Bearer <token>' com o token certo", () => {
		expect(engineAuthorized("Bearer segredo-123", "segredo-123")).toBe(true);
		expect(engineAuthorized("Bearer errado", "segredo-123")).toBe(false);
	});

	it("recusa o token cru, sem o esquema Bearer, e cabeçalhos vazios ou malformados", () => {
		expect(engineAuthorized("segredo-123", "segredo-123")).toBe(false); // antes: aceito
		expect(engineAuthorized("bearer segredo-123", "segredo-123")).toBe(false);
		expect(engineAuthorized("Bearer ", "segredo-123")).toBe(false);
		expect(engineAuthorized(undefined, "segredo-123")).toBe(false);
	});

	it("sem segredo configurado fecha tudo (fail-closed)", () => {
		expect(engineAuthorized("Bearer x", undefined)).toBe(false);
		expect(engineAuthorized("Bearer ", "")).toBe(false);
	});
});

describe("safeEqual", () => {
	it("compara certo e rejeita prefixos, sufixos e comprimentos diferentes", () => {
		expect(safeEqual("abc", "abc")).toBe(true);
		expect(safeEqual("abc", "abd")).toBe(false);
		expect(safeEqual("ab", "abc")).toBe(false);
		expect(safeEqual("abcd", "abc")).toBe(false);
		expect(safeEqual("", "abc")).toBe(false);
	});
});
