/**
 * Veredito de saúde para o operador (docs/engineering/BACKEND_HARDENING.md §Observabilidade). Função pura: recebe fatos medidos e
 * devolve um estado e os MOTIVOS, para que "engine-status" responda em segundos "está saudável?" sem exigir leitura de números crus.
 *
 * Três níveis, como a diferença entre liveness e readiness: `ok`, `degraded` (serve, mas com ressalva) e `not_ready` (não deve receber tráfego).
 */
export type Level = "ok" | "degraded" | "not_ready";

export interface Facts {
	dbOk: boolean;
	dbLatencyMs: number | null;
	collectionAgeSeconds: number | null; // idade do último Pulso nacional; null = nunca houve
	budgetMode: "normal" | "economy" | "critical";
	investigationsActive: number;
}

export interface Assessment {
	status: Level;
	reasons: string[];
}

export const STALE_AFTER_SECONDS = 900; // 3 ciclos de 5 min
export const VERY_STALE_AFTER_SECONDS = 3600;
export const SLOW_DB_MS = 2000;
export const INVESTIGATION_FLOOD = 25; // muitas investigações abertas ao mesmo tempo sugere gatilho barulhento (ver Sentinela)

export function assess(f: Facts): Assessment {
	const reasons: string[] = [];
	let status: Level = "ok";
	const raise = (to: Level, why: string) => {
		reasons.push(why);
		if (to === "not_ready" || status === "ok") status = to;
	};
	if (!f.dbOk) raise("not_ready", "banco indisponível");
	else if (f.dbLatencyMs !== null && f.dbLatencyMs > SLOW_DB_MS) raise("degraded", `banco lento (${f.dbLatencyMs} ms)`);
	if (f.collectionAgeSeconds === null) raise("degraded", "nenhum Pulso registrado ainda");
	else if (f.collectionAgeSeconds > VERY_STALE_AFTER_SECONDS) raise("degraded", `coleta parada há ${Math.round(f.collectionAgeSeconds / 60)} min`);
	else if (f.collectionAgeSeconds > STALE_AFTER_SECONDS) raise("degraded", `coleta atrasada (${Math.round(f.collectionAgeSeconds / 60)} min sem Pulso novo)`);
	if (f.budgetMode === "critical") raise("degraded", "orçamento de escrita crítico: só o essencial é gravado");
	else if (f.budgetMode === "economy") raise("degraded", "orçamento de escrita em economia: shadow/diagnóstico suspensos");
	if (f.investigationsActive >= INVESTIGATION_FLOOD) raise("degraded", `${f.investigationsActive} investigações abertas (gatilho possivelmente barulhento)`);
	return { status, reasons };
}
