import { useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import type { HistEntry } from "./Forecasts";
import { History } from "./Forecasts";

/**
 * Histórico de inteligência — no molde do PIZZA INTELLIGENCE HISTORY:
 * tabs de período, entradas datadas e retorno aos dados ao vivo.
 */
export function HistorySection({
	entries,
	events,
}: {
	entries: HistEntry[];
	events: PulsoEvent[];
}) {
	const [tab, setTab] = useState<"24h" | "7d" | "30d">("24h");
	const shown =
		tab === "24h"
			? { entries: [], events } // só eventos reais resolvidos nas últimas 24h
			: tab === "7d"
				? { entries: entries.slice(0, 2), events: [] }
				: { entries, events: [] };

	return (
		<div>
			<div className="tabs">
				{(["24h", "7d", "30d"] as const).map((t) => (
					<button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
						{t.toUpperCase()}
					</button>
				))}
			</div>
			{shown.entries.length === 0 && shown.events.length === 0 ? (
				<p className="state">SEM REGISTROS NESTE PERÍODO · O MOTOR AINDA NÃO FECHOU EVENTOS</p>
			) : (
				<History entries={shown.entries} events={shown.events} />
			)}
			<a className="back-live" href="#feed">
				↑ VOLTAR AOS DADOS AO VIVO
			</a>
		</div>
	);
}
