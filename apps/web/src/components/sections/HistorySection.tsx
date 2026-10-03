import { useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import type { HistEntry } from "./Forecasts";
import { History } from "./Forecasts";

/** Dia (dd/mm) no fuso de Brasília, usado para agrupar o histórico. */
function brDay(iso: string): string {
	return new Date(iso).toLocaleDateString("pt-BR", {
		timeZone: "America/Sao_Paulo",
		day: "2-digit",
		month: "2-digit",
	});
}

/** Fica com o item mais importante de cada dia, mantendo a ordem dos dias. */
function topPerDay<T>(items: T[], day: (x: T) => string, beats: (b: T, a: T) => boolean): T[] {
	const best = new Map<string, T>();
	for (const x of items) {
		const d = day(x);
		const cur = best.get(d);
		if (!cur || beats(x, cur)) best.set(d, x);
	}
	return [...best.values()];
}

/** Evento fechado mais importante por dia: maior nível, depois severidade, depois pulso. */
function topEvents(events: PulsoEvent[]): PulsoEvent[] {
	const closed = events
		.filter((e) => e.status === "RESOLVED" || e.status === "RESOLVING")
		.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
	return topPerDay(
		closed,
		(e) => brDay(e.updated_at),
		(b, a) =>
			b.alert_level > a.alert_level ||
			(b.alert_level === a.alert_level &&
				(b.severity > a.severity || (b.severity === a.severity && b.pulse > a.pulse))),
	);
}

/** Entrada de maior nível por dia; empate fica com a mais recente (a lista já vem ordenada). */
function topEntries(entries: HistEntry[]): HistEntry[] {
	return topPerDay(entries, (h) => h.date, (b, a) => b.level > a.level);
}

/**
 * Histórico de inteligência — no molde do PIZZA INTELLIGENCE HISTORY:
 * tabs de período e retorno aos dados ao vivo. Cada período mostra só
 * o momento mais importante de cada dia.
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
			? { entries: [], events: topEvents(events) } // só eventos reais resolvidos nas últimas 24h
			: tab === "7d"
				? { entries: topEntries(entries.slice(0, 2)), events: [] }
				: { entries: topEntries(entries), events: [] };

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
