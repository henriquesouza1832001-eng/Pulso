import { describe, expect, it, vi } from "vitest";
import { dispatchCollection } from "../src/lib/dispatch";

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
