/**
 * Orçamento diário de escrita do D1 (plano gratuito: 100 mil linhas/dia, zera às 00:00 UTC).
 *
 * O Worker soma as linhas que cada ingestão gravou (`meta.rows_written`) numa tabela minúscula (`write_budget`) e,
 * conforme o consumo do dia, descarta o que é menos importante ANTES de gravar. O que é crítico (alertas altos, o
 * indicador nacional, resolução de previsões) passa sempre. Assim a cota nunca estoura (erro 500 para tudo) e, no pior
 * caso, o painel perde detalhe de baixa prioridade, não o que importa. Ver docs/decisions/0008-orcamento-de-escrita-do-d1.md.
 */

export const DAILY_LIMIT = 100_000;
export const ECONOMY_FROM = 60_000; // a partir daqui só o que tem relevância
export const CRITICAL_FROM = 85_000; // a partir daqui só alertas altos e o indicador nacional
export const RESERVE = 5_000; // folga para o que não passa pelo ingest (migrations, ajustes manuais)

// Reserva do orçamento (ver ingest.ts): estimativa POR CIMA do que um item pode custar (linha + índices no D1) e linhas fixas do contador.
export const RESERVE_ROWS_PER_ITEM = 3;
export const RESERVE_FIXED = 2;

export type BudgetMode = "normal" | "economy" | "critical";

export function budgetMode(usedToday: number): BudgetMode {
	if (usedToday >= CRITICAL_FROM) return "critical";
	if (usedToday >= ECONOMY_FROM) return "economy";
	return "normal";
}

export const utcDay = (d = new Date()) => d.toISOString().slice(0, 10);

export interface BatchLike {
	sources: unknown[];
	catalog_complete: boolean;
	events: { event_id: string; alert_level: number }[];
	signals: { event_id: string | null }[];
	pulses: { scope: string }[];
	source_health: { status: string }[];
	series: { scope: string }[];
	forecasts: { status: string }[];
	observations: { scope: string }[];
	investigations: { status: string }[];
	forecast_registry: unknown[];
	shadow_results: unknown[];
	driver_registry: unknown[];
	calibrators: unknown[];
	source_runtime: unknown[];
	engine_cycle: unknown | null;
}

/**
 * Remove do lote o que o modo manda economizar. Mantém a integridade: sinal só entra se o evento dele também entra
 * (a chave estrangeira exige que o evento exista) e `catalog_complete` vira false quando o catálogo é cortado
 * (senão as fontes ausentes seriam desativadas).
 */
export function shedBatch<T extends BatchLike>(b: T, mode: BudgetMode): { batch: T; shed: Record<string, number> } {
	if (mode === "normal") return { batch: b, shed: {} };
	const minLevel = mode === "critical" ? 3 : 2;
	const events = b.events.filter((e) => e.alert_level >= minLevel);
	const keep = new Set(events.map((e) => e.event_id));
	const signals = b.signals.filter((s) => s.event_id !== null && keep.has(s.event_id));
	const pulses = mode === "critical" ? b.pulses.filter((p) => p.scope === "BR") : b.pulses;
	const series = mode === "critical" ? [] : b.series.filter((s) => s.scope === "BR");
	const source_health = b.source_health.filter((h) => h.status !== "ONLINE");
	const forecasts = mode === "critical" ? b.forecasts.filter((f) => f.status !== "open") : b.forecasts;
	// histórico agregado: em economia só o nacional; em modo crítico nada (nunca se perde evento por causa dele)
	const observations = mode === "critical" ? [] : b.observations.filter((o) => o.scope === "BR");
	// investigações: em economia só abertura (NEW) e encerramento (CLOSED); em modo crítico nada
	const investigations = mode === "critical" ? [] : b.investigations.filter((i) => i.status === "NEW" || i.status === "CLOSED");
	// validação V2: em economia o registro de previsões (auditoria, minúsculo) continua e a comparação/drivers esperam; em crítico nada
	const forecast_registry = mode === "critical" ? [] : b.forecast_registry;
	const shadow_results: unknown[] = [];
	const driver_registry: unknown[] = [];
	// calibradores são raros e minúsculos (versões novas): continuam em economia; em modo crítico nada
	const calibrators = mode === "critical" ? [] : b.calibrators;
	// estado por fonte e resumo do ciclo são minúsculos e operacionais (breaker, frescor): continuam em economia; em crítico nada
	const source_runtime = mode === "critical" ? [] : b.source_runtime;
	const engine_cycle = mode === "critical" ? null : b.engine_cycle;
	const batch: T = { ...b, sources: [], catalog_complete: false, events, signals, pulses, series, source_health, forecasts, observations, investigations, forecast_registry, shadow_results, driver_registry, calibrators, source_runtime, engine_cycle };
	const shed = {
		events: b.events.length - events.length,
		signals: b.signals.length - signals.length,
		pulses: b.pulses.length - pulses.length,
		series: b.series.length - series.length,
		source_health: b.source_health.length - source_health.length,
		sources: b.sources.length,
		forecasts: b.forecasts.length - forecasts.length,
		observations: b.observations.length - observations.length,
		investigations: b.investigations.length - investigations.length,
		forecast_registry: b.forecast_registry.length - forecast_registry.length,
		shadow_results: b.shadow_results.length,
		driver_registry: b.driver_registry.length,
		calibrators: b.calibrators.length - calibrators.length,
		source_runtime: b.source_runtime.length - source_runtime.length,
		engine_cycle: b.engine_cycle && !engine_cycle ? 1 : 0,
	};
	return { batch, shed };
}
