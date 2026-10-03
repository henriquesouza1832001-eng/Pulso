import type { ForecastCardData } from "../sections/Forecasts";

export function Markets({
	items,
	loading,
	error,
}: {
	items: ForecastCardData[];
	loading: boolean;
	error: string | null;
}) {
	return (
		<div className="mkt">
			<div className="mkt-head">
				<span className="mkt-title">PREVISÕES</span>
				<span className="dim">PROBABILIDADES</span>
			</div>
			{loading ? (
				<p className="state">CARREGANDO PREVISÕES…</p>
			) : error ? (
				<p className="state err">PREVISÕES INDISPONÍVEIS · {error}</p>
			) : items.length === 0 ? (
				<p className="state">SEM PREVISÕES ABERTAS</p>
			) : (
				<div className="mkt-list">
					{items.map((forecast) => {
						const probability = percent(forecast.probability);
						const low = forecast.intervalLow == null ? null : percent(forecast.intervalLow);
						const high = forecast.intervalHigh == null ? null : percent(forecast.intervalHigh);
						return (
							<article key={forecast.id} className="mkt-card">
								<div className="mkt-badges">
									<span className="mkt-forecast-label">PREVISÃO</span>
									{forecast.experimental && <span className="mkt-experimental">EXPERIMENTAL</span>}
									{forecast.demo && <span className="mkt-experimental">DEMO</span>}
								</div>
								<p className="mkt-q">{forecast.question}</p>
								<div className="mkt-row">
									<span className="mkt-yes">{probability}%</span>
									<span className="dim">{low == null || high == null ? "intervalo indisponível" : `intervalo ${low}%–${high}%`}</span>
								</div>
								<div className="mbar" aria-label={`Probabilidade de ${probability}%`}>
									<div className="y" style={{ width: `${probability}%` }} />
									<div className="n" style={{ width: `${100 - probability}%` }} />
								</div>
								<p className="mkt-drivers dim">
									{forecast.drivers ? `base: ${forecast.drivers}` : `evidência: ${summarizeEvidence(forecast.evidence)}`}
								</p>
								<p className="mkt-drivers dim">
									{forecast.scope} · {forecast.method} · horizonte {formatHorizon(forecast.horizonMinutes)}
									{forecast.resolvesAt && ` · vence ${formatTime(forecast.resolvesAt)}`}
								</p>
							</article>
						);
					})}
				</div>
			)}
			<p className="mkt-note dim">probabilidade com incerteza · previsões são estimativas, não fatos nem apostas.</p>
		</div>
	);
}

function percent(value: number): number {
	return Math.max(0, Math.min(100, Math.round(value * 100)));
}

function formatHorizon(minutes: number | null): string {
	if (minutes == null) return "não informado";
	if (minutes < 60) return `${minutes} min`;
	const hours = minutes / 60;
	return Number.isInteger(hours) ? `${hours} h` : `${hours.toFixed(1)} h`;
}

function summarizeEvidence(evidence: Record<string, unknown>): string {
	const details: string[] = [];
	if (typeof evidence.current_score === "number") details.push(`Pulso atual ${evidence.current_score}`);
	if (typeof evidence.pairs === "number") details.push(`${evidence.pairs} pares históricos`);
	if (typeof evidence.hits === "number") details.push(`${evidence.hits} ocorrências acima do limiar`);
	if (typeof evidence.history_hours === "number") details.push(`${evidence.history_hours} h de histórico`);
	if (typeof evidence.note === "string") details.push(evidence.note);
	return details.join(" · ") || "sem detalhe registrado";
}

function formatTime(iso: string): string {
	return new Date(iso).toLocaleTimeString("pt-BR", {
		timeZone: "America/Sao_Paulo",
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	});
}
