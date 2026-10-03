export interface DispatchEnv {
	/** Segredo: token fino do GitHub (só este repositório, permissão Actions: escrita). */
	GH_DISPATCH_TOKEN?: string;
	/** "dono/repositório". Não é segredo. */
	GITHUB_REPO: string;
}

export interface DispatchResult {
	ok: boolean;
	status: number | null;
	reason?: string;
}

/**
 * Aciona um workflow do GitHub Actions por `workflow_dispatch`.
 * O Cron Trigger da Cloudflare dispara no minuto certo; o GitHub só executa o Python.
 * Nunca lança: uma falha aqui não pode derrubar o Worker; o resultado vai para o log.
 */
export async function dispatchWorkflow(
	env: DispatchEnv,
	workflowFile: string,
	inputs?: Record<string, string>,
	fetchFn: typeof fetch = fetch,
): Promise<DispatchResult> {
	if (!env.GH_DISPATCH_TOKEN) return { ok: false, status: null, reason: "GH_DISPATCH_TOKEN não configurado" };
	try {
		const res = await fetchFn(
			`https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${workflowFile}/dispatches`,
			{
				method: "POST",
				headers: {
					Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
					Accept: "application/vnd.github+json",
					"X-GitHub-Api-Version": "2022-11-28",
					"User-Agent": "pulso-scheduler",
				},
				body: JSON.stringify(inputs ? { ref: "main", inputs } : { ref: "main" }),
			},
		);
		// 204 = aceito. 401/403 = token inválido/sem permissão. 404 = workflow ou repositório errado.
		return res.status === 204
			? { ok: true, status: 204 }
			: { ok: false, status: res.status, reason: `GitHub respondeu ${res.status}` };
	} catch (err) {
		return { ok: false, status: null, reason: err instanceof Error ? err.message : "erro de rede" };
	}
}

/** Coleta (Python Engine). */
export const dispatchCollection = (env: DispatchEnv, fetchFn: typeof fetch = fetch) =>
	dispatchWorkflow(env, "collect.yml", { push: "true" }, fetchFn);

/** Verificação de saúde da produção (`healthcheck.yml`). */
export const dispatchHealthcheck = (env: DispatchEnv, fetchFn: typeof fetch = fetch) =>
	dispatchWorkflow(env, "healthcheck.yml", undefined, fetchFn);

/**
 * A verificação de saúde roda nos minutos 15 e 45 de cada hora. O agendador do próprio GitHub (`schedule`) atrasa ou
 * ignora workflows novos por horas; o Cron da Cloudflare (a cada 5 min) é pontual, então é ele quem aciona.
 */
export const isHealthcheckSlot = (when: Date) => when.getUTCMinutes() % 30 === 15;
