/**
 * Indicador nacional — o equivalente brasileiro do DOUGHCON do pizzint.
 * Numeral grande + estado do país + gauge discreto. É o bloco mais
 * importante da página: responde "como está o Brasil agora".
 */
import type { PulseSnapshot } from "@pulso/shared";
import type { Polling } from "../../hooks/usePolling";
import type { PulseHistoryPoint } from "../../lib/api";
import { LEVEL_PT } from "../../lib/format";
import { Gauge } from "../ui/Gauge";
import { HeroArt } from "../ui/HeroArt";
import { PulseSparkline } from "../sections/Forecasts";

export const LEVEL_SUB: Record<number, string> = {
	1: "SEM ANOMALIAS RELEVANTES NO PAÍS",
	2: "CRESCIMENTO GRADUAL DE SINAIS",
	3: "CONCENTRAÇÃO DE SINAIS EM VÁRIAS UFS",
	4: "MÚLTIPLOS EVENTOS CRÍTICOS SIMULTÂNEOS",
	5: "INTENSIDADE MÁXIMA REGISTRADA HOJE",
};

export function PulseIndicator({
	pulse,
	sourcesOnline,
	eventsCount,
	signals2h,
	statesActive,
	pulseHistory,
	pulseHistoryLoading,
	pulseHistoryError,
}: {
	pulse: Polling<PulseSnapshot>;
	sourcesOnline: number | null;
	eventsCount: number | null;
	signals2h: number | null;
	statesActive: number | null;
	pulseHistory: PulseHistoryPoint[];
	pulseHistoryLoading: boolean;
	pulseHistoryError: string | null;
}) {
	const d = pulse.data;
	const lv = d?.alert_level ?? 3;
	const lvVar = `var(--lv${lv})`;
	const onlineSources = sourcesOnline;

	return (
		<section className="pi" id="topo">
			<div className="piwm" aria-hidden>
				<HeroArt />
			</div>
			<div className="pi-in">
				<span className="pi-kicker">ÍNDICE NACIONAL DE SINAIS</span>

				<div className="pi-main">
					<div className="pi-numeral">
						<span className="pi-label">PULSO</span>
						<span className="pi-number" style={{ color: pulse.loading ? "var(--tx2)" : lvVar }}>
							{pulse.loading ? "--" : (d?.score ?? 0)}
						</span>
						<span className="pi-lv" style={{ color: lvVar }}>
							{LEVEL_PT[lv]}
						</span>
						<span className="pi-sub">{LEVEL_SUB[lv]}</span>
					</div>
					<div className="pi-side">
						<Gauge score={d?.score ?? 0} level={lv} loading={pulse.loading} />
					</div>
				</div>

				<div className="pi-stats">
					<span>
						<b className="pi-b">{eventsCount?.toLocaleString("pt-BR") ?? "--"}</b> eventos ativos
					</span>
					<span className="sep">·</span>
					<span>
						<b className="pi-b">{signals2h?.toLocaleString("pt-BR") ?? "--"}</b> sinais · 2h
					</span>
					<span className="sep">·</span>
					<span>
						<b className="pi-b">{statesActive == null ? "--" : `${statesActive}/27`}</b> UFs ativas
					</span>
					<span className="sep">·</span>
					<span>
						<b className="pi-b">{onlineSources ?? "--"}</b> fontes online
					</span>
					<span className="sep">·</span>
					<span>
						{d?.delta_2h != null && d.delta_2h !== 0 ? (
							<b className={d.delta_2h > 0 ? "l4" : "l1"}>
								{d.delta_2h > 0 ? "▲ +" : "▼ "}{Math.abs(d.delta_2h)} nas últimas 2h
							</b>
						) : (
							<b className="dim">estável nas últimas 2h</b>
						)}
					</span>
				</div>

				<div className="pi-curve">
					<span className="pc-label">PULSO · ÚLTIMAS 24H</span>
					<PulseSparkline points={pulseHistory} loading={pulseHistoryLoading} error={pulseHistoryError} />
				</div>

				{d && d.contributors.length > 0 && (
					<div className="pi-contribs">
						<span className="dim">MAIORES VARIAÇÕES:</span>
						{d.contributors.map((c) => (
							<span key={c.scope} className="pi-chip">
								{c.scope}{" "}
								<b className={c.delta >= 0 ? "l4" : "l1"}>
									{c.delta >= 0 ? "+" : ""}
									{c.delta}
								</b>
							</span>
						))}
					</div>
				)}

				<p className="pi-note">
					o índice mede intensidade de sinais públicos · não é probabilidade de dano nem prova de fato
				</p>
			</div>
		</section>
	);
}
