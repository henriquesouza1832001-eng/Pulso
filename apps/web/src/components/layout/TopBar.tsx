import type { Clock } from "../../hooks/useClock";

/** Barra fina do topo, no molde do pizzint: marca + contadores + nav + status. */
export function TopBar({
	clock,
	apiOnline,
	demo,
	sourcesCount,
	alertsCount,
	score,
	level,
}: {
	clock: Clock;
	apiOnline: boolean;
	demo: boolean;
	sourcesCount: number;
	alertsCount: number;
	score: number | null;
	level: number;
}) {
	return (
		<nav className="topbar">
			<div className="in">
				<a href="#topo" className="brand">
					<span className="mark" aria-hidden>
						▁▂▄▂▁
					</span>
					<b>PULSO</b>
					<span className="sub">BRASIL EM TEMPO REAL</span>
				</a>

				<a href="#topo" className={`pulsechip n${level}`}>
					PULSO {score ?? "--"} · N{level}
				</a>

				<span className="counter">
					27 UFS · {sourcesCount > 0 ? `${sourcesCount} FONTES` : "-- FONTES"} MONITORADAS
				</span>

				<div className="links">
					<a href="#feed">FEED</a>
					<a href="#mapa">MAPA</a>
					<a href="#mercados">MERCADOS</a>
					<a href="#historico">HISTÓRICO</a>
					<a href="#faq">FAQ</a>
				</div>

				<div className="right">
					{alertsCount > 0 && (
						<a href="#feed" className="alertchip">
							{alertsCount} ALERTAS
						</a>
					)}
					<span className={`statuspill ${apiOnline ? "" : "err"}`}>
						<i className="dot" /> {apiOnline ? "OPERACIONAL" : "DEGRADADO"}
					</span>
					{demo && <span className="badge-demo">DEMO DATA</span>}
					<span className="clock">{clock.br} UTC-3</span>
				</div>
			</div>
		</nav>
	);
}
