/** Sinais de um evento, já medidos na janela de análise. */
export interface PulsoSignals {
	articles: number;
	sources: number;
	/** Matérias por hora na janela recente. */
	velocity: number;
	/** Variação percentual vs. janela anterior (0 = estável). */
	growthPct: number;
	/** Soma de trust_level das fontes distintas. */
	trustSum: number;
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

/**
 * Pulso Score (0–100): mede intensidade informacional, não veracidade.
 * Cada componente é normalizado em 0–1 e ponderado.
 */
export function pulsoScore(s: PulsoSignals): number {
	const volume = clamp01(s.articles / 40);
	const diversidade = clamp01(s.sources / 15);
	const velocidade = clamp01(s.velocity / 20);
	const crescimento = clamp01(s.growthPct / 400);
	const relevancia = clamp01(s.trustSum / 45);
	const total =
		volume * 0.25 +
		diversidade * 0.25 +
		velocidade * 0.2 +
		crescimento * 0.15 +
		relevancia * 0.15;
	return Math.round(total * 100);
}

export function activityLabel(score: number): string {
	if (score >= 80) return "ATIVIDADE MUITO ALTA";
	if (score >= 60) return "ATIVIDADE ALTA";
	if (score >= 35) return "ATIVIDADE MODERADA";
	return "ATIVIDADE BAIXA";
}
