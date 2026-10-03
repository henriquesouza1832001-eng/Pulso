import { describe, expect, it, vi } from "vitest";
import { dispatchCollection, dispatchHealthcheck, dispatchWorkflow, isHealthcheckSlot } from "../src/lib/dispatch";

const env = { GH_DISPATCH_TOKEN: "tok", GITHUB_REPO: "dono/repo" };

describe("dispatchCollection", () => {
	it("não chama a rede sem token e explica o motivo", async () => {
		const f = vi.fn();
		const r = await dispatchCollection({ GITHUB_REPO: "dono/repo" }, f as unknown as typeof fetch);
		expect(r.ok).toBe(false);
		expect(r.reason).toMatch(/não configurado/);
		expect(f).not.toHaveBeenCalled();
	});

	it("aciona o workflow collect.yml em main com push=true", async () => {
		const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
		const r = await dispatchCollection(env, f as unknown as typeof fetch);
		expect(r).toEqual({ ok: true, status: 204 });
		const [url, init] = f.mock.calls[0];
		expect(url).toBe("https://api.github.com/repos/dono/repo/actions/workflows/collect.yml/dispatches");
		expect(JSON.parse(init.body)).toEqual({ ref: "main", inputs: { push: "true" } });
		expect(init.headers.Authorization).toBe("Bearer tok");
	});

	it("reporta falha de permissão sem lançar", async () => {
		const f = vi.fn().mockResolvedValue(new Response("nope", { status: 403 }));
		const r = await dispatchCollection(env, f as unknown as typeof fetch);
		expect(r).toMatchObject({ ok: false, status: 403 });
	});

	it("reporta erro de rede sem lançar", async () => {
		const f = vi.fn().mockRejectedValue(new Error("timeout"));
		const r = await dispatchCollection(env, f as unknown as typeof fetch);
		expect(r).toEqual({ ok: false, status: null, reason: "timeout" });
	});
});

describe("verificação de saúde pelo Cron da Cloudflare", () => {
	it("aciona healthcheck.yml em main, sem inputs", async () => {
		const f = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
		const r = await dispatchHealthcheck(env, f as unknown as typeof fetch);
		expect(r).toEqual({ ok: true, status: 204 });
		const [url, init] = f.mock.calls[0];
		expect(url).toBe("https://api.github.com/repos/dono/repo/actions/workflows/healthcheck.yml/dispatches");
		expect(JSON.parse(init.body)).toEqual({ ref: "main" });
	});

	it("só roda nos minutos 15 e 45 de cada hora (o Cron é de 5 em 5 min)", () => {
		const at = (min: number) => new Date(Date.UTC(2026, 9, 3, 7, min, 0));
		const slots = Array.from({ length: 12 }, (_, i) => i * 5).filter((m) => isHealthcheckSlot(at(m)));
		expect(slots).toEqual([15, 45]);
		expect(isHealthcheckSlot(at(0))).toBe(false);
		expect(isHealthcheckSlot(at(30))).toBe(false);
	});

	it("o workflow genérico não lança sem token nem em erro de rede", async () => {
		expect((await dispatchWorkflow({ GITHUB_REPO: "dono/repo" }, "x.yml")).ok).toBe(false);
		const f = vi.fn().mockRejectedValue(new Error("fora"));
		expect(await dispatchWorkflow(env, "x.yml", undefined, f as unknown as typeof fetch)).toEqual({ ok: false, status: null, reason: "fora" });
	});
});
