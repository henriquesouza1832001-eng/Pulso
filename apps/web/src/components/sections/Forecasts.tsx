import type { HistoryEntry, PulseHistoryPoint } from "../../lib/api";

export interface ForecastCardData {
	id: string;
	question: string;
	probability: number;
	intervalLow: number | null;
	intervalHigh: number | null;
	horizonMinutes: number | null;
	scope: string;
	method: string;
	evidence: Record<string, unknown>;
	resolvesAt: string | null;
	experimental: boolean;
	demo?: boolean;
	drivers?: string;
}

/** Gráfico do histórico real do Pulso; sem pontos, não desenha uma curva inventada. */
export function PulseSparkline({
	points,
	loading,
	error,
}: {
	points: PulseHistoryPoint[];
	loading: boolean;
	error: string | null;
}) {
	if (points.length < 2) {
		return <span className="dim">{loading ? "carregando histórico…" : error ? "histórico indisponível" : "histórico insuficiente para o gráfico"}</span>;
	}
	const width = 220;
	const height = 26;
	const min = Math.min(...points.map((point) => point.score));
	const max = Math.max(...points.map((point) => point.score));
	const range = max - min || 1;
	const path = points
		.map((point, index) => {
			const x = (index / (points.length - 1)) * width;
			const y = height - 3 - ((point.score - min) / range) * (height - 6);
			return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
		})
		.join(" ");
	return (
		<svg viewBox={`0 0 ${width} ${height}`} className="spark" preserveAspectRatio="none" role="img" aria-label="Histórico real do Pulso nas últimas 24 horas">
			<path d={path} fill="none" stroke="var(--acc)" strokeWidth="1.5" />
		</svg>
	);
}

/** Histórico de inteligência carregado da API pública. */
export function History({ entries }: { entries: HistoryEntry[] }) {
	return (
		<div className="hist">
			{entries.map((entry) => {
				const location = [entry.city, entry.state].filter(Boolean).join("/");
				const details = [
					location,
					entry.peak_pulse != null ? `PULSO ${entry.peak_pulse}` : null,
					entry.signal_count != null ? `${entry.signal_count} sinais` : null,
					entry.source_count != null ? `${entry.source_count} fontes` : null,
					entry.duration_minutes != null ? `${entry.duration_minutes} min` : null,
				].filter(Boolean);
				return (
					<div key={entry.event_id ?? `${entry.kind}-${entry.date}`} className="histrow">
						<span className="d dim">{brDateTime(entry.date)}</span>
						<span>
							{entry.title.toUpperCase()} · <b className={`l${entry.level}`}>N{entry.level}</b>
							{details.length > 0 && <span className="dim"> · {details.join(" · ")}</span>}
						</span>
					</div>
				);
			})}
		</div>
	);
}

function brDateTime(iso: string): string {
	return new Date(iso).toLocaleString("pt-BR", {
		timeZone: "America/Sao_Paulo",
		day: "2-digit",
		month: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	});
}
