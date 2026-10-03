import type { Clock } from "../../hooks/useClock";

/** Rodapé editorial do pizzint: promo, colunas de links, wordmark, status. */
export function Footer({
	clock,
	apiOnline,
	sourcesCount,
	demo,
}: {
	clock: Clock;
	apiOnline: boolean;
	sourcesCount: number;
	demo: boolean;
}) {
	return (
		<footer className="foot">
			<div className="foot-promo">
				<span className="kicker">PAINEL OSINT AO VIVO</span>
				<p>
					o pulso monitora sinais públicos do brasil 24/7 e transforma ruído em eventos com
					fonte, intensidade e histórico. independente, sem anúncios, sem dado pessoal.
				</p>
			</div>

			<div className="foot-cols">
				<div>
					<span className="kicker">ASSISTIR</span>
					<a href="#feed">Feed OSINT</a>
					<a href="#mapa">Mapa do Brasil</a>
					<a href="#cidades">Cidades monitoradas</a>
					<a href="#cameras">Câmeras</a>
				</div>
				<div>
					<span className="kicker">LER</span>
					<a href="#briefings">Briefings</a>
					<a href="#mercados">Mercados</a>
					<a href="#historico">Histórico de inteligência</a>
					<a href="#faq">FAQ e disclaimer</a>
				</div>
				<div>
					<span className="kicker">CONECTAR</span>
					<a href="https://github.com/henriquesouza1832001-eng/Pulso" target="_blank" rel="noreferrer">GitHub</a>
					<a href="/api/pulse/br">API pública</a>
					<a href="/api/events">Eventos (JSON)</a>
				</div>
			</div>

			<div className="foot-base">
				<span className="foot-mark" aria-hidden>PULSO</span>
				<div className="foot-meta">
					<span>
						<i className={`dot ${apiOnline ? "" : "err"}`} /> {apiOnline ? "OPERACIONAL" : "DEGRADADO"}
					</span>
					<span>{sourcesCount || "--"} FONTES REGISTRADAS</span>
					<span>{clock.date} · {clock.br} UTC-3</span>
					<span>© 2026 PULSO · DADOS PÚBLICOS · INDEPENDENTE</span>
					{demo && <span style={{ color: "var(--amb)" }}>MODO DEMO: DADOS FICTÍCIOS INTERCALADOS</span>}
				</div>
			</div>
		</footer>
	);
}
