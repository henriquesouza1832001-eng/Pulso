import { useMemo } from "react";
import type { PulsoEvent } from "@pulso/shared";

/**
 * Cidades sob observação — o equivalente às pizzarias monitoradas do pizzint.
 * Fileira uniforme de cards: nome, badge de status (vocabular SPIKE/ELEVADO/
 * NORMAL/QUIET), mini-histograma 24h e contagem. A única fileira de cards da página.
 */
export function MonitoredCities({
	events,
	onSelect,
}: {
	events: PulsoEvent[];
	onSelect: (id: string) => void;
}) {
	const cities = useMemo(() => {
		const byKey = new Map<string, PulsoEvent[]>();
		for (const e of events) {
			const k = e.city ? `${e.city}|${e.state}` : `${e.state}|`;
			if (!byKey.has(k)) byKey.set(k, []);
			byKey.get(k)!.push(e);
		}
		return [...byKey.entries()]
			.map(([k, evs]) => {
				const worst = evs.reduce((a, b) => (b.pulse > a.pulse ? b : a));
				const signals = evs.reduce((a, e) => a + e.signal_count, 0);
				return { city: k.split("|")[0] || worst.state || "—", state: worst.state, evs, worst, signals };
			})
			.sort((a, b) => b.worst.pulse - a.worst.pulse)
			.slice(0, 6);
	}, [events]);

	if (cities.length === 0)
		return <p className="state">NENHUMA CIDADE COM SINAL · VARREDURA CONTÍNUA ATIVA</p>;

	return (
		<div className="cities">
			{cities.map((c) => {
				const lv = c.worst.alert_level;
				const status =
					lv >= 4 ? "CRÍTICO" : lv === 3 ? "ELEVADO" : lv === 2 ? "ATENÇÃO" : "NORMAL";
				const stClass = lv >= 4 ? "st-red" : lv === 3 ? "st-org" : lv === 2 ? "st-amb" : "st-grn";
				// variação: sinais chegando nas últimas 2h
				const recent = c.evs.filter(
					(e) => Date.now() - new Date(e.updated_at).getTime() < 2 * 3_600_000,
				);
				const recentSig = recent.reduce((a, e) => a + e.signal_count, 0);
				return (
					<article
						key={`${c.city}-${c.state}`}
						className="city"
						onClick={() => onSelect(c.worst.event_id)}
						role="button"
						tabIndex={0}
					>
						<div className="cy-top">
							<h3>{c.city.toUpperCase()}</h3>
							<span className={`cy-badge ${stClass}`}>{status}</span>
						</div>
						<span className="cy-uf dim">
							{c.state ?? "--"} · {c.evs.length} EVENTO{c.evs.length > 1 ? "S" : ""}
						</span>
						<Histo events={c.evs} level={lv} />
						<span className="cy-meta">
							<span className={`l${lv}`}>PULSO {c.worst.pulse}</span>
							{recentSig > 0 ? (
								<span className="cy-delta">▲ {recentSig}/2H</span>
							) : (
								<span className="dim">ESTÁVEL</span>
							)}
						</span>
					</article>
				);
			})}
		</div>
	);
}

/** Mini-histograma 24h por cidade: todos os eventos agregados, tooltip por hora. */
function Histo({ events, level }: { events: PulsoEvent[]; level: number }) {
	const bars = new Array(24).fill(0) as number[];
	const now = Date.now();
	for (const e of events) {
		const h = Math.floor((now - new Date(e.updated_at).getTime()) / 3_600_000);
		if (h >= 0 && h < 24) bars[23 - h] += Math.max(1, Math.round(e.signal_count / 4));
	}
	const max = Math.max(...bars, 1);
	const color =
		level >= 4 ? "var(--lv4)" : level === 3 ? "var(--lv3)" : level === 2 ? "var(--lv2)" : "var(--lv1)";
	const curHour = new Date()
		.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour12: false })
		.slice(0, 2);
	return (
		<div className="cy-histo" aria-hidden>
			{bars.map((v, i) => (
				<i
					key={i}
					title={`${String(i).padStart(2, "0")}h · ${v} sinais`}
					style={{
						height: `${Math.max(6, (v / max) * 100)}%`,
						background: v
							? String(i).padStart(2, "0") === curHour
								? "#ededed"
								: color
							: "var(--ln1)",
					}}
				/>
			))}
		</div>
	);
}
